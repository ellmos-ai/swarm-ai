# TODO - swarm-ai

Stand: 2026-07-15 (FABLE-Modulreview, Code- und Sicherheitsgates grün)

Dieses TODO ist der öffentliche Aufgaben-Einstieg. Historische Befunde bleiben
über Git nachvollziehbar; hier stehen nur der aktuelle Zustand und echte Restarbeit.

## Status

| Category | Status | Nachweis |
|---|---|---|
| Kernlogik | PASS | 172 Kern- plus 2 SDK-Vertragstests, `compileall`, Ruff |
| Lokale Sicherheit | PASS | Bandit ohne High-Severity-Befund; Legacy-Experimente fail-closed |
| Datenbanken | PASS | Standalone-Init für Stigmergie, Übersetzung und Summaries |
| Lieferkette | PASS | Actions SHA-gepinnt, CodeQL und Dependabot ergänzt |
| Echte API-E2E-Tests | OFFEN | Credentials und Kosten bewusst nicht in CI |
| Paketierung | VERTRAG DEFINIERT / RELEASE OFFEN | `pyproject.toml` und `PYPI_RELEASE.md`; noch kein PyPI-Upload |

## Offene Aufgaben

- [ ] Kostenbewusste, manuell freizugebende API-End-to-End-Tests für
  `consensus_swarm.py`, `summarize_chunks.py` und `translate_swarm.py`
  definieren und ausführen.
- [ ] Entscheiden, ob `hierarchy.py` und `specialist.py` als eigenständige
  Module portiert oder bewusst als Konzeptbestand geführt werden.
- [x] PyPI-Strategie klären: Paketname `ellmos-swarm-ai`, stabile Entry Points,
  PEP-440-Versionsschema und Release-Checkliste in `PYPI_RELEASE.md` definiert.
- [ ] Einen neuen kostenpflichtigen Live-Benchmark mit aktuellem Modell
  freigegeben ausführen; der kostenfreie Dry-Run mit Pricing und
  Python-/Plattform-/Repository-Export liegt in
  `results/benchmark_20260813.json`.
- [x] SDK-Untergrenze in einer eigenen Kompatibilitätsmatrix gegen aktuelle
  Anthropic-SDK-Versionen prüfen. (Erledigt 2026-07-28: `anthropic>=0.40.0`;
  CI testet Minimum und Latest auf Python 3.10/3.13. Version 0.39.0 scheitert
  mit aktuellem HTTPX bereits bei der Client-Konstruktion.)

## Im Review 2026-07-15 erledigt

- [x] Persönliche Zielpfade und Berechtigungs-Bypass aus ausführbaren Experimenten entfernt.
- [x] Legacy-Launcher mit Opt-in, Non-Root-Prüfung und Fixture-Gate abgesichert.
- [x] Dungeon-Generator vor Überschreiben nichtleerer Ziele geschützt und Restore-Pfad repariert.
- [x] `--source` in der Übersetzung durchgängig implementiert; Antworten werden
  identitätsbasiert geprüft und DB-Schreibvorgänge serialisiert.
- [x] Stigmergie auf ein automatisch initialisiertes, atomar aktualisiertes
  Standalone-Schema umgestellt; `evaporate(0)` ist ein echter No-op.
- [x] Summary-Schema-Init, CLI-Limit und exklusive Chunk-Claims ergänzt.
- [x] Konsens-Konfidenz berücksichtigt alle angefragten Agenten; ungültige
  Antworten, Response-Rate und modellabhängige Preise werden getrennt behandelt.
- [x] `ClaudeRunner` standardmäßig auf restriktive Lesetools begrenzt.
- [x] Verfügbarkeit (`--tools`) und Vorabgenehmigung (`--allowedTools`) getrennt;
  MCP und Sitzungspersistenz sind standardmäßig deaktiviert.
- [x] Nichtendliche Budgets verworfen und konservative Kostenobergrenzen um
  JSON-Escaping, Identitäten und alle Retry-Versuche ergänzt.
- [x] Historische Live-Launcher auf striktes `argparse`, Test-/Vollmodus,
  Pro-Agent- und Gesamtlaufbudget sowie Claude-Safe-Mode umgestellt.
- [x] Benutzer-Memory-Manipulation aus Experimenten entfernt; Dungeon- und
  Maintenance-Schreibläufe benötigen überprüfte Fixture-Marker.
- [x] Team-Lock-Ablauf bleibt ein Recovery-Signal und wird nicht automatisch
  gestohlen; fehlgeschlagene exklusive Writes hinterlassen keinen Claim.
- [x] Benchmark-CWD und Export-Reproduzierbarkeit korrigiert; ungenutzte
  `requests`-Abhängigkeit entfernt.
- [x] Tests von 99 auf 166 erweitert und Windows/Linux/macOS-CI gehärtet.
