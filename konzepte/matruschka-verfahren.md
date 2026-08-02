# Matruschka-Verfahren (Synonym: Subsidiaritätsprinzip)

**Version:** 1.3 | **Stand:** 2026-08-02

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
| 1 | Starker Worker | 2 Helfer der mittleren Klasse |
| 2 | Mittlerer Worker/Helfer | 1 Helfer der kleinen Klasse |
| 3 | Kleiner Helfer | keine weiteren Helfer |

Die konkreten Zahlen und Modellklassen sind konfigurierbar; konstant bleiben
vier Kernregeln:

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
4. **Exklusive Schreibbereiche bei paralleler Arbeit:** Wer delegiert und
   dabei selbst weiterarbeitet, vergibt disjunkte Schreibbereiche (etwa: Helfer
   nur `tests/`, Hauptagent `tools/`) — oder gibt dem Helfer eine eigene Kopie
   bzw. einen eigenen Worktree. **Ein Schreibverbot wird immer MIT Begründung
   ausgesprochen:** „nicht anfassen, weil ich parallel daran messe". Ohne das
   Warum wirkt ein kurzes, temporäres Zurücksetzen wie ein folgenloser
   Zwischenschritt, und ein gut gemeinter Gegencheck hebelt die Trennung aus.
   **Auch Lesen und Messen ist eine Nutzung des Bereichs:** Wer misst, muss sich
   darauf verlassen können, dass niemand parallel schreibt — sonst werden die
   Messwerte falsch, ohne dass es jemandem auffällt.

   *Belegfall 2026-08-02 (swarm-ai):* Der Hauptagent präzisierte einen Docstring
   in `tools/`, während der Test-Helfer dieselbe Datei trotz Verbots kurz auf den
   alten Stand zurückdrehte, um zu prüfen, ob seine neuen Tests den Fehler
   wirklich fangen. Ergebnis: zwei widersprüchliche Messreihen hintereinander und
   eine komplette Debug-Runde, bis die Ursache gefunden war. Beide Seiten
   handelten plausibel — die Bereichstrennung existierte, nur ihr Zweck war nie
   ausgesprochen worden.

**Rollen-Präzisierung unterste Ebene:** Ein einzelner Helfer der kleinsten
Modellklasse ist ein **Assistent**, kein Worker — geeignet für Botengänge, kleine
Dienste und kurze Recherchen (eng umrissene Einzelaufträge mit kleinem Kontext).
Als **Worker** taugt die kleinste Klasse nur im Schwarm: viele parallel auf
gleichartige kleine Chunks (parallel-chunks-Muster), nicht einer allein auf eine
große Sammelaufgabe — die endet im Kontextüberlauf.

**Zwei Betriebsarten für den Helfer-Slot:** (a) **Fester Assistent mit
Kontextbewahrung** — derselbe Helfer wird über Folgeaufträge wiederverwendet und
behält sein geladenes Wissen (Default bei thematisch zusammenhängenden Diensten).
(b) **Einweg-Helfer** — pro Kleinauftrag ein frischer Helfer, Ergebnis abliefern,
danach beenden/verwerfen; so sind auch kleine **Staffelaufträge** möglich (seriell
nacheinander), solange immer nur EIN Helfer gleichzeitig aktiv ist. Das
Aktivitäts-Limit gilt in beiden Betriebsarten gleich.

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
