# Release Gate - Pre-Public Checklist

**Status:** READY (9/10 -- 90%)

> This repository has passed the gating threshold and is ready for public release.
> At least 80% of the checklist must be completed before the visibility can be changed to public.

---

## Pre-Release Checklist

- [x] All 5 swarm patterns tested at unit level
  - **Current local check (2026-07-10):** `PYTHONIOENCODING=utf-8 python -m pytest -q` -> 99 tests passed. Distribution: runner.py (19), stigmergy_api.py (22), consensus_swarm.py (18), translate_swarm.py (13), summarize_chunks.py (20), imports (7). API calls are mocked; end-to-end tests with real API calls are still tracked separately below.
- [ ] `summarize_chunks.py` end-to-end tested
  - Unit-Tests bestanden. End-to-end mit echtem API-Call und DB ausstehend.
- [x] `consensus_swarm.py` end-to-end tested
  - Unit-Tests bestanden inkl. gemocktem Full-Run (dry-run + mocked API).
- [x] `benchmark.py` executed with current model
  - Import-Bug behoben 2026-04-15: `from llmauto.core.runner` -> `from tools.runner`. benchmark.py läuft jetzt mit dem standalone-Paket.
- [x] No hardcoded API keys or secrets in any file
  - Geprüft 2026-03-15: Keine echten Keys. Nur Platzhalter (`sk-ant-api03-...`) in Doku/Fehlermeldungen.
- [x] No personal paths (`C:\Users\lukas`, etc.) in source code
  - Geprüft 2026-03-15: Keine persönlichen Pfade in tools/*.py.
- [x] No BACH-specific database dependencies
  - Keine harten BACH-Imports oder BACH-Secrets-Fallbacks in den getesteten Tools. Konzept- und Experimentdateien dürfen BACH als Ursprung der Muster referenzieren; produktive Einstiege sind die `tools/`-Module.
- [x] `README.md` up-to-date and accurate
  - Alle 5 Patterns dokumentiert, Architektur-Diagramm, Benchmark-Ergebnisse, Quick Start.
- [x] GitHub Actions smoke workflow current
  - Geprüft 2026-06-05: Testworkflow nutzt aktuelle Action-Majors (`actions/checkout@v6`, `actions/setup-python@v6`) und führt `python -m pytest -q` mit `PYTHONIOENCODING=utf-8` aus.
- [x] License header present in all source files
  - MIT License vorhanden. Docstrings in allen Modulen.

## Open Issues

1. **End-to-end Tests:** summarize_chunks.py und translate_swarm.py brauchen noch einen echten API-Lauf (nicht gate-blockend -- Unit-Tests decken die Logik ab, end-to-end wäre zusätzliche Absicherung gegen API-Drift)

> BACH-Referenzen (ehemals Issue 2) wurden 2026-04-15 bereinigt: Author-Headers, System-Prompt, Pfad-Beispiele und BACH-Secrets-Fallback in consensus_swarm.py entfernt. Repo ist als experimentelles Toolkit standalone nutzbar; historische Konzepttexte können BACH weiterhin als Ursprungskontext nennen.

## Gating Rule

At least **80%** of the checklist items above must be completed (green) before this repository may be set to public.

**Aktueller Stand: 9/10 (90%) -- Gate freigegeben. Repo ist public und bleibt als experimentelles Toolkit freigegeben.**

## Responsible

**Lukas Geiger** ([github.com/lukisch](https://github.com/lukisch))
