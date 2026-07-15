"""
swarm_ai.runner -- Claude CLI Wrapper
======================================
Core component: starts Claude processes with configurable parameters.
Handles environment, fallback, timeout, and output capture.
"""
import subprocess
import os
import math
from datetime import datetime


class ClaudeRunner:
    """Wrapper around the Claude CLI for automated calls."""

    def __init__(self, model="claude-sonnet-4-6", fallback_model=None,
                 permission_mode="dontAsk", allowed_tools=None, timeout=1800,
                 cwd=None, max_budget_usd=None, allow_mcp=False,
                 persist_sessions=False, available_tools=None):
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if (max_budget_usd is not None and
                (not math.isfinite(float(max_budget_usd)) or max_budget_usd <= 0)):
            raise ValueError("max_budget_usd must be finite and greater than zero")
        self.model = model
        self.fallback_model = fallback_model
        self.permission_mode = permission_mode
        # Safe default: callers must explicitly opt into shell or write access.
        self.allowed_tools = ["Read", "Glob", "Grep"] if allowed_tools is None else list(allowed_tools)
        self.available_tools = (
            list(self.allowed_tools) if available_tools is None else list(available_tools)
        )
        self.timeout = timeout
        self.cwd = cwd
        self.max_budget_usd = max_budget_usd
        self.allow_mcp = bool(allow_mcp)
        self.persist_sessions = bool(persist_sessions)

    def _build_env(self):
        """Prepare environment: remove CLAUDECODE, set encoding."""
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _build_cmd(self, prompt, **overrides):
        """Build the Claude CLI command."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        model = overrides.get("model", self.model)
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        continue_conv = overrides.get("continue_conversation", False)
        permission_mode = overrides.get("permission_mode", self.permission_mode)
        if not isinstance(permission_mode, str) or not permission_mode.strip():
            raise ValueError("permission_mode must be a non-empty string")
        allowed_overridden = "allowed_tools" in overrides
        allowed_tools = overrides.get("allowed_tools", self.allowed_tools)
        if isinstance(allowed_tools, str):
            raise TypeError("allowed_tools must be a sequence of tool names")
        allowed_tools = list(allowed_tools)
        if any(not isinstance(tool, str) or not tool.strip() for tool in allowed_tools):
            raise ValueError("allowed_tools entries must be non-empty strings")
        available_tools = overrides.get(
            "available_tools", allowed_tools if allowed_overridden else self.available_tools
        )
        if isinstance(available_tools, str):
            raise TypeError("available_tools must be a sequence of tool names")
        available_tools = list(available_tools)
        if any(not isinstance(tool, str) or not tool.strip() for tool in available_tools):
            raise ValueError("available_tools entries must be non-empty strings")

        cmd = ["claude"]
        if continue_conv:
            cmd.append("--continue")
        cmd.extend([
            "--model", model,
            "-p", prompt,
            "--permission-mode", permission_mode,
        ])
        # --tools only restricts built-in tools; MCP needs a separate deny rule.
        cmd.extend(["--tools", ",".join(available_tools)])
        if allowed_tools:
            cmd.extend(["--allowedTools", *allowed_tools])
        if not overrides.get("allow_mcp", self.allow_mcp):
            cmd.extend(["--disallowedTools", "mcp__*"])
        if not overrides.get("persist_sessions", self.persist_sessions):
            cmd.append("--no-session-persistence")
        fallback = overrides.get("fallback_model", self.fallback_model)
        if fallback:
            cmd.extend(["--fallback-model", fallback])
        max_budget = overrides.get("max_budget_usd", self.max_budget_usd)
        if max_budget is not None:
            if not math.isfinite(float(max_budget)) or max_budget <= 0:
                raise ValueError("max_budget_usd must be finite and greater than zero")
            cmd.extend(["--max-budget-usd", str(max_budget)])
        return cmd

    def run(self, prompt, **overrides):
        """
        Fuehrt einen Claude-Aufruf aus.

        Returns:
            dict mit keys: success, output, stderr, returncode, duration_s
        """
        cmd = self._build_cmd(prompt, **overrides)
        env = self._build_env()
        cwd = overrides.get("cwd", self.cwd)
        timeout = overrides.get("timeout", self.timeout)
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        start = datetime.now()
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=str(cwd) if cwd else None
            )
            duration = (datetime.now() - start).total_seconds()
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "stderr": result.stderr.strip() if result.stderr else "",
                "returncode": result.returncode,
                "duration_s": duration,
                "model": overrides.get("model", self.model),
            }

        except subprocess.TimeoutExpired:
            duration = (datetime.now() - start).total_seconds()
            return {
                "success": False,
                "output": "",
                "stderr": f"TIMEOUT nach {timeout}s",
                "returncode": -1,
                "duration_s": duration,
                "model": overrides.get("model", self.model),
            }

        except FileNotFoundError:
            return {
                "success": False,
                "output": "",
                "stderr": "claude CLI not found. Is Claude Code installed?",
                "returncode": -2,
                "duration_s": 0,
                "model": overrides.get("model", self.model),
            }

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            return {
                "success": False,
                "output": "",
                "stderr": str(e),
                "returncode": -3,
                "duration_s": duration,
                "model": overrides.get("model", self.model),
            }

    def run_parallel(self, prompts, max_workers=3, **overrides):
        """Execute multiple Claude calls in parallel.

        Args:
            prompts: Liste von Prompt-Strings oder Liste von Dicts mit {prompt, **overrides}
            max_workers: Maximale Anzahl paralleler Worker
            **overrides: Default-Overrides fuer alle Aufrufe

        Returns:
            Liste von Result-Dicts (gleiche Struktur wie run())
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if max_workers <= 0:
            raise ValueError("max_workers must be greater than zero")
        if isinstance(prompts, (str, bytes)):
            raise TypeError("prompts must be an iterable of prompt items, not a string")
        prompts = list(prompts)
        if len(prompts) > 100:
            raise ValueError("at most 100 prompts are allowed per parallel run")

        tasks = []
        for item in prompts:
            if isinstance(item, dict):
                item_copy = dict(item)
                if "prompt" not in item_copy:
                    raise ValueError("Dict prompt items must include a 'prompt' key")
                prompt = item_copy.pop("prompt")
                merged = {**overrides, **item_copy}
                tasks.append((prompt, merged))
            else:
                tasks.append((item, overrides))

        for prompt, _ in tasks:
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("each prompt must be a non-empty string")

        results = [None] * len(tasks)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {}
            for idx, (prompt, ovr) in enumerate(tasks):
                future = executor.submit(self.run, prompt, **ovr)
                future_to_idx[future] = idx

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    task_overrides = tasks[idx][1]
                    results[idx] = {
                        "success": False, "output": "", "stderr": str(e),
                        "returncode": -4, "duration_s": 0,
                        "model": task_overrides.get("model", self.model),
                    }

        return results

    def pipe(self, prompt, **overrides):
        """Kurzform: Prompt rein, Text raus. Wirft Exception bei Fehler."""
        result = self.run(prompt, **overrides)
        if not result["success"]:
            raise RuntimeError(f"Claude Fehler (rc={result['returncode']}): {result['stderr']}")
        return result["output"]
