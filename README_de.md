# swarm-ai

**LLM-Schwarmintelligenz-Toolkit für parallele Claude- und LLM-Agenten-Orchestrierung.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Tests](https://github.com/ellmos-ai/swarm-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/ellmos-ai/swarm-ai/actions/workflows/ci.yml)
[![Lizenz MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![ellmos](https://img.shields.io/badge/ellmos-Agenten--Orchestrierung-4b5563)](https://github.com/ellmos-ai)

**English:** [README.md](README.md)

swarm-ai ist ein local-first Python-Toolkit für Entwicklerinnen und Entwickler, die dieselbe Aufgabe über mehrere LLM-Instanzen ausführen und die Ergebnisse anschließend zusammenführen wollen. Der Fokus liegt auf fünf wiederverwendbaren Koordinationsmustern: parallele Chunk-Verarbeitung, Boss-/Worker-Ausführung, Stigmergie, Konsensabstimmung und Spezialisten-Routing.

Das Projekt ist kein Docker-Swarm-Werkzeug, keine gehostete Agentenplattform und keine generische "AI swarm"-Demo. Es ist ein kleines, prüfbares Toolkit für Experimente mit Multi-Agent-LLM-Orchestrierung über CLI und Python.

![swarm-ai Koordinationsmuster](README/assets/swarm-patterns.svg)

## Auffindbarkeitskontext

Nutze `ellmos-ai/swarm-ai`, wenn der kanonische Repository-Name gemeint ist. Das Projekt lässt sich am besten als local-first Python-Toolkit für Claude-Agenten-Orchestrierung, parallele LLM-Aufrufe, Konsensabstimmung, SQLite-gestützte Stigmergie und Boss-/Worker-Schwarmexperimente beschreiben.

Nützliche Suchphrasen:

- `ellmos-ai swarm-ai`
- `Claude agent orchestration Python swarm`
- `parallel LLM consensus voting toolkit`
- `SQLite stigmergy agent coordination`
- `local-first multi-agent LLM orchestration`
- `boss worker LLM agents Python`

swarm-ai ist bewusst kleiner als Enterprise-Agentenplattformen wie CrewAI, OpenAI-Swarm-Ableitungen oder gehostete Swarms-Produkte. Es ist für prüfbare lokale Experimente und wiederverwendbare Orchestrierungsmuster gedacht, nicht für Managed Deployment, gehostete Dashboards oder produktive Agenteninfrastruktur.

## Warum swarm-ai

- **Parallele LLM-Ausführung:** große Aufgaben in Teilstücke aufteilen und über mehrere Claude- oder Anthropic-Aufrufe verarbeiten.
- **Konsensprüfungen:** mehrere Agenten unabhängig antworten lassen und Antwortrate, Zustimmung, Konfidenz und Stimmen berechnen.
- **Stigmergie-Experimente:** ein SQLite-basierter Pheromonspeicher ermöglicht indirekte Koordinationssignale zwischen Agenten.
- **Chain-Definitionen:** Hierarchie- und Spezialisten-Schwärme werden als JSON beschrieben statt fest verdrahtet.
- **Local-first Workflow:** Code, Prompts, Benchmarks und Designdokumente bleiben lokal und versioniert im Repo.

## Muster

| # | Muster | Geeignet für | Implementierung |
|---|---|---|---|
| 1 | **Parallel-Chunks** | Große Dokumente oder Aufgaben, die teilbar und zusammenführbar sind | `tools/translate_swarm.py`, `tools/summarize_chunks.py` |
| 2 | **Hierarchie / Boss + Worker** | Ein Koordinator verteilt Arbeit an mehrere Worker | `tools/runner.py`, `tools/swarm_haiku_3.json` |
| 3 | **Stigmergie / Pheromonpfade** | Agenten koordinieren sich indirekt über gemeinsame Marker | `tools/stigmergy_api.py` |
| 4 | **Konsens / Mehrheitsentscheid** | Mehrere unabhängige Antworten sollen zu Konfidenz und Abstimmung führen | `tools/consensus_swarm.py` |
| 5 | **Spezialist / Boss-Routing** | Unterschiedliche Teilaufgaben brauchen unterschiedliche Expertenrollen | `tools/swarm_haiku_research.json` |

## Koordinations-Guardrail: Team-Locks

Wenn mehrere Agenten Dateien, Tools, MCP-Sitzungen oder Ergebnisartefakte teilen,
sollte vor der parallelen Arbeit ein projektlokaler Team-Lock gesetzt werden. Das
Lock-Verfahren ist eine Koordinationsschicht um die fünf Schwarmmuster, kein
sechstes Muster. Das portable Dateiformat, Claim-Regeln und der Lebenszyklus sind
in [`konzepte/team-lock-verfahren.md`](konzepte/team-lock-verfahren.md) beschrieben.
Die getestete Implementierung `tools/team_lock.py` nutzt atomare Claims pro
Ressource und unveränderliche Anwesenheitsdateien pro Teilnehmer.

## Installation

```bash
git clone https://github.com/ellmos-ai/swarm-ai.git
cd swarm-ai
pip install -r requirements.txt
```

Für Tools mit API-Aufrufen wird ein Anthropic API-Key benötigt:

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

Die `ClaudeRunner`-Beispiele benötigen zusätzlich eine installierte und authentifizierte `claude`-CLI.

## Schnellstart

### Konsens-Schwarm

Mehrere Agenten beantworten dieselbe Frage, anschließend wird aggregiert:

```bash
PYTHONIOENCODING=utf-8 python tools/consensus_swarm.py \
  --mode boolean \
  --agents 7 \
  --max-budget-usd 0.25 \
  --question "Is Python dynamically typed?"
```

Trockenlauf ohne Tokenkosten:

```bash
PYTHONIOENCODING=utf-8 python tools/consensus_swarm.py --dry-run "Test question"
```

Nutzung aus Python:

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

### Stigmergie-Speicher

Agenten können pheromonartige Pfadmarker in SQLite ablegen, lesen und verdunsten lassen:

```python
from tools.stigmergy_api import StigmergyAPI

api = StigmergyAPI(db_path="swarm.db", agent_id="agent_A")

api.deposit("approach_refactor", strength=0.9, metadata={"result": "success"})
paths = api.sense()
best = api.get_best_path()
api.evaporate(decay_rate=0.1)
```

Das dateibasierte Schema wird automatisch initialisiert. `:memory:` wird
abgewiesen, weil ein Koordinationsspeicher mehrere Verbindungen überdauern muss.

### Parallele Claude-CLI-Aufrufe

`ClaudeRunner` verteilt unabhängige Prompts parallel über Claude Code:

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

Der Runner ist standardmäßig nur lesend (`Read`, `Glob`, `Grep`), genehmigt im
nichtinteraktiven `dontAsk`-Modus nur diese Werkzeuge vorab, sperrt konfigurierte
MCP-Werkzeuge und speichert keine Sitzungen. Ein größerer Werkzeugumfang muss
über `allowed_tools` und `available_tools` ausdrücklich freigegeben werden.

### Eigenständige Chunk-Datenbanken

Die datenbankgebundenen Tools können ihre Schemas selbst initialisieren:

```bash
python tools/translate_swarm.py --init-db
python tools/summarize_chunks.py --init-db
python tools/translate_swarm.py --limit 20 --max-budget-usd 1
python tools/summarize_chunks.py --limit 20 --max-budget-usd 1
```

Übersetzungen werden anhand von Schlüssel und Namespace statt anhand der
Antwortreihenfolge zugeordnet. Der Summarizer reserviert Chunks zeitlich begrenzt
in SQLite, damit parallele Läufe nicht doppelt API-Kosten erzeugen. Echte
API-End-to-End-Tests bleiben eine offene Release-Aufgabe.

## Benchmarks

Der enthaltene Benchmark vergleicht sequenzielle und parallele Ausführung:

```bash
PYTHONIOENCODING=utf-8 python tools/benchmark.py
PYTHONIOENCODING=utf-8 python tools/benchmark.py --compare --workers 3 \
  --limit 5 --max-budget-usd 2
```

Gemessenes Ergebnis aus `results/benchmark_20260306.json`:

| Metrik | Sequenziell | Parallel (3 Worker) | Ergebnis |
|---|---:|---:|---:|
| Gesamtzeit | 1306s | 514s | 2,54x Speedup |
| Erfolgsrate | 20/20 | 19/20 | 95% paralleler Erfolg |
| Parallele Effizienz | - | 85% | 85% |
| Gesparte Zeit | - | 792s | 61% |

## Repository-Struktur

```text
swarm_ai/
|-- tools/
|   |-- runner.py                  # Claude-CLI-Wrapper mit run_parallel()
|   |-- consensus_swarm.py         # Mehrheitsentscheid und Konfidenzberechnung
|   |-- stigmergy_api.py           # SQLite-Pheromonkoordination
|   |-- translate_swarm.py         # Paralleles Übersetzungsmuster
|   |-- summarize_chunks.py        # Paralleles Zusammenfassungsmuster
|   |-- benchmark.py               # Sequenzielles vs. paralleles Benchmarking
|   |-- swarm_haiku_3.json         # Boss-/Worker-Chain-Definition
|   `-- swarm_haiku_research.json  # Spezialisten-Research-Chain
|-- konzepte/                      # Deutsche Designdokumente
|-- experiments/                   # Experimentelle Prototypen
|-- results/                       # Benchmark-Snapshots
`-- tests/                         # Pytest-Suite
```

## Projektstatus

swarm-ai ist öffentlich und als experimentelles Toolkit nutzbar. Die Kernmodule besitzen eine lokale Testsuite; einige Konzept- und Experimentdateien referenzieren weiterhin BACH, weil sie die Herkunft der Muster dokumentieren. Für produktive Nutzung sollten die Module unter `tools/` und die getesteten Python-APIs als Einstieg dienen.

Historische Launcher unter `experiments/` brechen ohne ausdrücklichen Test- oder
Vollmodus, `SWARM_ENABLE_LEGACY_EXPERIMENTS=I_UNDERSTAND`, ein geprüftes Ziel,
ein Pro-Agent-Budget und ein Gesamtbudget ab. Schreibfähige Dungeon- und
Maintenance-Experimente verlangen zusätzlich einen isolierten Fixture-Marker.
Sie laufen im Claude-Safe-Mode mit fester Werkzeugfreigabe und gesperrtem MCP;
Benutzer-Memory-Dateien werden nicht verändert.

Aktuelle Prüfung:

- 166 lokale Tests auf der Review-Baseline vom 15.07.2026 grün.
- Ruff, `compileall`, ein Bandit-Gate für hohe Schweregrade und gepinnte Linux-/Windows-/macOS-Actions sind aktiviert.
- MIT-lizenziert.
- Noch kein PyPI-Release.
- Keine grafische Oberfläche und keine gehostete Landing-Page.

## Verwandte ellmos-Projekte

- [BACH](https://github.com/ellmos-ai/bach): vollständiges textbasiertes OS für LLM-Agenten.
- [USMC](https://github.com/ellmos-ai/usmc): lokaler SQLite-Memory-Baustein für LLM-Agenten.
- [Rinnsal](https://github.com/ellmos-ai/rinnsal): leichte LLM-Agenten-Infrastruktur.
- [clutch](https://github.com/ellmos-ai/clutch): providerneutrales Routing für Einzelaufgaben.
- [MarbleRun](https://github.com/ellmos-ai/MarbleRun): Chain-Ausführung für sequenzielle Agenten-Loops.

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md). Sinnvolle Beiträge sind Standalone-Bereinigung der Muster, End-to-End-Beispiele, reproduzierbare Benchmarks und klarere Chain-Definitionen.

## Lizenz

[MIT](LICENSE) - Copyright 2026 Lukas Geiger
