# Matruschka-Verfahren (Synonym: Subsidiaritätsprinzip)

**Version:** 1.1 | **Stand:** 2026-08-01

Kaskadierte Helfer-Delegation mit Aktivitäts-Limits je Ebene. Wie das
Team-Lock-Verfahren ist dies **kein sechstes Grundmuster**, sondern ein
Querschnittsverfahren: Es regelt die **Besetzung und Staffelung** eines Schwarms,
unabhängig vom gewählten Grundmuster (kombinierbar vor allem mit `hierarchy`,
aber auch mit jedem anderen Muster).

## Prinzip

Jede Ebene darf sich selbst eine begrenzte Zahl Helfer der nächstkleineren
Modellklasse spawnen — wie ineinander geschachtelte Matruschka-Puppen.
Entscheidungskompetenz bleibt oben, Ausführung wandert so weit wie möglich nach
unten (Subsidiaritätsprinzip: die kleinste Einheit, die eine Aufgabe lösen kann,
löst sie).

## Referenz-Staffelung (Beispiel mit vier Modellklassen)

| Ebene | Rolle | Darf gleichzeitig aktiv halten |
|---|---|---|
| 0 | Operator (stärkste Klasse) | z. B. 2 × starke Worker + 1 × mittlerer Worker |
| 1 | Starker Worker | 1 Helfer der mittleren Klasse |
| 2 | Mittlerer Worker/Helfer | 1 Helfer der kleinen Klasse |
| 3 | Kleiner Helfer | keine weiteren Helfer |

Die konkreten Zahlen und Modellklassen sind konfigurierbar; konstant bleiben
drei Kernregeln:

1. **Limits zählen gleichzeitige AKTIVITÄT, nicht Bestand.** Es dürfen mehr
   Agenten VORGEHALTEN werden, als aktiv sind — wartende/pausierte Agenten
   kosten keinen Slot.
2. **Vorhalten + Wiederverwenden statt Neu-Spawnen:** Agenten kontextbezogen
   bzw. bereichs-/ortsspezifisch wiederverwenden (Folgeauftrag an den
   bestehenden Agenten), um wertvollen Loading-Context (gelesene Register,
   Projektwissen) zu erhalten. Erst bei Domänenwechsel oder drohender
   Kontext-Kompaktierung sauber abschließen und auf einen frischen Agenten
   rotieren.
3. **Delegation nur abwärts, je eine Modellklasse:** nie lateral oder aufwärts
   spawnen; Eskalation nach oben läuft über die Abschlussmeldung an den
   Auftraggeber.

**Rollen-Präzisierung unterste Ebene:** Ein einzelner Helfer der kleinsten
Modellklasse ist ein **Assistent**, kein Worker — geeignet für Botengänge, kleine
Dienste und kurze Recherchen (eng umrissene Einzelaufträge mit kleinem Kontext).
Als **Worker** taugt die kleinste Klasse nur im Schwarm: viele parallel auf
gleichartige kleine Chunks (parallel-chunks-Muster), nicht einer allein auf eine
große Sammelaufgabe — die endet im Kontextüberlauf.

## Abgrenzung

- **vs. `hierarchy`:** hierarchy beschreibt die Baum-KOORDINATION (wer kennt
  wen, wie fließen Ergebnisse); Matruschka beschreibt die KAPAZITÄTS- und
  MODELLKLASSEN-Staffelung je Ebene. Ein hierarchy-Schwarm kann, muss aber
  nicht matruschka-gestaffelt sein.
- **vs. Team-Lock-Verfahren:** Team-Lock schützt gemeinsame Ressourcen;
  Matruschka regelt Besetzung und Delegationstiefe. Beide sind orthogonal und
  kombinierbar.

## Wann einsetzen

- Langlaufende Operator-/Loop-Sessions mit begrenztem Parallel-Budget
- Wenn der Orchestrator Kontext sparen muss (reine Entscheider-/Lenker-Rolle)
  und Ausführung vollständig delegiert
- Wenn Worker selbst mechanische Unteraufgaben haben (Tests, Formatierung,
  Suche)

## Grenzen

- Tiefe Kaskaden verwässern das Gesamtbild (Ebene 3 kennt den Auftrag nur
  gefiltert)
- Abnahme bleibt Pflicht auf JEDER Ebene (eine Fertigmeldung ist kein Nachweis
  — Artefakte am Evidenzpfad selbst prüfen)
- Slot-Buchhaltung nötig: Wer spawnt, prüft vor jedem Neu-Spawn seine aktiven
  Helfer

---

*Begleit-Dateien: schwarm-operationen.md (Grundmuster), team-lock-verfahren.md (Ressourcenschutz)*
