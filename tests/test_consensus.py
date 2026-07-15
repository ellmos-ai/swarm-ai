# -*- coding: utf-8 -*-
"""
test_consensus.py -- Tests for consensus_swarm.py.

API calls are mocked. Focus on prompt building, consensus computation,
and the run_consensus orchestration logic.
"""
import pytest
from unittest.mock import patch, MagicMock

from tools.consensus_swarm import (
    build_prompts,
    compute_consensus,
    query_agent,
    run_consensus,
    DEFAULT_AGENTS,
    MODEL,
    COST_PER_1M,
    resolve_model_costs,
)


class TestBuildPrompts:
    """Tests for prompt construction per mode."""

    def test_answer_mode(self):
        system, user = build_prompts("What is Python?", mode="answer")
        assert "Wissens-Agent" in system
        assert "praezise" in system
        assert user == "What is Python?"

    def test_boolean_mode(self):
        system, user = build_prompts("Is Python typed?", mode="boolean")
        assert "JA" in system
        assert "NEIN" in system
        assert user == "Is Python typed?"

    def test_classify_mode(self):
        categories = ["positiv", "negativ", "neutral"]
        system, user = build_prompts(
            "Der Film war gut.",
            mode="classify",
            categories=categories,
        )
        assert "positiv" in system
        assert "negativ" in system
        assert "neutral" in system
        assert "GENAU EINE" in system

    def test_classify_without_categories_is_rejected(self):
        with pytest.raises(ValueError, match="requires"):
            build_prompts("Test", mode="classify", categories=None)


class TestComputeConsensus:
    """Tests for consensus computation logic."""

    def test_unanimous_boolean(self):
        results = [
            {"answer": "JA", "agent_id": i, "input_tokens": 10, "output_tokens": 5, "error": None}
            for i in range(5)
        ]
        consensus = compute_consensus(results, mode="boolean")
        assert consensus["consensus_answer"] == "JA"
        assert consensus["confidence"] == 1.0
        assert consensus["valid_responses"] == 5
        assert consensus["total_agents"] == 5

    def test_majority_boolean(self):
        results = [
            {"answer": "JA", "agent_id": 0, "input_tokens": 10, "output_tokens": 5, "error": None},
            {"answer": "JA", "agent_id": 1, "input_tokens": 10, "output_tokens": 5, "error": None},
            {"answer": "JA", "agent_id": 2, "input_tokens": 10, "output_tokens": 5, "error": None},
            {"answer": "NEIN", "agent_id": 3, "input_tokens": 10, "output_tokens": 5, "error": None},
            {"answer": "NEIN", "agent_id": 4, "input_tokens": 10, "output_tokens": 5, "error": None},
        ]
        consensus = compute_consensus(results, mode="boolean")
        assert consensus["consensus_answer"] == "JA"
        assert consensus["confidence"] == 0.6
        assert consensus["votes"]["JA"] == 3
        assert consensus["votes"]["NEIN"] == 2

    def test_classify_case_insensitive(self):
        results = [
            {"answer": "Positiv", "agent_id": 0, "input_tokens": 10, "output_tokens": 5, "error": None},
            {"answer": "positiv", "agent_id": 1, "input_tokens": 10, "output_tokens": 5, "error": None},
            {"answer": "POSITIV", "agent_id": 2, "input_tokens": 10, "output_tokens": 5, "error": None},
        ]
        consensus = compute_consensus(results, mode="classify")
        assert consensus["confidence"] == 1.0
        # All normalize to POSITIV
        assert "POSITIV" in consensus["votes"]

    def test_no_valid_answers(self):
        results = [
            {"answer": None, "agent_id": 0, "input_tokens": 0, "output_tokens": 0, "error": "timeout"},
            {"answer": None, "agent_id": 1, "input_tokens": 0, "output_tokens": 0, "error": "rate limit"},
        ]
        consensus = compute_consensus(results, mode="answer")
        assert consensus["consensus_answer"] is None
        assert consensus["confidence"] == 0.0
        assert consensus["valid_responses"] == 0

    def test_answer_mode_normalization(self):
        """Free-text answers should be normalized (lowercase, strip punctuation)."""
        results = [
            {"answer": "Paris.", "agent_id": 0, "input_tokens": 10, "output_tokens": 5, "error": None},
            {"answer": "paris", "agent_id": 1, "input_tokens": 10, "output_tokens": 5, "error": None},
            {"answer": "Paris!", "agent_id": 2, "input_tokens": 10, "output_tokens": 5, "error": None},
            {"answer": "Berlin", "agent_id": 3, "input_tokens": 10, "output_tokens": 5, "error": None},
        ]
        consensus = compute_consensus(results, mode="answer")
        assert consensus["confidence"] == 0.75  # 3/4 agree on "paris"

    def test_single_agent(self):
        results = [
            {"answer": "42", "agent_id": 0, "input_tokens": 10, "output_tokens": 5, "error": None},
        ]
        consensus = compute_consensus(results, mode="answer")
        assert consensus["confidence"] == 1.0
        assert consensus["consensus_answer"] == "42"

    def test_mixed_errors_and_valid(self):
        results = [
            {"answer": "Yes", "agent_id": 0, "input_tokens": 10, "output_tokens": 5, "error": None},
            {"answer": None, "agent_id": 1, "input_tokens": 0, "output_tokens": 0, "error": "fail"},
            {"answer": "Yes", "agent_id": 2, "input_tokens": 10, "output_tokens": 5, "error": None},
        ]
        consensus = compute_consensus(results, mode="answer")
        assert consensus["valid_responses"] == 2
        assert consensus["total_agents"] == 3
        assert consensus["confidence"] == pytest.approx(2 / 3)
        assert consensus["agreement_ratio"] == 1.0
        assert consensus["response_rate"] == pytest.approx(2 / 3)

    def test_invalid_boolean_answer_is_not_counted(self):
        results = [
            {"answer": "JA", "agent_id": 0, "input_tokens": 1, "output_tokens": 1, "error": None},
            {"answer": "Vielleicht", "agent_id": 1, "input_tokens": 1, "output_tokens": 1, "error": None},
        ]
        consensus = compute_consensus(results, mode="boolean")
        assert consensus["valid_responses"] == 1
        assert consensus["confidence"] == 0.5

    def test_tie_has_no_arbitrary_winner(self):
        results = [
            {"answer": "JA", "agent_id": 0, "input_tokens": 1, "output_tokens": 1, "error": None},
            {"answer": "NEIN", "agent_id": 1, "input_tokens": 1, "output_tokens": 1, "error": None},
        ]
        consensus = compute_consensus(results, mode="boolean")
        assert consensus["tie"] is True
        assert consensus["consensus_answer"] is None
        assert consensus["tied_answers"] == ["JA", "NEIN"]


