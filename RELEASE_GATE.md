# Release Gate - Public Experimental Toolkit

**Status:** CORE GATES PASS / EXTERNAL API E2E OPEN

Das Repository ist bereits öffentlich. Dieses Gate beschreibt daher keine
Sichtbarkeitsfreigabe, sondern den nachweisbaren Stand des experimentellen Toolkits.

## Verifizierte Gates (2026-07-15)

- [x] `PYTHONIOENCODING=utf-8 python -m pytest -q` → **166 passed**.
- [x] `python -m ruff check tools tests` → keine Befunde.
- [x] `python -m compileall -q tools tests experiments` → erfolgreich.
- [x] Bandit-Scan der produktiven Tools → keine High-Severity-Befunde.
- [x] Keine echten API-Keys oder getrackten Datenbanken.
- [x] Keine persönlichen Zielpfade und kein
  `--dangerously-skip-permissions` in ausführbaren Python-Quellen.
- [x] Standalone-Schema-Initialisierung für alle drei DB-gebundenen Tools.
- [x] Historische, schreibfähige Experimente sind standardmäßig gesperrt und
  verlangen expliziten Modus, Opt-in, Pro-Agent-/Gesamtbudget sowie validierte
  Ziele/Fixtures; Benutzer-Memory wird nicht verändert.
- [x] GitHub Actions sind SHA-gepinnt; Windows/Linux/macOS-Matrix, CodeQL,
  High-Severity-Bandit-Gate und Dependabot sind konfiguriert.
- [x] MIT-Lizenz, Security Policy, englische und deutsche README vorhanden.

## Offenes externes Gate

- [ ] Je ein echter, kostenbewusst freigegebener API-/DB-End-to-End-Lauf für
  `consensus_swarm.py`, `summarize_chunks.py` und `translate_swarm.py`.

Bis dieses Gate geschlossen ist, bleibt die korrekte Bezeichnung
**public experimental**, nicht production-ready. Gemockte API-Tests sichern die
lokale Logik, können aber Provider- oder SDK-Drift nicht vollständig beweisen.
