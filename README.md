# swarm-ai

**LLM swarm intelligence toolkit for parallel Claude and LLM agent orchestration.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Tests](https://github.com/ellmos-ai/swarm-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/ellmos-ai/swarm-ai/actions/workflows/ci.yml)
[![License MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![ellmos](https://img.shields.io/badge/ellmos-agent%20orchestration-4b5563)](https://github.com/ellmos-ai)

**Deutsch:** [README_de.md](README_de.md)

swarm-ai is a local-first Python toolkit for developers who want to run the same task through multiple LLM instances and merge the results. It focuses on five reusable coordination patterns: parallel chunk processing, boss/worker execution, stigmergy, consensus voting, and specialist routing.

It is not Docker Swarm, not a hosted agent platform, and not a generic "AI swarm" demo. The repository is a small, inspectable toolkit for experimenting with multi-agent LLM orchestration from the command line or from Python.

![swarm-ai coordination patterns](README/assets/swarm-patterns.svg)

## Discovery Context

Use `ellmos-ai/swarm-ai` when you need the canonical repository name. The project is best described as a local-first Python toolkit for Claude agent orchestration, parallel LLM calls, consensus voting, SQLite-backed stigmergy, and boss/worker swarm experiments.

Useful search phrases:

- `ellmos-ai swarm-ai`
- `Claude agent orchestration Python swarm`
- `parallel LLM consensus voting toolkit`
- `SQLite stigmergy agent coordination`
- `local-first multi-agent LLM orchestration`
- `boss worker LLM agents Python`

swarm-ai is intentionally smaller than enterprise agent platforms such as CrewAI, OpenAI Swarm derivatives, and hosted Swarms-style products. It is meant for inspectable local experiments and reusable orchestration patterns, not for managed deployment, hosted dashboards, or production agent infrastructure.

## Why swarm-ai

- **Parallel LLM execution:** fan out chunked work across multiple Claude or Anthropic calls.
- **Consensus checks:** ask several agents independently and compute response rate, agreement, confidence, and votes.
- **Stigmergy experiments:** use a SQLite-backed pheromone store so agents can leave indirect coordination signals.
- **Chain definitions:** describe hierarchy and specialist swarms as JSON files instead of hardcoding every run.
- **Local-first workflow:** code, prompts, benchmark results, and design notes stay in the repo.

## Patterns

| # | Pattern | Use it when | Implementation |
|---|---|---|---|
| 1 | **Parallel Chunks** | A large document or workload can be split and merged | `tools/translate_swarm.py`, `tools/summarize_chunks.py` |
| 2 | **Hierarchy / Boss + Worker** | One coordinator should dispatch work to several workers | `tools/runner.py`, `tools/swarm_haiku_3.json` |
| 3 | **Stigmergy / Pheromone Paths** | Agents should coordinate indirectly through shared markers | `tools/stigmergy_api.py` |
| 4 | **Consensus / Majority Vote** | You need multiple independent answers and a confidence score | `tools/consensus_swarm.py` |
| 5 | **Specialist / Boss Routing** | Different subtasks need different expert roles | `tools/swarm_haiku_research.json` |

## Coordination Guardrail: Team Locks

When multiple agents share files, tools, MCP sessions, or result artifacts, use a
project-local team lock before starting parallel work. The lock procedure is a
coordination layer around the five swarm patterns, not a sixth pattern. See
[`konzepte/team-lock-verfahren.md`](konzepte/team-lock-verfahren.md) for the
portable file format, claim rules, and lifecycle.
The tested `tools/team_lock.py` implementation uses atomic per-resource claim
files and immutable per-participant attendance records.

## Installation

```bash
git clone https://github.com/ellmos-ai/swarm-ai.git
cd swarm-ai
pip install -r requirements.txt
```

Set an Anthropic API key for tools that call the API:

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

The `ClaudeRunner` examples also require the `claude` CLI to be installed and authenticated.

## Quick Start

### Consensus swarm

Run several agents on the same question and aggregate the answer:

```bash
PYTHONIOENCODING=utf-8 python tools/consensus_swarm.py \
  --mode boolean \
  --agents 7 \
  --max-budget-usd 0.25 \
  --question "Is Python dynamically typed?"
```

Dry-run a consensus call without spending tokens:

```bash
PYTHONIOENCODING=utf-8 python tools/consensus_swarm.py --dry-run "Test question"
```

Use it from Python:

```python
from tools.consensus_swarm import run_consensus

result = run_consensus(
    question="Is Rust memory-safe?",
    num_agents=5,
    mode="boolean",
    max_budget_usd=0.25,
)

print(result["consensus"]["consensus_answer"])
print(result["consensus"]["confidence"])
```

### Stigmergy store

Agents can deposit, sense, and evaporate pheromone-like path markers in SQLite:

```python
from tools.stigmergy_api import StigmergyAPI

api = StigmergyAPI(db_path="swarm.db", agent_id="agent_A")

api.deposit("approach_refactor", strength=0.9, metadata={"result": "success"})
paths = api.sense()
best = api.get_best_path()
api.evaporate(decay_rate=0.1)
```

The file-backed schema is initialized automatically. `:memory:` is rejected
because a multi-connection coordination store must persist across connections.

### Parallel Claude CLI calls

Use `ClaudeRunner` when you want to fan out independent prompts through Claude Code:

```python
from tools.runner import ClaudeRunner

runner = ClaudeRunner(
    model="claude-haiku-4-5-20251001",
    max_budget_usd=0.25,
)
results = runner.run_parallel(
    [
        "Analyze security vulnerabilities in Flask apps",
        "Review Python packaging best practices",
        "Compare async frameworks in Python",
    ],
    max_workers=3,
)
```

The runner is read-only by default (`Read`, `Glob`, `Grep`), pre-approves only
that set in non-interactive `dontAsk` mode, denies configured MCP tools, and
does not persist sessions. Pass explicit `allowed_tools` and `available_tools`
only when a reviewed task really requires a wider capability surface.

### Standalone chunk databases

The database-bound tools can initialize their own schemas:

```bash
python tools/translate_swarm.py --init-db
python tools/summarize_chunks.py --init-db
python tools/translate_swarm.py --limit 20 --max-budget-usd 1
python tools/summarize_chunks.py --limit 20 --max-budget-usd 1
```

Translation results are matched by key and namespace rather than response order.
The summarizer uses expiring SQLite claims so concurrent runs do not pay twice
for the same chunk. Real API end-to-end verification remains an open release task.

## Benchmarks

The included benchmark compares sequential and parallel execution:

```bash
PYTHONIOENCODING=utf-8 python tools/benchmark.py
PYTHONIOENCODING=utf-8 python tools/benchmark.py --compare --workers 3 \
  --limit 5 --max-budget-usd 2
```

Measured result from `results/benchmark_20260306.json`:

| Metric | Sequential | Parallel (3 workers) | Result |
|---|---:|---:|---:|
| Total time | 1306s | 514s | 2.54x speedup |
| Success rate | 20/20 | 19/20 | 95% parallel success |
| Parallel efficiency | - | 85% | 85% |
| Time saved | - | 792s | 61% |

## Repository Layout

```text
swarm_ai/
|-- tools/
|   |-- runner.py                  # Claude CLI wrapper with run_parallel()
|   |-- consensus_swarm.py         # Majority vote and confidence scoring
|   |-- stigmergy_api.py           # SQLite pheromone coordination
|   |-- translate_swarm.py         # Parallel translation pattern
|   |-- summarize_chunks.py        # Parallel summarization pattern
|   |-- benchmark.py               # Sequential vs. parallel benchmark
|   |-- swarm_haiku_3.json         # Boss + worker chain definition
|   `-- swarm_haiku_research.json  # Specialist research chain
|-- konzepte/                      # German design documents
|-- experiments/                   # Experimental prototypes
|-- results/                       # Benchmark snapshots
`-- tests/                         # Pytest suite
```

## Project Status

swarm-ai is public and usable as an experimental toolkit. The core modules have a local test suite; some concept and experiment files still reference BACH because they document the origin of the patterns. Production use should start from the `tools/` modules and the tested Python APIs.

Historical launchers under `experiments/` fail closed. They require an explicit
test/full-run CLI mode, `SWARM_ENABLE_LEGACY_EXPERIMENTS=I_UNDERSTAND`, a
validated target, a per-agent budget environment variable, and a total-run CLI
budget. Write-capable dungeon and maintenance experiments additionally require
an isolated fixture marker. They run with Claude safe mode, a fixed built-in
tool allowlist, MCP disabled, and never modify user memory files.

Current verification:

- 166 local tests passing on the 2026-07-15 review baseline.
- Ruff, `compileall`, a high-severity Bandit gate, and pinned Linux/Windows/macOS GitHub Actions are enabled.
- MIT licensed.
- No package release on PyPI yet.
- No graphical interface or hosted landing page.

## Related ellmos Projects

- [BACH](https://github.com/ellmos-ai/bach): full text-based OS for LLM agents.
- [USMC](https://github.com/ellmos-ai/usmc): local SQLite memory primitive for LLM agents.
- [Rinnsal](https://github.com/ellmos-ai/rinnsal): lightweight LLM agent infrastructure.
- [clutch](https://github.com/ellmos-ai/clutch): provider-neutral routing for a single task.
- [MarbleRun](https://github.com/ellmos-ai/MarbleRun): chain execution for sequential agent loops.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Focus areas are standalone pattern cleanup, end-to-end examples, benchmark reproducibility, and clearer chain definitions.

## License

[MIT](LICENSE) - Copyright 2026 Lukas Geiger
