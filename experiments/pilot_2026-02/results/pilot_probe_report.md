# LLM-Navigationsexperiment: Pilot-Proben Ergebnisbericht

**Datum:** 2026-02-15
**Experiment:** 10 Sub-Agenten erkunden das BACH-Dateisystem
**Transkript-ID:** ed9e7375-ff86-437f-9cb1-33fb25854ca2

---

## Zusammenfassung

### Gesamtstatistik
- **Anzahl Proben:** 10
- **Erfolgsquote:** 100% (10/10)
- **Gesamt Tool-Aufrufe:** 205
- **Gesamt besuchte Pfade:** 182
- **Modelle:** 5x Haiku, 5x Sonnet

### Erfolgsrate nach Modell
- **Haiku:** 5/5 (100%)
- **Sonnet:** 5/5 (100%)

---

## Einzelne Proben

### 1. af22b5f - Task erstellen (Haiku)

**Auftrag:** Wie erstellt man einen Task in BACH?

**Ergebnis:** Erfolgreich

**Navigation:**
- Suchte systematisch nach BACH-System
- Fand Task-relevante Dateien via Grep-Pattern `task.*create`
- Las Hauptdateien: `bach.py`, `hub/task.py`, `core/db.py`
- Suchte nach Datenbank-Schema für Task-Struktur

**Statistik:**
- 18 besuchte Pfade
- 22 Tool-Aufrufe
- 2 Fehler

**Kernfunde:**
- `<USER_HOME>/OneDrive/.AI/BACH/system/bach.py`
- `<USER_HOME>/OneDrive/.AI/BACH/system/hub/task.py`
- `<USER_HOME>/OneDrive/.AI/BACH/system/core/db.py`

---

### 2. a79cfdb - BACH starten (Sonnet)

**Auftrag:** Wie startet man BACH?

**Ergebnis:** Erfolgreich

**Navigation:**
- Begann mit breiten Glob-Patterns (Timeout)
- Verfeinerte Suche auf OneDrive-Verzeichnis
- Fand Start-Verzeichnis und Dokumentation
- Las Launcher-Skripte und API-Dateien

**Statistik:**
- 18 besuchte Pfade
- 20 Tool-Aufrufe
- 4 Fehler

**Kernfunde:**
- `<USER_HOME>/OneDrive/.AI/BACH/README.md`
- `<USER_HOME>/OneDrive/.AI/BACH/start/README.md`
- `<USER_HOME>/OneDrive/.AI/BACH/start/BACH_Launcher.bat`
- `<USER_HOME>/OneDrive/.AI/BACH/system/bach_api.py`

---

### 3. ae480d9 - Steuerbelege finden (Haiku)

**Auftrag:** Wo sind die Steuerbelege in BACH?

**Ergebnis:** Erfolgreich

**Navigation:**
- Systematische Exploration des BACH-Systems
- Suchte mit Mustern: `*steuer*`, `*belege*`, `*tax*`
- Fand spezialisierte Steuer-Module
- Entdeckte Expert-Agent für Steuerbelege

**Statistik:**
- 27 besuchte Pfade
- 28 Tool-Aufrufe
- 2 Fehler

**Kernfunde:**
- `<USER_HOME>/OneDrive/.AI/BACH/system/hub/steuer.py`
- `<USER_HOME>/OneDrive/.AI/BACH/system/agents/_experts/steuer/steuer-beleg-scan.md`
- `<USER_HOME>/OneDrive/.AI/BACH/system/hub/bach_paths.py`

---

### 4. a233c53 - Offene Tasks (Sonnet)

**Auftrag:** Welche offenen Tasks gibt es?

**Ergebnis:** Erfolgreich

**Navigation:**
- Suchte nach Task-Dateien (`*task*.md`, `*todo*.md`, `TODO*`)
- Fand Task-Queue-JSON
- Untersuchte Task-Management-Modul
- Suchte in data/ati/ nach weiteren Task-Quellen

**Statistik:**
- 12 besuchte Pfade
- 26 Tool-Aufrufe
- 2 Fehler

**Kernfunde:**
- `<USER_HOME>/OneDrive/.AI/BACH/system/data/quick_tasks_queue.json`
- `<USER_HOME>/OneDrive/.AI/BACH/system/hub/task.py`

---

### 5. a76d7f1 - Python-Tools finden (Haiku)

**Auftrag:** Welche Python-Tools gibt es in BACH?

**Ergebnis:** Erfolgreich

**Navigation:**
- Fand BACH-System schnell
- Nutzte `find` um alle .py-Dateien zu lokalisieren
- Entdeckte tools/-Verzeichnis mit 60+ Python-Dateien
- Systematische Durchsuchung aller Verzeichnisse

**Statistik:**
- 10 besuchte Pfade
- 11 Tool-Aufrufe
- 3 Fehler

