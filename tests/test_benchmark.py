"""Focused validation tests for the benchmark CLI."""

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
