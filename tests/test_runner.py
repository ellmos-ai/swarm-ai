# -*- coding: utf-8 -*-
"""
test_runner.py -- Unit tests for ClaudeRunner (tools/runner.py).

All tests mock subprocess.run to avoid actual CLI calls.
"""
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from tools.runner import ClaudeRunner


class TestClaudeRunnerInit:
    """Tests for ClaudeRunner construction and defaults."""

    def test_default_values(self):
        runner = ClaudeRunner()
        assert runner.model == "claude-sonnet-4-6"
        assert runner.fallback_model is None
        assert runner.permission_mode == "dontAsk"
        assert runner.timeout == 1800
        assert runner.cwd is None
        assert "Read" in runner.allowed_tools
        assert "Bash" in runner.allowed_tools

    def test_custom_values(self):
        runner = ClaudeRunner(
            model="claude-haiku-4-5-20251001",
            fallback_model="claude-sonnet-4-6",
            permission_mode="strict",
            timeout=60,
            cwd="/tmp/test",
            allowed_tools=["Read"],
        )
        assert runner.model == "claude-haiku-4-5-20251001"
        assert runner.fallback_model == "claude-sonnet-4-6"
        assert runner.timeout == 60
        assert runner.cwd == "/tmp/test"
        assert runner.allowed_tools == ["Read"]


class TestBuildEnv:
    """Tests for _build_env method."""

    def test_removes_claudecode(self):
        runner = ClaudeRunner()
        with patch.dict("os.environ", {"CLAUDECODE": "1", "PATH": "/usr/bin"}):
            env = runner._build_env()
            assert "CLAUDECODE" not in env
            assert "PATH" in env

    def test_sets_pythonioencoding(self):
        runner = ClaudeRunner()
        env = runner._build_env()
        assert env["PYTHONIOENCODING"] == "utf-8"


class TestBuildCmd:
    """Tests for _build_cmd method."""

    def test_basic_command(self):
        runner = ClaudeRunner(model="claude-haiku-4-5-20251001")
        cmd = runner._build_cmd("Hello")
        assert cmd[0] == "claude"
        assert "--model" in cmd
        assert "claude-haiku-4-5-20251001" in cmd
        assert "-p" in cmd
        assert "Hello" in cmd
        assert "--permission-mode" in cmd
        assert "dontAsk" in cmd

    def test_continue_conversation(self):
        runner = ClaudeRunner()
        cmd = runner._build_cmd("Hello", continue_conversation=True)
        assert "--continue" in cmd

    def test_fallback_model(self):
        runner = ClaudeRunner(fallback_model="claude-haiku-4-5-20251001")
        cmd = runner._build_cmd("Hello")
        assert "--fallback-model" in cmd
        assert "claude-haiku-4-5-20251001" in cmd

    def test_override_model(self):
        runner = ClaudeRunner(model="claude-sonnet-4-6")
        cmd = runner._build_cmd("Hello", model="claude-haiku-4-5-20251001")
        assert "claude-haiku-4-5-20251001" in cmd


class TestRun:
    """Tests for run() method with mocked subprocess."""

    @patch("tools.runner.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Hello World",
            stderr="",
        )
        runner = ClaudeRunner()
        result = runner.run("Test prompt")

        assert result["success"] is True
        assert result["output"] == "Hello World"
        assert result["returncode"] == 0
        assert result["duration_s"] >= 0
        assert result["model"] == "claude-sonnet-4-6"

    @patch("tools.runner.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error occurred",
        )
        runner = ClaudeRunner()
        result = runner.run("Test prompt")

        assert result["success"] is False
        assert result["returncode"] == 1
        assert "Error" in result["stderr"]

    @patch("tools.runner.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=10)
        runner = ClaudeRunner(timeout=10)
        result = runner.run("Test prompt")

        assert result["success"] is False
        assert result["returncode"] == -1
        assert "TIMEOUT" in result["stderr"]

    @patch("tools.runner.subprocess.run")
    def test_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("claude not found")
        runner = ClaudeRunner()
        result = runner.run("Test prompt")

        assert result["success"] is False
        assert result["returncode"] == -2
        assert "not found" in result["stderr"]

    @patch("tools.runner.subprocess.run")
    def test_generic_exception(self, mock_run):
        mock_run.side_effect = OSError("Some OS error")
        runner = ClaudeRunner()
        result = runner.run("Test prompt")

        assert result["success"] is False
        assert result["returncode"] == -3


class TestRunParallel:
    """Tests for run_parallel() method."""

    @patch("tools.runner.subprocess.run")
    def test_parallel_with_strings(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Result",
            stderr="",
        )
        runner = ClaudeRunner()
        results = runner.run_parallel(["Prompt 1", "Prompt 2"], max_workers=2)

        assert len(results) == 2
        assert all(r["success"] for r in results)

    @patch("tools.runner.subprocess.run")
    def test_parallel_with_dicts(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Result",
            stderr="",
        )
        runner = ClaudeRunner()
        prompts = [
            {"prompt": "Task A", "model": "claude-haiku-4-5-20251001"},
            {"prompt": "Task B"},
        ]
        results = runner.run_parallel(prompts, max_workers=2)

        assert len(results) == 2
        assert all(r["success"] for r in results)

    @patch("tools.runner.subprocess.run")
    def test_parallel_preserves_order(self, mock_run):
        """Results should be in the same order as input prompts."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            return MagicMock(
                returncode=0,
                stdout=f"Result {call_count[0]}",
                stderr="",
            )

        mock_run.side_effect = side_effect
        runner = ClaudeRunner()
        results = runner.run_parallel(["A", "B", "C"], max_workers=1)

        assert len(results) == 3
        assert all(r is not None for r in results)

    def test_parallel_dict_requires_prompt_key(self):
        runner = ClaudeRunner()
        with pytest.raises(ValueError, match="prompt"):
            runner.run_parallel([{"model": "claude-haiku-4-5-20251001"}])


class TestPipe:
    """Tests for pipe() convenience method."""

    @patch("tools.runner.subprocess.run")
    def test_pipe_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Output text",
            stderr="",
        )
        runner = ClaudeRunner()
        output = runner.pipe("Test")
        assert output == "Output text"

    @patch("tools.runner.subprocess.run")
    def test_pipe_raises_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error",
        )
        runner = ClaudeRunner()
        with pytest.raises(RuntimeError, match="Claude Fehler"):
            runner.pipe("Test")