**Kernfunde:**
- `<USER_HOME>/OneDrive/.AI/BACH/system/tools/` (60+ .py-Dateien)

**Besonderheit:** Minimale Pfad-Anzahl bei hoher Effizienz

---

### 6. ae2fe98 - Wiki-Artikel schreiben (Sonnet)

**Auftrag:** Schreibe einen Wiki-Artikel über Docker

**Ergebnis:** Erfolgreich

**Navigation:**
- Suchte nach Wiki-Struktur in BACH
- Fand Wiki-Verzeichnis und Konventionen
- Las bestehende Artikel als Vorlagen
- Untersuchte DevOps- und Deployment-Bereiche

**Statistik:**
- 19 besuchte Pfade
- 19 Tool-Aufrufe
- 4 Fehler

**Kernfunde:**
- `<USER_HOME>/OneDrive/.AI/BACH/system/wiki/informatik/devops/README.txt`
- `<USER_HOME>/OneDrive/.AI/BACH/system/wiki/informatik/README.txt`
- `<USER_HOME>/OneDrive/.AI/BACH/system/wiki/webapps/deployment/README.txt`
- `<USER_HOME>/OneDrive/.AI/BACH/system/wiki/wiki_konventionen.txt`
- `<USER_HOME>/OneDrive/.AI/BACH/system/wiki/n8n.txt`

---

### 7. a877330 - Logs lesen (Haiku)

**Auftrag:** Wo sind die BACH-Logs?

**Ergebnis:** Erfolgreich

**Navigation:**
- Suchte nach .log-Dateien und logs/-Verzeichnissen
- Fand leeres logs/-Verzeichnis
- Untersuchte bach_paths.py für Log-Konfiguration
- Las bach_api.py für Logging-Infrastruktur

**Statistik:**
- 19 besuchte Pfade
- 20 Tool-Aufrufe
- 2 Fehler

**Kernfunde:**
- `<USER_HOME>/OneDrive/.AI/BACH/system/hub/bach_paths.py`
- `<USER_HOME>/OneDrive/.AI/BACH/system/bach_api.py`
- `<USER_HOME>\.claude\projects\C--Users-User\memory\MEMORY.md` (als Orientierung)

**Besonderheit:** Nutzte MEMORY.md als Einstiegspunkt

---

### 8. a1c18c2 - Agenten auflisten (Sonnet)

**Auftrag:** Welche Agenten gibt es in BACH?

**Ergebnis:** Erfolgreich

**Navigation:**
- Systematische Suche nach BACH-System
- Fand agents/-Verzeichnis
- Las README und SKILL.md-Dateien der Agenten
- Untersuchte sowohl Boss-Agenten als auch Experten

**Statistik:**
- 20 besuchte Pfade
- 20 Tool-Aufrufe
- 4 Fehler

**Kernfunde:**
- `<USER_HOME>/OneDrive/.AI/BACH/system/agents/README.md`
- `<USER_HOME>/OneDrive/.AI/BACH/system/agents/ati/SKILL.md`
- `<USER_HOME>/OneDrive/.AI/BACH/system/agents/entwickler/SKILL.md`
- `<USER_HOME>/OneDrive/.AI/BACH/system/agents/production/SKILL.md`
- `<USER_HOME>/OneDrive/.AI/BACH/system/agents/reflection/SKILL.md`

---

### 9. adff5c1 - DB exportieren (Haiku)

**Auftrag:** Wie exportiert man die BACH-Datenbank?

**Ergebnis:** Erfolgreich

**Navigation:**
- Suchte nach db/- und system/system/exports/-Verzeichnissen
- Fand Schema-SQL-Dateien
- Entdeckte exporter.py und dump_schema.py
- Untersuchte Hub-Verzeichnis für Registry

**Statistik:**
- 14 besuchte Pfade
- 14 Tool-Aufrufe
- 2 Fehler

**Kernfunde:**
- `<USER_HOME>/OneDrive/.AI/BACH/system/data/schema_bach.sql`
- `<USER_HOME>/OneDrive/.AI/BACH/system/tools/generators/exporter.py`
- `<USER_HOME>/OneDrive/.AI/BACH/system/data/dump_schema.py`

---

### 10. a743337 - System-Status (Sonnet)

**Auftrag:** Was ist der System-Status von BACH?

**Ergebnis:** Erfolgreich

**Navigation:**
- Breite Glob-Suche mit Pattern-Verfeinerung
- Systematisches Durchsuchen von Hub-Modulen
- Fand Status-Handler und Hauptdateien
- Las bach_paths.py für Systemstruktur

**Statistik:**
- 25 besuchte Pfade
- 25 Tool-Aufrufe
- 11 Fehler

