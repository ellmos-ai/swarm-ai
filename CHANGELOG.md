# Changelog

## Unreleased

### Added

- `konzepte/matruschka-verfahren.md` (Version 1.3): Kernregel 4 „Exklusive
  Schreibbereiche bei paralleler Arbeit" — disjunkte Schreibbereiche oder eigene
  Kopie für Helfer, Schreibverbote immer mit Begründung, und Messen zählt als
  Nutzung des Bereichs. Mit Belegfall vom 2026-08-02. [C 2026-08-02]
- Alt-Datenbanken: `summarize_chunks.py --init-db` übernimmt Laufprotokolle aus
  der abgelösten Tabelle `epstein_runs` idempotent nach `parallel_chunks_runs`
  (`initialize_schema(migrate_legacy=True)` liefert die Anzahl übernommener
  Läufe). **Gewählt wurde die Datenmigration statt eines Kompatibilitäts-Views:**
  Der kanonische Tabellenname bleibt `parallel_chunks_runs` (umbenannt am
  2026-06-17), und ein View könnte eine in der Alt-Datenbank real existierende
  Tabelle gleichen Namens ohnehin nicht überlagern. Ohne Migration legte
  `initialize_schema` daneben eine leere Tabelle an — die Altläufe blieben auf
  der Platte, wären aber für jede Abfrage unsichtbar. Die Legacy-Tabelle wird
  nicht verändert und nicht gelöscht; der Abgleich zählt je
  (`started_at`, `llm_model`)-Gruppe, damit auch zwei echte Altläufe mit
  identischem Zeitstempel und Modell erhalten bleiben. [C 2026-08-02]
- `konzepte/schwarm-operationen.md`: frühere Bezeichnung des Musters
  („Epstein-Muster", bis Juni 2026) als Herkunftsnotiz aufgenommen — der Name
  wird nirgends mehr ausgewertet, bleibt aber dokumentiert, damit ältere Notizen
  und Datenbanken zuordenbar sind. [C 2026-08-02]
- `konzepte/matruschka-verfahren.md`: Matruschka-Verfahren (Synonym:
  Subsidiaritätsprinzip) als Querschnittsverfahren für kaskadierte
  Helfer-Delegation mit Aktivitäts-Limits je Ebene (Limits = gleichzeitige
  Aktivität statt Bestand; Vorhalten + kontextbezogenes Wiederverwenden;
  Delegation nur abwärts). Verweis in `konzepte/schwarm-operationen.md`
  (Version 1.2). [C 2026-08-01]

### Fixed

- Technical Hygiene & Maintenance: fixed 38 ruff lint issues across experiment scripts (unused imports, extraneous f-strings, boolean/None comparisons), added noqa E402 import guards in dungeon_template.py, updated llms.txt Last-checked timestamp to 2026-08-04 and verified test suite count (182 passed, 1 skipped). [G 2026-08-04]
- Handled optional COMA provider test dependency gracefully with `pytest.importorskip` in `test_runner.py`. [G 2026-07-30]
- Restored the empirically supported Anthropic SDK floor to 0.40.0 and added
  minimum/latest SDK contract tests across Python 3.10 and 3.13.
- Installed the declared COMA provider dependency in full CI so provider
  runner tests execute instead of failing during import.
- Added a clear `ValueError` for `ClaudeRunner.run_parallel()` dict items that omit the required `prompt` key.
- Made `ClaudeRunner` read-only by default and restrictive even with an empty tool set.
- Corrected consensus confidence under partial failures and validated classification/boolean responses.
- Made consensus pricing model-aware instead of silently applying Haiku prices to overrides.
- Added atomic standalone stigmergy storage and fixed `evaporate(0)` deleting a record.
- Implemented translation source-language handling, identity-based result mapping, and serialized writes.
- Added standalone DB initialization, limits, and cross-process claims for chunk summarization.
- Added mandatory live limits and conservative cost ceilings for benchmarks, translation, and summarization.
- Cost ceilings include every configured retry, not only the first API attempt.
- Added pre-API translation claims to prevent concurrent runs paying for the same rows.
- Made team resource claims atomic across processes and attendance lossless.
- Serialized claim/release transitions and hashed attendance tokens to prevent path escape and release races.
- Made stigmergy evaporation reserve its SQLite writer transaction before reading.
- Corrected the benchmark working directory and duplicate dungeon result keys.
- Made historical experiment launchers fail closed and protected dungeon fixtures from accidental overwrite.
- Separated Claude CLI tool visibility from pre-approval, denied MCP tools by default, and disabled session persistence.
- Required finite live budgets for consensus and rejected NaN/infinite caps across every paid tool.
- Counted exact JSON escaping and translation identities in conservative cost bounds.
- Closed every SQLite handle, rejected concurrent summary overwrites, and preserved translation placeholders.
- Made consensus ties explicit instead of selecting a completion-order winner.
- Kept expired team claims non-stealable and removed partial claim files after failed writes.
- Made legacy stigmergy migration select the newest valid duplicate deterministically.
- Removed user-memory mutation from historical experiments and required strict modes, fixture markers, and total-run budgets.
- Restricted write-capable experiments to pre-approved built-in file tools in Claude safe mode.

### Security

- Removed legacy permission bypass flags and hardcoded personal targets from executable experiments.
- Pinned GitHub Actions by commit SHA and added CodeQL, Dependabot, Bandit, and `SECURITY.md`.

### Documentation

- Synchronized `llms.txt`, `RELEASE_GATE.md`, and test suite verification to 2026-08-03 (172 passed, 1 skipped). Integrated open-bricks ecosystem & Pytest badges and GFM Callout box for `llms.txt` in English & German READMEs. Fixed unused `import time` in `tools/render_previews.py` (ruff 100% clean). [G 2026-08-03]
- Synchronized `llms.txt`, `RELEASE_GATE.md`, and test suite verification to 2026-07-30 (170 passed, 4 skipped for optional COMA backend). [G 2026-07-30]
- Synchronized `llms.txt`, `RELEASE_GATE.md`, and verification metadata to the 2026-07-27 test run (167 passed).
- Added PEP 621 compliant `pyproject.toml` with pytest `pythonpath` and `testpaths` configuration.
- Synchronized `llms.txt`, `RELEASE_GATE.md`, and verification metadata to the 2026-07-26 test run (167 passed).
- Synchronized `llms.txt`, `RELEASE_GATE.md`, and verification metadata to the 2026-07-25 test run (166 passed).
- Added `konzepte/team-lock-verfahren.md` and README references for the coordination guardrail used during shared-file swarm work.
- Synchronized release-gate and `llms.txt` verification metadata to the 2026-07-10 test run.
- Updated verification metadata to the 2026-07-15 FABLE review (166 tests).
- Added clearer discovery context and search phrases to `README.md` and `README_de.md`.
- Standardized `llms.txt` with `Last-checked`, audience, search phrases, keywords, and disambiguation notes.
