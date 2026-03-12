# swarm-ai

**LLM swarm intelligence toolkit** — 5 parallel execution patterns for orchestrating multiple LLM instances.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

---

## Overview

swarm-ai implements five swarm intelligence patterns for parallel LLM execution. Each pattern addresses a different coordination need — from simple parallel chunking to emergent pheromone-based path selection.

| # | Pattern | Description | Module |
|---|---------|-------------|--------|
| 1 | **Epstein (Parallel Chunks)** | Split work into chunks, process in parallel, merge results | `translate_swarm.py`, `summarize_chunks.py` |
| 2 | **Hierarchy (Boss + Worker)** | Coordinator dispatches tasks to workers, aggregator merges | `swarm_haiku_3.json`, `runner.py` |
| 3 | **Stigmergy (Pheromone)** | Agents communicate indirectly via shared markers (ant-colony style) | `stigmergy_api.py` |
| 4 | **Consensus (Majority Vote)** | Multiple agents answer the same question, majority wins | `consensus_swarm.py` |
| 5 | **Specialist (Boss Routing)** | Boss routes tasks to domain-specific expert agents | Chain definitions (JSON) |

---

## Installation

```bash
git clone https://github.com/lukisch/swarm-ai.git
cd swarm-ai
pip install -r requirements.txt
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

---

## Quick Start

### 1. Epstein — Parallel Chunk Processing

Split large workloads into chunks and process them with parallel LLM instances:

```bash
PYTHONIOENCODING=utf-8 python tools/translate_swarm.py --dry-run
PYTHONIOENCODING=utf-8 python tools/summarize_chunks.py --dry-run
```

### 2. Hierarchy — Boss + Worker Chain

Coordinator assigns tasks, workers execute in parallel, aggregator merges results:

```bash
# Chain definitions (Coordinator + 3 Workers + Aggregator)
cat tools/swarm_haiku_3.json
```

```python
from tools.runner import ClaudeRunner

runner = ClaudeRunner(model="claude-haiku-4-5-20251001")
results = runner.run_parallel([
    "Analyze security vulnerabilities in Flask apps",
    "Review Python packaging best practices",
    "Compare async frameworks in Python",
], max_workers=3)
```

### 3. Stigmergy — Pheromone-Based Coordination

Agents leave markers ("pheromones") on paths. Other agents sense these markers to follow promising directions:

```python
from tools.stigmergy_api import StigmergyAPI

api = StigmergyAPI(db_path="swarm.db", agent_id="agent_A")

# Agent A marks a successful path
api.deposit("approach_refactor", strength=0.9, metadata={"result": "success"})

# Agent B reads which paths are promising
paths = api.sense()  # sorted by strength DESC
best = api.get_best_path()  # -> "approach_refactor"

# Evaporate weak pheromones (cleanup)
api.evaporate(decay_rate=0.1)
```

### 4. Consensus — Majority Vote

Multiple LLM instances answer the same question independently, then a majority vote determines the final answer:

```bash
# Simple question (5 agents, majority vote)
PYTHONIOENCODING=utf-8 python tools/consensus_swarm.py "What is the capital of France?"

# Classification mode with predefined categories
PYTHONIOENCODING=utf-8 python tools/consensus_swarm.py \
    --mode classify \
    --categories "positive,negative,neutral" \
    --question "The movie was okay."

# Boolean mode (yes/no)
PYTHONIOENCODING=utf-8 python tools/consensus_swarm.py \
    --mode boolean \
    --agents 7 \
    --question "Is Python dynamically typed?"

# Dry run (cost estimate only)
PYTHONIOENCODING=utf-8 python tools/consensus_swarm.py --dry-run "Test question"
```

```python
from tools.consensus_swarm import run_consensus

result = run_consensus(
    question="Is Rust memory-safe?",
    num_agents=5,
    mode="boolean",
)
print(result["consensus"]["consensus_answer"])  # "JA"
print(result["consensus"]["confidence"])         # 1.0
```

### 5. Specialist — Boss Routing

The boss analyzes incoming tasks and routes them to domain-specific expert agents. Configuration via JSON chain definitions:

```bash
cat tools/swarm_haiku_research.json  # Planner + 5 Researchers + Synthesizer
```

---

## Benchmarks

Run the benchmark suite to compare sequential vs. parallel execution:

```bash
# Show available tasks (dry-run)
PYTHONIOENCODING=utf-8 python tools/benchmark.py

# Run comparison
PYTHONIOENCODING=utf-8 python tools/benchmark.py --compare --workers 3

# Export results
PYTHONIOENCODING=utf-8 python tools/benchmark.py --compare \
    --export results/benchmark_$(date +%Y%m%d).json
```

### Results (2026-03-06, Claude Haiku 4.5, 20 tasks, 3 workers)

| Metric | Sequential | Parallel (3W) | Speedup |
|--------|-----------|---------------|---------|
| Total time | 1306s | 514s | **2.54x** |
| Success rate | 20/20 | 19/20 | — |
| Parallel efficiency | — | — | 85% |
| Time saved | — | 792s (61%) | — |

Full results: [`results/benchmark_20260306.json`](results/benchmark_20260306.json)

---

## Architecture

```
swarm_ai/
├── tools/
│   ├── runner.py              # ClaudeRunner — CLI wrapper with run_parallel()
│   ├── consensus_swarm.py     # Consensus pattern (majority vote)
│   ├── stigmergy_api.py       # Stigmergy pattern (pheromone coordination)
│   ├── translate_swarm.py     # Epstein pattern (parallel translation)
│   ├── summarize_chunks.py    # Epstein pattern (parallel summarization)
│   ├── benchmark.py           # Sequential vs. parallel benchmarking
│   ├── swarm_haiku_3.json     # Hierarchy chain (3 workers)
│   └── swarm_haiku_research.json  # Specialist chain (5 researchers)
├── konzepte/                  # Design documents (German)
│   ├── schwarm-operationen.md
│   ├── schwarm-entscheidungsbaum.md
│   └── trampelpfadanalyse.md
├── results/                   # Benchmark results (JSON)
└── tests/                     # Test scripts
```

### Core Components

- **`ClaudeRunner`** (`runner.py`): Wraps the Claude CLI with configurable model, timeout, permission mode, and parallel execution via `ThreadPoolExecutor`.
- **`StigmergyAPI`** (`stigmergy_api.py`): SQLite-backed pheromone store. Agents deposit, sense, and evaporate pheromones to coordinate without direct communication.
- **`consensus_swarm`**: Runs N agents on the same prompt with `temperature=0.7` for diversity, then computes agreement ratio and confidence score.
- **`benchmark`**: 20 tasks across 4 categories (software dev, research, wiki, code review) for measuring parallel speedup.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE) — Copyright 2026 Lukas Geiger