**Kernfunde:**
- `<USER_HOME>/OneDrive/.AI/BACH/system/hub/__init__.py`
- `<USER_HOME>/OneDrive/.AI/BACH/system/bach.py`
- `<USER_HOME>/OneDrive/.AI/BACH/system/bach_api.py`
- `<USER_HOME>/OneDrive/.AI/BACH/system/hub/bach_paths.py`
- `<USER_HOME>/OneDrive/.AI/BACH/system/data/bach.db`

---

## Analyse

### Navigationsmuster

#### Erfolgreiche Strategien:
1. **Grep-Pattern für Funktionalität** (z.B. `task.*create`) - Sehr effektiv
2. **MEMORY.md als Orientierung** - Einige Agenten nutzten dies als Einstieg
3. **Systematisches ls-Traversieren** - Von OneDrive -> projects -> BACH -> system
4. **find mit Mustern** - Gut für spezifische Dateitypen (.py, .db, etc.)
5. **README-Dateien** - Wichtige Ankerpunkte für Verzeichnisse

#### Probleme:
1. **Zu breite Glob-Patterns** - Timeouts bei `**/BACH*/**` von Root
2. **Windows-Pfad-Escaping** - `projects` vs `KI\&AI` verursachte gelegentlich Probleme
3. **Leere Verzeichnisse** - logs/-Verzeichnis war leer, verwirrt manche Agenten

### Modell-Vergleich

**Haiku (5 Proben):**
- Durchschnitt: 17.6 besuchte Pfade, 19 Tool-Aufrufe
- Eher direkte, fokussierte Navigation
- Weniger Fehler (durchschnittlich 2.2)
- Schnellere Pfadfindung

**Sonnet (5 Proben):**
- Durchschnitt: 18.8 besuchte Pfade, 22 Tool-Aufrufe
- Mehr explorative Ansätze
- Etwas mehr Fehler (durchschnittlich 5.0)
- Gründlichere Untersuchung der Struktur

### Wichtigste Dateien (von Agenten am häufigsten besucht)

1. `bach_paths.py` - 4 Proben
2. `bach_api.py` - 4 Proben
3. `bach.py` - 3 Proben
4. `hub/task.py` - 2 Proben
5. SKILL.md-Dateien in agents/ - 1 Probe (aber viele davon)

### Verzeichnisstruktur-Erkenntnisse

Alle Agenten identifizierten die wichtigsten BACH-Verzeichnisse:
- `system/` - Hauptsystem
- `agents/` - Boss-Agenten (11)
- `agents/_experts/` - Domain-Experten (17)
- `tools/` - Python-Tools (60+)
- `hub/` - Registry und Pfade
- `data/` - Datenbanken, Schemas, Queues
- `wiki/` - Wissensdatenbank
- `skills/_protocols/` - Workflows/Protokolle

---

## Erkenntnisse für BACH-Verbesserungen

### 1. Navigationshilfen
- MEMORY.md ist sehr wertvoll als Einstiegspunkt
- README.md in Hauptverzeichnissen sollte vorhanden sein
- `bach_paths.py` ist ein perfektes "Inhaltsverzeichnis" für das System

### 2. Dokumentation
- SKILL.md-Format für Agenten funktioniert gut
- Wiki-Konventionen helfen bei Orientierung
- Schema-Dateien sollten prominent sein

### 3. Struktur-Optimierungen
- Leere Verzeichnisse (wie `logs/`) sollten eine README haben
- Windows-Pfade brauchen konsistentes Escaping
- Glob-Patterns sollten eingeschränkter sein (nicht von Root)

### 4. Tool-Discovery
- `tools/`-Verzeichnis ist gut strukturiert
- Python-Dateien sind einfach zu finden mit `find *.py`
- generators/, validators/, connectors/ sind klare Kategorien

---

## Fazit

Alle 10 Pilot-Proben waren erfolgreich (100% Erfolgsquote). Sowohl Haiku als auch Sonnet konnten das BACH-Dateisystem effektiv navigieren und ihre Aufträge erfüllen.

**Durchschnittliche Navigation:**
- 18.2 besuchte Pfade pro Probe
- 20.5 Tool-Aufrufe pro Probe
- 3.9 Fehler pro Probe (meist Timeouts oder Escaping-Probleme)

**Empfehlungen:**
1. MEMORY.md als Standard-Einstiegspunkt beibehalten
2. README-Dateien in allen Hauptverzeichnissen
3. bach_paths.py als "Single Source of Truth" weiter ausbauen
4. Leere Verzeichnisse mit Erklärungen versehen
5. Windows-Pfad-Konventionen dokumentieren

---

**Datei-Referenzen:**
- Rohdaten: `<USER_HOME>/OneDrive/.AI/BACH/system/data/pilot_probe_results.json`
- Zusammenfassung: `<USER_HOME>/OneDrive/.AI/BACH/system/data/pilot_probe_summary.json`
- Dieser Bericht: `<USER_HOME>/OneDrive/.AI/BACH/system/data/pilot_probe_report.md`
