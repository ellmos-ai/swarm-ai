# -*- coding: utf-8 -*-
"""
test_imports.py -- Verify all core modules are importable.
"""


def test_import_runner():
    from tools.runner import ClaudeRunner
    assert ClaudeRunner is not None


def test_import_stigmergy_api():
    from tools.stigmergy_api import StigmergyAPI
    assert StigmergyAPI is not None


def test_import_stigmergy_convenience():
    from tools.stigmergy_api import deposit_pheromone, sense_pheromones, get_best_pheromone_path
    assert deposit_pheromone is not None
    assert sense_pheromones is not None
    assert get_best_pheromone_path is not None


def test_import_consensus():
    from tools.consensus_swarm import build_prompts, compute_consensus, run_consensus
    assert build_prompts is not None
    assert compute_consensus is not None
    assert run_consensus is not None


def test_import_translate_swarm():
    from tools.translate_swarm import chunk_texts
    assert chunk_texts is not None


def test_import_summarize_chunks():
    from tools.summarize_chunks import ChunkSummarizer, MODELS, COST_PER_1M
    assert ChunkSummarizer is not None
    assert "haiku" in MODELS
    assert "sonnet" in MODELS


def test_import_benchmark():
    import tools.benchmark as benchmark

    assert benchmark.run_benchmark is not None
