# Schwarm-Operationen Protokoll

**Version:** 1.1 | **Stand:** 2026-06-17

## Anwendungsmodi

Die 5 Grundmuster sind **Schwarmorganisation** (das WIE). Davon zu unterscheiden sind **Anwendungsmodi** (das WOFUER):

| Modus | Beschreibung | Typische Grundmuster |
|-------|-------------|---------------------|
| **Suchschwarm** | Alle Agenten suchen dasselbe Ziel | Parallel-Chunks, Stigmergy |
| **Aufgabenschwarm** | Agenten erledigen Teilaufgaben | Hierarchie, Parallel-Chunks, Stigmergy, Konsensus, Spezialist |

### Suchschwarm-Varianten

**Variante A — Echolot (Kartierung):**
Ziel: System/Terrain kartieren (z.B. Trampelpfadanalyse). Kein konkreter Schatz, sondern Heatmap der besuchten Pfade.

**Variante B — Schatzsuche (ein oder viele Schaetze):**
Ziel: spezifische Objekte finden (Dateien, Bugs, Muster, ...).
Abbruch-Kriterien (NICHT beim ersten Fund, es koennte mehrere geben):
- Zeitlimit: nach N Minuten / M Agenten-Runden
- Schatzfundrate: wenn ueber mehrere Runden kein neuer Fund -> Suche gesaettigt
- Vollstaendigkeit: wenn alle Suchbereiche abgedeckt sind

**Variante C — Single Op / Spermienprinzip (Unterform der Schatzsuche):**
Voraussetzung: Es existiert GENAU EIN Schatz.
Abbruch: sofort wenn der erste Agent findet (alle anderen stoppen).
Pflicht: Signal-Mechanismus damit alle Worker den Abbruch erkennen:
- Signal-Datei (.found im gemeinsamen Verzeichnis) — empfohlen
- Threading.Event (nur gleicher Prozess)
- Subprocess.kill (Orchestrator bricht Worker ab)
- Kill-Datei + Poll (Worker prueft .stop-Datei jede Runde)

### Trampelpfadanalyse (Suchschwarm als empirisches Instrument)

Naive LLM-Agenten erkunden ein System ohne Anleitung, ihre besuchten Pfade werden als Heatmap aufgezeichnet.
Ergebnis: Dokumentations-Blindstellen sichtbar machen — wo geht kein Agent hin?
Grossversuch-Ergebnis (100 Haiku-Sonden, $3.54): groesster Blindfleck = help/ (0/100 Besuche), 0%-Aufgabe = "neuen Skill erstellen".
Implementierung: `elephant_path_treasure_hunt.py` (Rounds-basiert v2), `*_live.py` (Continuous Flow v3 mit Leichen-System).

---

## 5 Grundmuster

Vor jedem Aufgabenschwarm mit möglicher Überschneidung gilt zusätzlich das
Team-Lock-Verfahren aus `team-lock-verfahren.md`. Es ist kein sechstes Muster,
sondern schützt gemeinsame Dateien, Tools, MCP-Sitzungen und Ergebnisartefakte
über einen projektlokalen Koordinationsraum.

### 1. Parallel-Chunks

Aufgabe -> N gleichgrosse Chunks -> N parallele Agenten -> Ergebnisse zusammenfuehren

**Einsatz:** Uebersetzungen, Code-Review, Dokumentation
**Optimale Chunk-Groesse:** 20-30 Aufgaben pro Agent
**BACH-Tool:** `bach skills create chunk_agent --type tool`

**Ablauf:**
1. Aufgabe analysieren und in gleichgrosse Teile aufteilen
2. Jeden Chunk einem Agenten zuweisen (via task delegation)
3. Parallel ausfuehren (verschiedene Claude-Instanzen oder API-Calls)
4. Ergebnisse in Haupt-Instanz zusammenfuehren
5. Quality-Check: Konsistenz der Teilergebnisse pruefen

**Beispiel:**
```bash
# 100 Dokumente uebersetzen: 5 Agenten a 20 Dokumente
bach task add "Chunk 1-20: DE->EN Uebersetzung" --agent translator_de
bach task add "Chunk 21-40: DE->EN Uebersetzung" --agent translator_de
# ... etc.
```

---

