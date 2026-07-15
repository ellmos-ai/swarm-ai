# TODO - swarm-ai

Stand: 2026-07-15 (Fremdvorarbeiten gegen Remote-Baseline zertifiziert)

Dieses TODO ist der öffentliche, releasefähige Aufgaben-Einstieg für `swarm-ai`.
Interne oder historische Arbeitsnotizen bleiben außerhalb des Release-Pfads.

## STATUS

| Category | Status | Hinweis |
|---|---|---|
| README | PASS | Englische README vorhanden; deutsche README ist ergänzend. |
| Lizenz | PASS | MIT-Lizenz vorhanden. |
| Tests | PASS | Aktuelle Remote-Baseline mit 99 Tests grün. |
| Secrets | PASS | Keine getrackten `.env`- oder Datenbankdateien sichtbar. |
| `.gitignore` | PASS | Python-, Secret-, Datenbank- und lokale Datenmuster abgedeckt. |
| BACH-Entkopplung | PASS | Getestete `tools/`-Module sind standalone; Konzepttexte dürfen Ursprungskontext nennen. |
| End-to-End-API-Tests | OFFEN | Echte API-Läufe für `summarize_chunks.py` und `translate_swarm.py` stehen noch aus. |
| Paketierung | OFFEN | Noch kein PyPI-Release und keine stabile Package-Metadatenpflege. |

## Offene Aufgaben

- [ ] Echte API-End-to-End-Tests für `summarize_chunks.py` und `translate_swarm.py` planen, ohne Testkosten oder Credentials in CI zu erzwingen.
- [ ] Entscheiden, ob `hierarchy.py` und `specialist.py` als eigenständige Module aus BACH portiert werden sollen oder bewusst Konzeptbestand bleiben.
- [ ] PyPI-/Package-Strategie klären: Paketname, Entry Points, Versionierung und Release-Checkliste.
- [ ] Benchmark-Reproduzierbarkeit schärfen: Modell, Datum, Umgebung und Kostenannahmen pro Ergebnis dokumentieren.
- [ ] Historische Konzept- und Experimentdateien bei Gelegenheit auf aktuelle Pattern-Namen prüfen.

## Erledigt

- [x] Standalone-Import-Bug in `tools/benchmark.py` behoben.
- [x] Kernmodule durch lokale Unit-Tests abgesichert. (Aktuelle Remote-Baseline 2026-07-15: `pytest -q`, 99 Tests grün.)
- [x] Release-Gate-Dokument für den Public-Readiness-Stand angelegt.

## Audit 2026-06-12

Vollaudit (Doku, `tools/`, `tests/`, `experiments/`, `konzepte/`, `results/`, CI, Git-Status).
Testlauf verifiziert: 98 Tests grün in 32s. Repo ist public (`ellmos-ai/swarm-ai`).

### Fixes

- [ ] **(hoch) Persönliche Pfade in öffentlich getrackten Experiment-Dateien entfernen.**
  `experiments/dungeon/elephant_path_treasure_hunt.py:47` und
  `experiments/dungeon/elephant_path_treasure_hunt_live.py:52` enthalten hartcodiert
  einen fest verdrahteten lokalen Beispielpfad (`TARGET_PATH`). Beide Dateien sind in
  `git ls-files` enthalten, das Repo ist public. Widerspricht RELEASE_GATE.md-Punkt
  „No personal paths in source code" — der Check von 2026-03-15 prüfte nur `tools/*.py`.
  Lösung: CLI-Argument/Env-Variable statt Konstante; danach RELEASE_GATE.md-Eintrag korrigieren.
  Achtung: Pfad bleibt in der Git-Historie — bewerten, ob das akzeptabel ist.
- [ ] **(mittel) `--source`-Flag in `tools/translate_swarm.py` ist funktionslos.**
  `get_missing_translations()` (Zeile 119–155) hardcodet `t1.language = 'de'`;
  `run_swarm()` reicht `source_lang` nicht in die Query durch (Zeile 283–303, CLI Zeile 448).
  Entweder Flag entfernen oder Quellsprache tatsächlich parametrisieren.
