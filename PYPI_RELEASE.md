# PyPI-Strategie und Release-Checkliste

## Festgelegter Paketvertrag

- **Distribution-Name:** `ellmos-swarm-ai` (der normalisierte PyPI-Name).
- **Import-Kompatibilität:** Die bestehenden Python-Imports unter `tools.*`
  bleiben erhalten; es wird kein erzwungener Namespace- oder Modulrename für
  den ersten Release eingeführt.
- **Versionsquelle:** `pyproject.toml` ist die einzige autoritative Quelle in
  `[project].version`.
- **Versionsschema:** PEP-440-kompatibles `MAJOR.MINOR.PATCH`, beginnend mit
  `0.1.0`. Neue rückwärtskompatible Funktionen erhöhen `MINOR`, reine
  Fehler-/Dokumentationskorrekturen `PATCH`, inkompatible API-Änderungen
  `MAJOR`. Vorabversionen verwenden ausschließlich PEP-440-Suffixe wie
  `0.2.0a1`, `0.2.0b1` oder `0.2.0rc1`.

## Öffentliche CLI-Entry-Points

Die Namen sind stabil und zeigen auf die vorhandenen `main()`-Funktionen:

| Befehl | Ziel |
|---|---|
| `swarm-consensus` | `tools.consensus_swarm:main` |
| `swarm-benchmark` | `tools.benchmark:main` |
| `swarm-translate` | `tools.translate_swarm:main` |
| `swarm-summarize` | `tools.summarize_chunks:main` |
| `swarm-stigmergy-init` | `tools.stigmergy_init:main` |

Die JSON-Chain-Definitionen unter `tools/*.json` werden als Package-Daten in
das Wheel aufgenommen. Datenbank-, API- und Experimentdateien sind kein
automatischer Bestandteil eines Release und müssen vor jeder Erweiterung
separat geprüft werden.

## Release-Checkliste

1. [ ] Arbeitsbaum, Remote-Stand, Lockdateien und Eigentum vor der Freigabe
   prüfen; fremde oder unbestätigte Änderungen nicht übernehmen.
2. [ ] Version in `pyproject.toml` erhöhen und Changelog/README-Status mit
   demselben Versionsstand aktualisieren.
3. [ ] In einer frischen Umgebung `python -m pip install .` ausführen und alle
   fünf Entry-Points mit `--help` bzw. einem kostenfreien Dry-Run prüfen.
4. [ ] `python -m pytest -q`, Ruff und `python -m compileall -q tools tests`
   erfolgreich ausführen.
5. [ ] `python -m build` ausführen; Wheel und Source-Archiv mit
   `python -m twine check dist/*` prüfen.
6. [ ] Wheel-Inhalt, License/README und `tools/*.json` per Archiv-Readback
   kontrollieren; keine Secrets, lokalen Pfade oder Testdaten akzeptieren.
7. [ ] Zuerst nach TestPyPI hochladen, Installierbarkeit und Entry-Points aus
   einem getrennten frischen Verzeichnis verifizieren und den Readback
   dokumentieren.
8. [ ] Erst nach ausdrücklicher Freigabe auf PyPI veröffentlichen, danach
   Versionsnummer, Hashes und installierte CLI erneut gegen PyPI lesen.
9. [ ] Git-Tag und Release-Notiz erst nach erfolgreichem Readback erstellen.

Ein PyPI-Upload ist mit diesem Vertrag noch nicht erfolgt. Kostenpflichtige
Provider-End-to-End-Tests bleiben ein getrenntes, ausdrücklich freizugebendes
Release-Gate.
