#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schatzsuche / Treasure Hunt v2.0 - Runden-basiertes Swarm Pattern E
====================================================================
LLM-Agenten navigieren einen Dungeon mit Raumen, Fallen und einem Schatz.
Runden-System: Pro Runde N Agenten gleichzeitig, dann naechste Runde.
Agenten koennen Fallen REPARIEREN - spaetere Runden sehen die Fixes.

Verwendung:
  cd system/ && python data/elephant_path_treasure_hunt.py           # Vollversion: 10 Runden x 10
  cd system/ && python data/elephant_path_treasure_hunt.py --test    # Testmodus: 1 Runde x 5

Konfiguration:
  AGENTS_PER_ROUND  - Agenten pro Runde (gleichzeitig)
  NUM_ROUNDS        - Anzahl Runden
  TIMEOUT_SECONDS   - Max. Zeit pro Agent
  DUNGEON_PATH      - Pfad zum Dungeon

v2.0 - Runden-basiert:
  - Runde 1: Alle Agenten gleichzeitig los, koennen Fallen fixen
  - Runde 2: Naechste Welle sieht die Aenderungen der vorherigen
  - Nach allen Runden: Welche Fallen wurden gefixt? Welche ueberlebten?
  - Dungeon-Snapshot vor/nach jeder Runde (Checksummen)
  - Testmodus: --test fuer 1 Runde mit 5 Agenten
"""

import argparse
import subprocess
import time
import json
import math
import os
import sys
import re
import hashlib
import threading
from pathlib import Path
from datetime import datetime

# --- Konfiguration ---
AGENTS_PER_ROUND = 10
NUM_ROUNDS = 10
TIMEOUT_SECONDS = 180
MAX_CONCURRENT = 5     # API-Limit innerhalb einer Runde
MODEL = "haiku"
TARGET_PATH = os.getenv("SWARM_EXPERIMENT_TARGET", "")
DUNGEON_PATH = "data/swarm/dungeon"  # Relativ zu TARGET_PATH
DUNGEON_FIXTURE_MARKER = ".swarm-dungeon-fixture"
DUNGEON_FIXTURE_MARKER_CONTENT = "SWARM_AI_DUNGEON_FIXTURE_V1"
RESULTS_DIR = Path(__file__).parent / "elephant_path_treasure_hunt"


def experiment_budget_per_agent():
    raw = os.getenv("SWARM_EXPERIMENT_MAX_BUDGET_USD_PER_AGENT", "")
    try:
        value = float(raw)
    except ValueError as exc:
        raise SystemExit(
            "SWARM_EXPERIMENT_MAX_BUDGET_USD_PER_AGENT must be a positive number"
        ) from exc
    if not math.isfinite(value) or value <= 0:
        raise SystemExit(
            "SWARM_EXPERIMENT_MAX_BUDGET_USD_PER_AGENT must be a positive number"
        )
    return value


def parse_cli():
    parser = argparse.ArgumentParser(description="Historical round-based dungeon swarm")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--test", action="store_true", help="Run one round with five agents")
    mode.add_argument("--run", action="store_true", help="Run the configured full experiment")
    parser.add_argument("--max-total-budget-usd", type=float, required=True)
    args = parser.parse_args()
    if (not math.isfinite(args.max_total_budget_usd) or
            args.max_total_budget_usd <= 0):
        parser.error("--max-total-budget-usd must be positive and finite")
    return args


def validate_total_budget(agent_count, total_budget):
    requested = experiment_budget_per_agent() * agent_count
    if requested > total_budget:
        raise SystemExit(
            f"per-agent caps total ${requested:.2f}, above the run budget "
            f"${total_budget:.2f}"
        )

TREASURE_WORD = "STIGMERGIE"
DECOY_WORD = "FALSCHGOLD"

# Bekannte Fallen mit Pruef-Logik
KNOWN_TRAPS = {
    "falle_1.py": {
        "path": "raum_1/falle_1.py",
        "description": "Python-Bug: i%2==1 statt i%2==0",
        "check": lambda content: "i % 2 == 0" in content or "i % 2==0" in content,
    },
    "falle_2.json": {
        "path": "raum_2/falle_2.json",
        "description": "Fehlendes Komma im JSON-Array",
        "check": lambda content: _is_valid_json(content),
    },
    "falle_3.txt": {
        "path": "raum_3/falle_3.txt",
        "description": "Falsche Werte: 47 statt 93, powershell statt bash",
        "check": lambda content: "93" in content and ("bash" in content.lower() and "powershell" not in content.lower()),
    },
}

def require_explicit_opt_in():
    """Fail closed before this historical, write-capable experiment starts."""
    if os.getenv("SWARM_ENABLE_LEGACY_EXPERIMENTS") != "I_UNDERSTAND":
        raise SystemExit(
            "Historical experiment disabled. Set "
            "SWARM_ENABLE_LEGACY_EXPERIMENTS=I_UNDERSTAND explicitly."
        )
    target = Path(TARGET_PATH).expanduser()
    if not TARGET_PATH or not target.is_dir() or target.resolve().parent == target.resolve():
        raise SystemExit("SWARM_EXPERIMENT_TARGET must name an existing non-root directory")
    marker = target / DUNGEON_FIXTURE_MARKER
    if (not marker.is_file() or
            marker.read_text(encoding="utf-8").strip() != DUNGEON_FIXTURE_MARKER_CONTENT):
        raise SystemExit(
            f"Dungeon experiments require an isolated fixture marker: {marker}"
        )
    experiment_budget_per_agent()


def _is_valid_json(content):
    try:
        json.loads(content)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


# --- Prompt ---
PROMPT_TEMPLATE = r"""Du bist ein Schatzsucher im BACH-System.
BACH liegt unter: {target_path}

