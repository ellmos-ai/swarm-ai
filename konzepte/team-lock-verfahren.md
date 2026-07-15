# Team-Lock-Verfahren für Schwarmarbeit

**Stand:** 2026-07-15  
**Status:** Portabler Koordinations-Guardrail, kein sechstes Schwarmmuster

## Zweck

Wenn mehrere Agenten parallel dieselben Dateien, Tools, Sitzungen oder
Ergebnisartefakte nutzen, reicht eine bloße Aufgabenverteilung nicht. Ein
projektlokaler Team-Lock macht Anwesenheit, Claims, Warteschlangen und kurze
Übergaben sichtbar. Die Datei liegt im betroffenen Projekt und wird von allen
beteiligten Agenten vor Schreibzugriffen gelesen.

## Dateiname und Geltung

```text
LOCK.team.<host>.txt
LOCK.team.<scope>.<host>.txt
```

- `host` bezeichnet das System, auf dem das Team koordiniert wird.
- `scope` begrenzt den Claim optional auf einen Teilbereich.
- Für andere Systeme wirkt der Team-Lock wie eine exklusive Sperre.
- Ein projektweites `LOCK.txt` oder ein Nutzer-Lock hat Vorrang.
- Projektspezifische Lock-Regeln haben Vorrang vor diesem allgemeinen Muster.

## Pflichtbereiche

Eine Team-Lockdatei enthält:

1. Anwesenheit: Agent, Rolle, Aufgabe und Startzeit.
2. Datei-/Ordner-Claims mit Warteschlange.
3. Tool-/MCP-/Sitzungs-Claims mit Warteschlange.
4. Nachrichten, Warnungen und kurze Übergaben.

Beispiel:

```text
owner: local-agent-team
created: 2026-07-15T10:00+02:00
host: WORKSTATION
expires_after: 24h
mode: hard
purpose: Parallel review and fixes
scope: project

[attendance]
- reviewer: security review, started 10:00
- implementer: waiting for review findings

[file_claims]
- reviewer: read-only whole repository
- implementer: tools/runner.py after review handoff

[tool_claims]
- none

[messages]
- Keep experiment outputs unchanged.
```

## Lebenszyklus

1. Vor Arbeitsbeginn bestehende `LOCK*.txt` prüfen.
2. Team-Lock anlegen oder der bestehenden Anwesenheit beitreten.
3. Claims vor dem ersten Schreibzugriff eintragen und eng halten.
4. Freie Ressourcen zuerst an eingetragene Wartende übergeben.
5. Eigene Claims beim Abschluss entfernen.
6. Die Datei erst löschen, wenn keine aktive Anwesenheit mehr eingetragen ist.

## Wann genügt ein einfacher Lock?

- Unabhängige Read-only-Chunks brauchen meist keinen gemeinsamen Team-Lock.
- Ein einzelner schreibender Agent nutzt einen normalen Projekt- oder Scope-Lock.
- Team-Locks sind für echte lokale Parallelität mit gemeinsamen Ressourcen gedacht.

## Einordnung in die fünf Muster

- Parallel-Chunks: nur bei gemeinsamem Output oder überlappenden Dateien.
- Hierarchie: der Koordinator vergibt und konsolidiert Claims.
- Stigmergie: der Lock schützt gemeinsame Stores und Experimentverzeichnisse.
- Konsens: der Lock schützt Bewertungsartefakte und die Entscheidungsausgabe.
- Spezialisten-Routing: Spezialisten claimen ihre Ressourcen, der Koordinator führt zusammen.

Installationen mit einem zentralen Lock-Manager können dieses portable Format
durch ihre strengere lokale Spezifikation ersetzen.