- [ ] **(mittel) Stigmergy-Schema-Init fehlt — README-Quickstart scheitert still.**
  `tools/stigmergy_init.py` enthält nur einen 3-Zeilen-Kommentar (offenbar verirrtes
  `__init__.py`-Fragment), keine Schema-Erstellung. `StigmergyAPI(db_path="swarm.db")` aus dem
  README-Beispiel liefert auf einer frischen DB still `False`/leere Listen, weil die Tabelle
  `shared_memory_working` fehlt (CREATE TABLE existiert nur in `tests/conftest.py:27–41`).
  Lösung: `init_schema()`-Funktion in `stigmergy_api.py` oder echtes Init-Script;
  `stigmergy_init.py` aufräumen oder löschen.
- [ ] **(niedrig) Veralteter Modul-Header in `tools/runner.py:1–5`:** Docstring nennt noch
  `llmauto.core.runner` statt `tools.runner`.
- [ ] **(niedrig) Ungenutzte Imports in `tools/consensus_swarm.py`:** `threading` (Zeile 30)
  und `Path` (Zeile 33) werden nicht verwendet.
- [ ] **(niedrig) `requests>=2.31.0` in `requirements.txt` wird nirgends importiert** —
  entfernen (Grep über das gesamte Repo: kein Treffer).
- [ ] **(niedrig) Interne Referenzen in öffentlichen Docstrings bereinigen:**
  `tools/translate_swarm.py:5,10` (SQ062, `.SOFTWARE/_LANG/LANGUAGE_CODES.md`) und
  `tools/summarize_chunks.py:5` (SQ047) referenzieren interne BACH-Task-IDs und private Pfade.
- [ ] **(niedrig) `--dangerously-skip-permissions` in Dungeon-Experimenten**
  (`elephant_path_treasure_hunt.py:302`, `_live.py:283`): deutlichen Warnhinweis in
  `experiments/dungeon/README.md` ergänzen (steht dort bisher nicht explizit).

### Upgrades

- [ ] **(mittel) Modell-IDs und Preise aktualisieren/konfigurierbar machen.**
  Hardcodiert: `claude-haiku-4-5-20251001` (consensus_swarm.py:44, translate_swarm.py:49,
  summarize_chunks.py:42), `claude-sonnet-4-20250514` (summarize_chunks.py:43),
  `claude-sonnet-4-6` (runner.py:17, swarm_haiku_3.json, swarm_haiku_research.json).
  Kostenkommentar „Stand 2025" (summarize_chunks.py:46). `consensus_swarm.py` hat kein
  `--model`-Flag. Lösung: Modell via CLI-Flag/Env (`SWARM_MODEL`) überschreibbar machen,
  Preise zentralisieren.
- [ ] **(mittel) Standalone-Schema-Initialisierung für alle DB-gebundenen Tools.**
  `translate_swarm.py` setzt `languages_translations`, `summarize_chunks.py` setzt
  `document_chunks` + `parallel_chunks_runs`, `stigmergy_api.py` setzt `shared_memory_working`
  voraus — alles BACH-Schema, kein CREATE TABLE im Repo, `data/` existiert nicht
  (gitignored). Ohne vorhandene DB: Exit bzw. stilles Scheitern. Ein `tools/init_db.py`
  (oder `--init-db`-Flag) würde die Tools erst wirklich standalone machen und den
  RELEASE_GATE-Punkt „No BACH-specific database dependencies" inhaltlich einlösen.
- [ ] **(mittel) RELEASE_GATE letzter offener Punkt:** End-to-end-Lauf `summarize_chunks.py`
  (und `translate_swarm.py`) mit echtem API-Call — deckt sich mit bestehendem TODO-Punkt oben.
