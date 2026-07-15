# Schwarm-Dungeon (historisches Experiment)

Diese Dateien dokumentieren frühe LLM-Schatzsuche-Experimente mit absichtlich
fehlerhaften Fixture-Dateien. Sie sind kein produktiver Einstiegspunkt.

## Sichere Fixture-Erzeugung

Der Generator schreibt standardmäßig nur in ein neues oder leeres Ziel. Ein
nichtleeres Ziel wird ohne bewusstes `--force` abgewiesen:

```bash
python dungeon_template.py ./tmp/test_dungeon STIGMERGIE
```

Der Generator schreibt eine eigene Markierungsdatei in das Dungeon-Ziel.
`--force` funktioniert ausschließlich, wenn diese Markierung unverändert
vorhanden ist; ein beliebiger nichtleerer Ordner kann nicht erzwungen
überschrieben werden.

## Legacy-Launcher

Die Launcher sind standardmäßig gesperrt. Ein Lauf erfordert:

```text
SWARM_ENABLE_LEGACY_EXPERIMENTS=I_UNDERSTAND
SWARM_EXPERIMENT_TARGET=<existierender, isolierter Nicht-Root-Ordner>
SWARM_EXPERIMENT_MAX_BUDGET_USD_PER_AGENT=<positiver endlicher Betrag>
```

Im Ziel muss außerdem `.swarm-dungeon-fixture` mit exakt
`SWARM_AI_DUNGEON_FIXTURE_V1` liegen. Jeder Aufruf benötigt einen ausdrücklichen
Test- oder Vollmodus und ein Gesamtbudget, zum Beispiel:

```bash
python elephant_path_treasure_hunt.py --test --max-total-budget-usd 1
```

Die Launcher verwenden keinen Permission-Bypass. Sie starten Claude im
Safe-Mode, sperren MCP sowie Sitzungspersistenz und genehmigen nur
Glob/Grep/Read/Edit/Write vorab. Benutzer-Memory-Dateien werden nie verändert.
Trotzdem sind v2/v3 schreibfähige Experimente: nur gegen das isolierte Fixture
starten und die Gesamtwirkung vorher prüfen.

Die Continuous-Flow-Variante bewahrt `.leichen/` nach dem Lauf, weil das
Verzeichnis bereits vor dem Lauf bestanden haben könnte. Aufräumen erfolgt
bewusst manuell nach Sichtprüfung.

## Varianten

- `dungeon_template.py`: reproduzierbarer Fixture-Generator.
- `elephant_path_treasure_hunt.py`: rundenbasierte historische Variante.
- `elephant_path_treasure_hunt_live.py`: Continuous-Flow-Variante mit Markern.

Ergebnisartefakte bleiben als historische, nicht erneut verifizierte Snapshots
erhalten. In ihnen vorkommende alte Pfade und Modellangaben beschreiben frühere
Läufe und sind keine aktuelle Konfiguration.