AUFTRAG: Finde das geheime Codewort das im Dungeon versteckt ist.
Der Dungeon liegt in: {dungeon_path}

REGELN:
1. Starte in {dungeon_path} und lies das README.md
2. Folge den Hinweisen von Raum zu Raum
3. Lies ALLE Dateien in jedem Raum BEVOR du zum naechsten gehst
4. Manche Raeume enthalten FALLEN (fehlerhafte Dateien)
5. Wenn du eine Falle findest: REPARIERE den Fehler in der Datei!
   Das ist Teil der Aufgabe - reparieren und weitergehen.
6. Es gibt ABLENKUNGEN - lass dich nicht taeuschen
7. Es gibt eine FALSCHE TRUHE - pruefe ob ein Codewort echt ist
8. Maximal 20 Schritte

WICHTIG:
- Nutze ausschließlich Glob/Grep/Read/Edit/Write innerhalb des Fixture-Ziels
- Wenn eine Datei einen Fehler hat, benutze Edit/Write um ihn zu beheben

Am Ende IMMER diese Zusammenfassung:
  CODEWORT: (das gefundene Wort oder "nicht gefunden")
  BESUCHTE_RAEUME: (Liste aller Raeume)
  GEFUNDENE_FALLEN: (Liste mit Beschreibung jedes Fehlers)
  REPARIERTE_FALLEN: (Liste der Dateien die du gefixt hast)
  ABLENKUNG_ERKANNT: ja oder nein
  FALSCHE_TRUHE_ERKANNT: ja oder nein
  AUFTRAG_ERFUELLT: ja oder nein