- [ ] **(niedrig) Test-Abdeckung erweitern:** `tools/benchmark.py` ist nur per Import getestet
  (`tests/test_imports.py:43–46`); keine Unit-Tests für Task-Katalog, `--compare`-Logik und
  JSON-Export. `experiments/dungeon/*` ist komplett ungetestet (als Experiment vertretbar,
  dann aber in CI-Scope-Doku so benennen).
- [ ] **(niedrig) `anthropic>=0.39.0` Versionsuntergrenze prüfen/anheben** (SDK-Drift seit
  Pinning; bei Gelegenheit gegen aktuelle SDK-Version testen).
- [ ] **(niedrig) `pyproject.toml` anlegen** sobald die PyPI-Strategie (offener TODO-Punkt)
  entschieden ist — derzeit existieren keinerlei Package-Metadaten.

### Änderungen

- [ ] **(hoch) `AUFGABEN.txt` und `TODO.md` konsolidieren.** `AUFGABEN.txt` (intern,
  gitignored, Stand 2026-05-11) trägt noch Status „ZURÜCKGESTELLT — Keine Veröffentlichung
  bis Konzept geprüft", während RELEASE_GATE.md „READY 9/10, Gate freigegeben" meldet und
  das Repo bereits public ist. Offene AUFGABEN-Punkte 1 (Konzept-Review/Naming), 3
  (hierarchy.py/specialist.py portieren), 4 (stigmergy entkoppeln) und 6 (Muster umbenennen:
  Delegator-Control etc.) entweder in dieses TODO überführen oder explizit als verworfen
  markieren; `AUFGABEN.txt` danach archivieren. Punkt 6 kollidiert inzwischen mit den im
  README etablierten öffentlichen Pattern-Namen.
- [ ] **(mittel) `TODO.md` und `.gitignore`-Änderung committen.** `TODO.md` deklariert sich
  als „öffentlicher, releasefähiger Aufgaben-Einstieg", ist aber untracked (`git status: ??`);
  die `.gitignore`-Erweiterung (`*.pyc`, `.env.*`, `data/`) ist uncommitted (`M`).
- [ ] **(mittel) Verhältnis zu Parallel-Implementierungen dokumentieren.** Dieselben 5 Muster
  existieren dreifach: (1) dieses Toolkit, (2) Skill `swarm-operations`
  (`~/.claude/skills/swarm-operations/SKILL.md`, v1.0.0, `bach_origin: true`, Stand
  2026-03-12), (3) MCP-Tools `hb_swarm_consensus/hierarchy/parallel/stigmergy` in
  ellmos-homebase. Quelle der Wahrheit festlegen (Empfehlung: swarm-ai = Code-Referenz,
  Skill = Prozess-Anleitung, hb_swarm_* = Runtime) und Querverweise in README/konzepte
  ergänzen, damit Weiterentwicklungen nicht divergieren.
- [ ] **(niedrig) `README/`-Ordner umbenennen.** Ein Ordner namens `README` (enthält nur
  `assets/swarm-patterns.svg`) neben `README.md`/`README_de.md` ist verwirrend.
  In `assets/` o. ä. umbenennen; Links anpassen in `README.md:16`, `README_de.md:16`,
  `llms.txt:38`. Inhaltlich sind README.md/README_de.md saubere Übersetzungen voneinander —
  keine Drift festgestellt.
- [ ] **(niedrig) `konzepte/trampelpfadanalyse.md` (16 KB) vs. `.txt` (8 KB) Doppelung:**
  .txt als Rohfassung kennzeichnen oder entfernen.
- [ ] **(niedrig) `results/`:** nur ein Snapshot (`benchmark_20260306.json`), kein
  Aufräumbedarf; Umgebungs-Metadaten (OS, CLI-Version, Worker) fehlen im Snapshot —
  gehört zum bestehenden TODO-Punkt „Benchmark-Reproduzierbarkeit".
- [ ] **(niedrig) Pipeline-Doku korrigieren (außerhalb des Repos):**
  `.TOPICS/.AI/CLAUDE.md` listet swarm_ai unter `.OS/`, tatsächlich liegt es unter
  `.MODULES/swarm_ai`.
