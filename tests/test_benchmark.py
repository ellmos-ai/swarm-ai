"""Focused validation tests for the benchmark CLI."""

import json

import pytest

from tools import benchmark


@pytest.mark.parametrize("budget", ["nan", "inf"])
def test_live_benchmark_rejects_nonfinite_budget(monkeypatch, budget):
    monkeypatch.setattr(
        "sys.argv",
        ["benchmark", "--run", "--limit", "1", "--max-budget-usd", budget],
    )
    with pytest.raises(SystemExit):
        benchmark.main()


def test_benchmark_requires_explicit_pricing_for_unknown_model(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["benchmark", "--model", "future-model"],
    )
    with pytest.raises(SystemExit):
        benchmark.main()


def test_dry_run_export_contains_pricing_and_metadata(monkeypatch, tmp_path):
    export_path = tmp_path / "benchmark.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark",
            "--category", "software_dev",
            "--export", str(export_path),
        ],
    )

    assert benchmark.main() == 0

    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["schema_version"] == "1.0"
    assert exported["dry_run"] is True
    assert exported["model"] == benchmark.DEFAULT_MODEL
    assert exported["model_pricing"] == {
        "currency": "USD",
        "unit": "per_1m_tokens",
        "input": 1.0,
        "output": 5.0,
        "source": "configured MODEL_COSTS_PER_1M or explicit CLI override",
    }
    assert exported["environment"]["repository"] == "ellmos-ai/swarm-ai"
    assert exported["task_count"] == len(exported["tasks"]) == 5
    assert exported["estimated_total_cost_usd"] > 0


def test_record_result_adds_estimated_cost():
    task = {"name": "one", "prompt": "a" * 8, "category": "test"}
    result = {
        "success": True,
        "output": "b" * 8,
        "duration_s": 0.1,
        "model": benchmark.DEFAULT_MODEL,
        "returncode": 0,
    }

    record = benchmark._record_result(task, result, "sequential", {"input": 1, "output": 5})

    assert record["estimated_input_tokens"] == 2
    assert record["estimated_output_tokens"] == 2
    assert record["estimated_cost_usd"] == pytest.approx(0.000012)