### 2. Hierarchie-Schwarm (Boss + Worker)

Boss teilt auf -> Worker bearbeiten -> Boss konsolidiert

**Einsatz:** Komplexe Projekte, Abhaengigkeits-Management
**Tool:** llmauto chain (geplant)

**Rollen:**
- **Boss-Agent:** Zerlegung, Delegation, Konsolidierung, Qualitaetskontrolle
- **Worker-Agenten:** Spezialisiert, bearbeiten einen klar abgegrenzten Teilbereich
- **Koordinator:** BACH selbst (Task-System, Memory, Logging)

**Abbruchkriterien:**
- Worker meldet BLOCKED -> Boss bearbeitet Blockade
- Worker meldet FAIL -> Boss delegiert neu oder eskaliert
- Timeout -> Boss bricht Kette ab und dokumentiert Status

---

### 3. Stigmergy-Schwarm (Pheromon-basiert)

Agenten hinterlassen Markierungen -> andere folgen erfolgreichen Pfaden

**Einsatz:** Exploration, Optimierung ohne zentrale Koordination
**BACH-Implementierung:** shared_memory_working als Pheromon-Traeger
**Namespace:** 'stigmergy' (siehe stigmergy_api.py)

**Prinzip:**
- Agent A findet erfolgreichen Pfad -> schreibt Pheromon mit Staerke 0.8
- Agent B liest Pheromone -> waehlt Pfad mit staerksten Pheromonen
- Nicht genutzte Pfade -> Pheromone verdunsten (evaporate())
- Ergebnis: Emergentes Routing ohne zentrale Steuerung

**Anwendungsfall:** Feature-Exploration in grossem Codebase
- Agenten testen verschiedene Ansaetze
- Erfolgreiche Ansaetze werden markiert
- Spaetere Agenten folgen den Markierungen

---

### 4. Konsensus-Schwarm

Mehrere Agenten bearbeiten dieselbe Aufgabe -> Mehrheitsentscheid

**Einsatz:** Qualitaetssicherung, Bewertungen, kritische Entscheidungen
**Kosten:** N x Einzelkosten, dafuer hoehere Qualitaet
**Empfohlene Agenten-Zahl:** 3 (ungerade = klarer Mehrheitsentscheid)

**Abstimmungsarten:**
- **Einfache Mehrheit:** 2/3 Agenten einig -> Ergebnis angenommen
- **Qualifizierte Mehrheit:** Alle 3 einig -> fuer kritische Entscheidungen
- **Gewichtete Abstimmung:** Spezialist-Agenten haben mehr Gewicht

**Qualitaets-Check:** Wenn Agenten stark abweichen -> Aufgabe neu formulieren

---

### 5. Spezialist-Schwarm

Verschiedene Experten-Agenten -> jeder fuer sein Fachgebiet

**Einsatz:** BACH Boss-Agenten System
**Implementiert:** 11 Boss-Agenten + 17 Experten (Stand v2.5)

**Spezialisierungen in BACH:**
- STEUER-Boss: ELSTER, CAMT, Fahrtenbuch
- GESUNDHEIT-Boss: Diagnosen, Labor, Medikamente
- FINANZEN-Boss: Banking, Versicherungen
- SOFTWARE-Boss: Code-Analyse, ATI, Commits
- THERAPIE-Boss: Protokolle, Foerderberichte, ICF
- HAUSHALT-Boss: Einkauf, Kalender, Planung
- KARRIERE-Boss: Bewerbungen, CV

**Routing:** BACH analysiert Aufgabe und leitet an zustaendigen Boss weiter

---

## Vergleichs-Tabelle

| Muster | Koordination | Skalierung | Kosten | Qualitaet |
|--------|-------------|------------|--------|-----------|
| parallel-chunks | Zentral (Split+Merge) | Linear | 1x | Gleichwertig |
| Hierarchie | Hierarchisch | Moderat | 1.5x | +20% |
| Stigmergy | Dezentral | Sehr gut | 1x | +10% |
| Konsensus | Abstimmung | Schlecht | 3x | +30% |
| Spezialist | Routing | Sehr gut | 1x | +25% |

---

*Naechster Schritt: stigmergy_api.py vollstaendige Implementierung (nach Release)*