class TestQueryAgent:
    """Tests for individual agent query with mocked API."""

    def test_successful_query(self, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = (
            mock_anthropic_client._make_response("Paris", 50, 10)
        )

        result = query_agent(mock_anthropic_client, 0, "System", "Question")
        assert result["answer"] == "Paris"
        assert result["agent_id"] == 0
        assert result["error"] is None
        assert result["input_tokens"] == 50
        assert result["output_tokens"] == 10

    def test_query_with_api_error(self, mock_anthropic_client):
        mock_anthropic_client.messages.create.side_effect = Exception("Connection failed")

        result = query_agent(mock_anthropic_client, 1, "System", "Question")
        assert result["answer"] is None
        assert result["error"] is not None
        assert "Connection failed" in result["error"]


class TestRunConsensus:
    """Tests for the full orchestration with dry_run."""

    def test_dry_run_no_api_call(self, capsys):
        result = run_consensus(
            question="Test question?",
            num_agents=3,
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert result["agents"] == 3
        assert result["conservative_cost_bound_usd"] > result["estimated_cost_usd"]
        captured = capsys.readouterr()
        assert "DRY-RUN" in captured.out
        assert "Geschaetzte Kosten" in captured.out

    @patch("tools.consensus_swarm.get_api_key", return_value="sk-test-key")
    @patch("tools.consensus_swarm.anthropic")
    def test_full_run_mocked(self, mock_anthropic_module, mock_get_key, capsys):
        """Full run with mocked Anthropic client."""
        mock_client = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        # All agents return "Paris"
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Paris")]
        mock_message.usage.input_tokens = 50
        mock_message.usage.output_tokens = 10
        mock_client.messages.create.return_value = mock_message

        result = run_consensus(
            question="What is the capital of France?",
            num_agents=3,
            workers=2,
            mode="answer",
            max_budget_usd=1.0,
        )

        assert result["consensus"]["consensus_answer"] == "Paris"
        assert result["consensus"]["confidence"] == 1.0
        assert result["stats"]["total_input_tokens"] == 150  # 3 * 50
        assert result["stats"]["total_output_tokens"] == 30  # 3 * 10

    def test_live_run_requires_budget_before_api_setup(self):
        with pytest.raises(ValueError, match="max_budget_usd"):
            run_consensus(question="Test", num_agents=1)
        with pytest.raises(ValueError, match="finite"):
            run_consensus(
                question="Test", num_agents=1, max_budget_usd=float("nan")
            )


class TestCostEstimation:
    """Tests for cost calculation constants."""

    def test_cost_per_1m_structure(self):
        assert "input" in COST_PER_1M
        assert "output" in COST_PER_1M
        assert COST_PER_1M["input"] > 0
        assert COST_PER_1M["output"] > 0

    def test_default_agents(self):
        assert DEFAULT_AGENTS == 5

    def test_model_is_haiku(self):
        assert "haiku" in MODEL.lower()

    def test_model_specific_costs(self):
        assert resolve_model_costs("claude-sonnet-5")["input"] == 3.0

    def test_unknown_model_requires_explicit_costs(self):
        with pytest.raises(ValueError, match="no pricing"):
            resolve_model_costs("future-model")