Los."""


# --- Dungeon Snapshot ---
def snapshot_dungeon(dungeon_base):
    """Erstellt Checksummen aller Dungeon-Dateien."""
    snapshot = {}
    for f in sorted(dungeon_base.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(dungeon_base)).replace("\\", "/")
            content = f.read_bytes()
            snapshot[rel] = {
                "hash": hashlib.md5(content).hexdigest(),
                "size": len(content),
            }
    return snapshot


def check_traps(dungeon_base):
    """Prueft welche bekannten Fallen noch kaputt sind."""
    status = {}
    for name, trap in KNOWN_TRAPS.items():
        fpath = dungeon_base / trap["path"]
        if not fpath.exists():
            status[name] = {"exists": False, "fixed": False, "deleted": True}
            continue
        content = fpath.read_text(encoding="utf-8", errors="replace")
        is_fixed = trap["check"](content)
        status[name] = {"exists": True, "fixed": is_fixed, "deleted": False}
    return status


def restore_dungeon_from_template(dungeon_base):
    """Stellt den Dungeon aus dem Template wieder her."""
    template_script = Path(__file__).parent / "dungeon_template.py"
    if template_script.exists():
        # Template-Script importieren und ausfuehren
        import importlib.util
        spec = importlib.util.spec_from_file_location("dungeon_template", template_script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.create_dungeon(
            str(dungeon_base), TREASURE_WORD, DECOY_WORD, force=True
        )
        return True
    return False


# --- Stream-JSON Parser ---
def parse_stream_json(raw_text):
    tool_calls = []
    visited_paths = []
    final_result = None
    num_turns = 0
    total_cost = 0.0

    for line in raw_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type", "")
        if etype == "assistant":
            msg = event.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        tool_calls.append({"tool": tool_name, "input": tool_input})
                        for key in ["path", "file_path", "command", "pattern"]:
                            if key in tool_input:
                                visited_paths.append(f"{tool_name}: {tool_input[key]}")
        if etype == "result":
            final_result = event.get("result", "")
            num_turns = event.get("num_turns", 0)
            total_cost = event.get("total_cost_usd", 0)

    return {
        "tool_calls": tool_calls,
        "visited_paths": visited_paths,
        "final_result": final_result,
        "num_turns": num_turns,
        "total_cost_usd": total_cost,
    }


# --- Ergebnis-Analyse ---
def analyze_treasure_result(parsed, raw_text):
    result_text = (parsed.get("final_result") or "") + "\n" + raw_text[-5000:]
    result_lower = result_text.lower()

    found_treasure = TREASURE_WORD.lower() in result_lower
    found_decoy = DECOY_WORD.lower() in result_lower and not found_treasure

    codewort_match = re.search(r"CODEWORT:\s*(\S+)", result_text, re.IGNORECASE)
    reported_word = codewort_match.group(1) if codewort_match else None

    paths_str = " ".join(parsed.get("visited_paths", []))
    rooms_visited = {
        "raum_1": "raum_1" in paths_str,
        "raum_2": "raum_2" in paths_str,
        "raum_3": "raum_3" in paths_str,
        "kammer": "kammer" in paths_str,
        "tresor": "tresor" in paths_str,
    }

    traps_found = {
        "falle_1": "falle_1" in paths_str,
        "falle_2": "falle_2" in paths_str,
        "falle_3": "falle_3" in paths_str,
        "ablenkung": "ablenkung" in paths_str,
        "falsche_truhe": "falsche_truhe" in paths_str,
    }

    # Reparatur-Erkennung (Edit/Write auf falle_* Dateien)
    traps_repaired = {
        "falle_1": any("falle_1" in p and ("Edit" in p or "Write" in p) for p in parsed.get("visited_paths", [])),
        "falle_2": any("falle_2" in p and ("Edit" in p or "Write" in p) for p in parsed.get("visited_paths", [])),
        "falle_3": any("falle_3" in p and ("Edit" in p or "Write" in p) for p in parsed.get("visited_paths", [])),
    }

    return {
        "found_treasure": found_treasure,
        "found_decoy": found_decoy,
        "reported_word": reported_word,
        "rooms_visited": rooms_visited,
        "rooms_count": sum(rooms_visited.values()),
        "traps_encountered": traps_found,
        "traps_count": sum(traps_found.values()),
        "traps_repaired": traps_repaired,
        "repairs_count": sum(traps_repaired.values()),
    }


# --- Einzelner Agent ---
def run_agent(agent_id, round_num, results_lock, round_results, sem):
    prompt = PROMPT_TEMPLATE.format(target_path=TARGET_PATH, dungeon_path=DUNGEON_PATH)
    prefix = f"r{round_num:02d}_a{agent_id:02d}"
    stream_file = RESULTS_DIR / f"{prefix}.stream.jsonl"
    output_file = RESULTS_DIR / f"{prefix}.json"

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = [
        "claude", "-p",
        "--model", MODEL,
        "--max-budget-usd", str(experiment_budget_per_agent()),
        "--verbose",
        "--permission-mode", "dontAsk",
        "--no-session-persistence",
        "--safe-mode",
        "--disallowedTools", "mcp__*",
        "--tools", "Glob,Grep,Read,Edit,Write",
        "--allowedTools", "Glob", "Grep", "Read", "Edit", "Write",
        "--output-format", "stream-json",
        prompt,
    ]

    sem.acquire()
    start_time = time.time()
    timed_out = False
    stdout_data = b""
    stderr_data = b""

    try:
        try:
            result = subprocess.run(
                cmd, capture_output=True,
                timeout=TIMEOUT_SECONDS, env=env,
                cwd=str(Path(TARGET_PATH).expanduser().resolve()),
            )
            stdout_data = result.stdout
            stderr_data = result.stderr
            returncode = result.returncode
        except subprocess.TimeoutExpired as e:
            timed_out = True
            stdout_data = e.stdout or b""
            stderr_data = e.stderr or b""
            returncode = -1

        elapsed = time.time() - start_time
        with open(stream_file, "wb") as f:
            f.write(stdout_data)

        raw_text = stdout_data.decode("utf-8", errors="replace") if stdout_data else ""
        parsed = parse_stream_json(raw_text)

        if not parsed["tool_calls"] and stderr_data:
            stderr_text = stderr_data.decode("utf-8", errors="replace")
            parsed_stderr = parse_stream_json(stderr_text)
            if parsed_stderr["tool_calls"]:
                parsed = parsed_stderr
                raw_text = stderr_text

        treasure = analyze_treasure_result(parsed, raw_text)

        result_data = {
            "agent_id": agent_id,
            "round": round_num,
            "model": MODEL,
            "status": "timeout" if timed_out else "completed",
            "duration_seconds": round(elapsed, 1),
            "num_turns": parsed["num_turns"],
            "total_cost_usd": parsed["total_cost_usd"],
            "stdout_bytes": len(stdout_data),
            "tool_calls_count": len(parsed["tool_calls"]),
            "visited_paths": parsed["visited_paths"],
            "tool_calls": parsed["tool_calls"],
            "final_result": parsed["final_result"][:3000] if parsed["final_result"] else None,
            "treasure": treasure,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        word = treasure["reported_word"] or "?"
        rooms = treasure["rooms_count"]
        repairs = treasure["repairs_count"]
        found = "SCHATZ!" if treasure["found_treasure"] else ("KOEDER!" if treasure["found_decoy"] else "LEER")
        status_str = "TIMEOUT" if timed_out else "OK"

        with results_lock:
            round_results.append(result_data)
            print(f"    R{round_num} A{agent_id:2d} | {status_str} {found} | {rooms} Raeume, {repairs} Repairs, Wort: {word} | {elapsed:.0f}s")
            sys.stdout.flush()

    except Exception as e:
        with results_lock:
            round_results.append({
                "agent_id": agent_id, "round": round_num,
                "status": "error", "error": str(e),
            })
            print(f"    R{round_num} A{agent_id:2d} | EXCEPTION: {e}")
            sys.stdout.flush()
    finally:
        sem.release()


# --- Hauptprogramm ---
def main():
    args = parse_cli()
    require_explicit_opt_in()
    RESULTS_DIR.mkdir(exist_ok=True)
    test_mode = args.test
    if test_mode:
        agents_per_round = 5
        num_rounds = 1
        print("  *** TESTMODUS: 1 Runde x 5 Agenten ***")
    else:
        agents_per_round = AGENTS_PER_ROUND
        num_rounds = NUM_ROUNDS

    total_agents = agents_per_round * num_rounds
    validate_total_budget(total_agents, args.max_total_budget_usd)
    dungeon_base = Path(TARGET_PATH) / DUNGEON_PATH

    print(f"{'='*65}")
    print(f"  SCHATZSUCHE v2.0 - Runden-basiertes Swarm Pattern E")
    print(f"  {num_rounds} Runden x {agents_per_round} Agenten = {total_agents} total")
    print(f"  Max {MAX_CONCURRENT} gleichzeitig pro Runde")
    print(f"  Timeout: {TIMEOUT_SECONDS}s, Model: {MODEL}")
    print(f"  Dungeon: {dungeon_base}")
    print(f"  Agenten koennen Fallen REPARIEREN (Edit/Write)")
    print(f"  Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")
    print()

    experiment_start = time.time()
    all_round_data = []

    for round_num in range(1, num_rounds + 1):
        print(f"  {'─'*55}")
        print(f"  RUNDE {round_num}/{num_rounds}")
        print(f"  {'─'*55}")

        # Dungeon-Status VOR der Runde
        snapshot_before = snapshot_dungeon(dungeon_base)
        traps_before = check_traps(dungeon_base)
        fixed_before = sum(1 for t in traps_before.values() if t.get("fixed"))
        print(f"  Fallen-Status: {fixed_before}/3 bereits gefixt")

        # Alle Agenten dieser Runde starten
        sem = threading.Semaphore(MAX_CONCURRENT)
        results_lock = threading.Lock()
        round_results = []
        threads = []

        for a in range(1, agents_per_round + 1):
            t = threading.Thread(
                target=run_agent,
                args=(a, round_num, results_lock, round_results, sem),
                daemon=True,
            )
            t.start()
            threads.append(t)

        # Warten bis alle fertig
        for t in threads:
            t.join(timeout=TIMEOUT_SECONDS + 60)

        # Dungeon-Status NACH der Runde
        snapshot_after = snapshot_dungeon(dungeon_base)
        traps_after = check_traps(dungeon_base)
        fixed_after = sum(1 for t in traps_after.values() if t.get("fixed"))

        # Aenderungen erkennen
        changed_files = []
        for fname, info in snapshot_after.items():
            before_info = snapshot_before.get(fname, {})
            if info["hash"] != before_info.get("hash", ""):
                changed_files.append(fname)

        # Runden-Zusammenfassung
        treasure_found = sum(1 for r in round_results if r.get("treasure", {}).get("found_treasure"))
        decoy_found = sum(1 for r in round_results if r.get("treasure", {}).get("found_decoy"))
        total_cost = sum(r.get("total_cost_usd", 0) for r in round_results)

        round_data = {
            "round": round_num,
            "agents": agents_per_round,
            "treasure_found": treasure_found,
            "decoy_found": decoy_found,
            "traps_fixed_before": fixed_before,
            "traps_fixed_after": fixed_after,
            "new_fixes": fixed_after - fixed_before,
            "changed_files": changed_files,
            "cost_usd": round(total_cost, 3),
            "trap_details": {k: v for k, v in traps_after.items()},
            "agent_results": round_results,
        }
        all_round_data.append(round_data)

        print()
        print(f"  Runde {round_num} Ergebnis:")
        print(f"    Schatz:    {treasure_found}/{agents_per_round}")
        print(f"    Koeder:    {decoy_found}/{agents_per_round}")
        print(f"    Fallen:    {fixed_before} → {fixed_after} gefixt ({fixed_after - fixed_before} neu)")
        print(f"    Aenderg.:  {len(changed_files)} Dateien: {', '.join(changed_files) if changed_files else 'keine'}")
        print(f"    Kosten:    ${total_cost:.2f}")

        if fixed_after >= 3:
            print(f"  *** ALLE FALLEN GEFIXT nach Runde {round_num}! ***")

        # Dungeon fuer naechste Runde zuruecksetzen? NEIN - das ist der Witz!
        # Spaetere Runden sehen die Fixes der frueheren.
        print()

    experiment_elapsed = time.time() - experiment_start

    # --- Gesamtauswertung ---
    total_treasure = sum(r["treasure_found"] for r in all_round_data)
    total_decoy = sum(r["decoy_found"] for r in all_round_data)
    total_cost = sum(r["cost_usd"] for r in all_round_data)
    final_traps = check_traps(dungeon_base)

    experiment = {
        "name": "Schatzsuche v2.0 - Runden-basiert",
        "test_mode": test_mode,
        "model": MODEL,
        "round_count": num_rounds,
        "agents_per_round": agents_per_round,
        "total_agents": total_agents,
        "timeout_seconds": TIMEOUT_SECONDS,
        "treasure_word": TREASURE_WORD,
        "decoy_word": DECOY_WORD,
        "start_time": datetime.fromtimestamp(experiment_start).isoformat(),
        "end_time": datetime.now().isoformat(),
        "wall_clock_seconds": round(experiment_elapsed, 1),
        "total_cost_usd": round(total_cost, 2),
        "results": {
            "total_treasure_found": total_treasure,
            "total_decoy_found": total_decoy,
            "total_not_found": total_agents - total_treasure - total_decoy,
            "final_trap_status": {k: v for k, v in final_traps.items()},
        },
        "round_results": all_round_data,
    }

    with open(RESULTS_DIR / "experiment.json", "w", encoding="utf-8") as f:
        json.dump(experiment, f, ensure_ascii=False, indent=2)

    # Dungeon auf Ursprung zuruecksetzen
    print("  [RESET] Stelle Dungeon auf Ursprung zurueck...")
    if restore_dungeon_from_template(dungeon_base):
        print("  Dungeon wiederhergestellt.")
    else:
        print("  WARNUNG: Template nicht gefunden, Dungeon bleibt modifiziert.")

    print()
    print(f"{'='*65}")
    print(f"  SCHATZSUCHE BEENDET!")
    print(f"{'='*65}")
    print(f"  Dauer:           {experiment_elapsed/60:.1f} min")
    print(f"  Kosten:          ${total_cost:.2f}")
    print(f"  Runden:          {num_rounds}")
    print(f"  Agenten total:   {total_agents}")
    print()
    print(f"  --- SCHATZ ---")
    print(f"  Gefunden:        {total_treasure}/{total_agents} ({100*total_treasure/max(total_agents,1):.0f}%)")
    print(f"  Koeder:          {total_decoy}/{total_agents}")
    print()
    print(f"  --- FALLEN-EVOLUTION ---")
    for round_data in all_round_data:
        r = round_data["round"]
        before = round_data["traps_fixed_before"]
        after = round_data["traps_fixed_after"]
        bar_before = "." * (3 - before) + "#" * before
        bar_after = "." * (3 - after) + "#" * after
        print(f"  Runde {r:2d}: [{bar_before}] → [{bar_after}]  ({after - before:+d} Fixes)")
    print()
    print(f"  --- FINAL ---")
    for name, status in final_traps.items():
        icon = "GEFIXT" if status.get("fixed") else "KAPUTT"
        desc = KNOWN_TRAPS[name]["description"]
        print(f"  {name:15s} {icon:6s}  ({desc})")
    print()
    print(f"  Ergebnisse: {RESULTS_DIR}")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()
