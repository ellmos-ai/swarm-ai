# Changelog

## Unreleased

### Fixed

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

- Added `konzepte/team-lock-verfahren.md` and README references for the coordination guardrail used during shared-file swarm work.
- Synchronized release-gate and `llms.txt` verification metadata to the 2026-07-10 test run.
- Updated verification metadata to the 2026-07-15 FABLE review (166 tests).
- Added clearer discovery context and search phrases to `README.md` and `README_de.md`.
- Standardized `llms.txt` with `Last-checked`, audience, search phrases, keywords, and disambiguation notes.
