# Atomare Team-Locks für Schwarmarbeit

**Stand:** 2026-07-15  
**Status:** Portabler Koordinations-Guardrail, kein sechstes Schwarmmuster

## Zweck

Mehrere Prozesse dürfen gemeinsame Dateien, Datenbanken, Tools oder Sitzungen
nicht über eine gemeinsam editierte Plaintextdatei claimen: Read-modify-write
verliert unter Parallelität Einträge und kann zwei Gewinner erzeugen.

`tools/team_lock.py` verwendet deshalb zwei atomare Dateimuster:

- Ein Claim pro Ressource wird mit `O_CREAT | O_EXCL` angelegt. Genau ein
  konkurrierender Prozess gewinnt.
- Anwesenheit liegt in einer unveränderlichen JSON-Datei pro Teilnehmer. Ein
  Join überschreibt niemals den Eintrag eines anderen Teilnehmers.

Die Zustände liegen projektlokal unter `.team-locks/`. Das Verzeichnis gehört in
lokale Laufzeitdaten und wird nicht als Aufgaben- oder Ergebnisartefakt committed.

## Verwendung

```python
from tools.team_lock import TeamLock

lock = TeamLock(project_root=".", owner="reviewer")
lock.register(role="review", task="security pass")

if not lock.claim("tools/runner.py", kind="file"):
    raise RuntimeError("resource already claimed")

try:
    # geprüfter exklusiver Schreibzugriff
    ...
finally:
    lock.release("tools/runner.py", kind="file")
    lock.leave()
```

## Geltung und Vorrang

- Ein projektweites `LOCK.txt`, Nutzer-Lock oder zentraler Lock-Manager hat Vorrang.
- Read-only-Teilaufgaben benötigen keinen exklusiven Datei-Claim.
- Ressourcen-IDs müssen kanonisch und im Team identisch sein.
- Claims enthalten eine Ablaufzeit als Auditinformation. Abgelaufene Claims
  werden nicht automatisch gestohlen; ihre Entfernung verlangt eine bewusste,
  extern koordinierte Recovery-Entscheidung.
- Freigeben darf nur der Token, der den Claim atomar angelegt hat.

## Lebenszyklus

1. Übergeordnete Projekt-/Nutzer-Locks prüfen.
2. Anwesenheit registrieren.
3. Vor dem ersten Schreibzugriff den engsten Ressourcen-Claim atomar erwerben.
4. Bei `False` warten, andere Arbeit wählen oder einen Handoff anfordern.
5. Claim im `finally`-Block freigeben; danach Anwesenheit entfernen.

## Verifikation

`tests/test_team_lock.py` startet zwei echte Prozesse gleichzeitig auf denselben
Scope. Der Gate-Test verlangt genau einen Gewinner und zwei erhaltene
Attendance-Einträge. Ein zweiter Test beweist tokengebundene Freigabe.

Installationen mit einem zentralen Lock-Manager dürfen diese lokale
Implementierung durch ihre strengere Spezifikation ersetzen.
