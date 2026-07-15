#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elephant Path Experiment - Trampelpfadanalyse
=============================================
Naive LLM-Agenten erkunden PARALLEL ein Dateisystem.
Ergebnisse in data/elephant_path_100/

v6.2 - Sicherheitsgrenzen:
  - Kein Delay mehr: Alle Threads starten sofort, Semaphore regelt Parallelitaet
  - Naiver Kontext via Claude --safe-mode, ohne Benutzerdaten zu veraendern
  - Nur Read/Glob/Grep; konfigurierte MCP-Tools werden separat gesperrt
  - subprocess.run (Windows-kompatibel)

Verwendung:
  cd system/ && python data/elephant_path_launcher.py

Konfiguration: NUM_PROBES, MAX_CONCURRENT, TIMEOUT_SECONDS unten anpassen.
Auch nutzbar fuer beliebige Ordnerstrukturen (TARGET_PATH aendern).
"""

import argparse
import subprocess
import time
import json
import math
import os
import sys
import threading
from pathlib import Path
from datetime import datetime

# --- Konfiguration ---
NUM_PROBES = 100
TIMEOUT_SECONDS = 120
MAX_CONCURRENT = 5
MODEL = "haiku"
TARGET_PATH = os.getenv("SWARM_EXPERIMENT_TARGET", "")
RESULTS_DIR = Path(__file__).parent / "elephant_path_post_signs"


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
    parser = argparse.ArgumentParser(description="Historical read-only elephant-path run")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--test", action="store_true", help="Run one probe")
    mode.add_argument("--run", action="store_true", help="Run the configured probe swarm")
    parser.add_argument("--probes", type=int, default=NUM_PROBES)
    parser.add_argument("--max-concurrent", type=int, default=MAX_CONCURRENT)
    parser.add_argument("--timeout", type=int, default=TIMEOUT_SECONDS)
    parser.add_argument("--max-total-budget-usd", type=float, required=True)
    args = parser.parse_args()
    if args.test:
        args.probes = 1
        args.max_concurrent = 1
    if not 1 <= args.probes <= 100:
        parser.error("--probes must be between 1 and 100")
    if not 1 <= args.max_concurrent <= 20:
        parser.error("--max-concurrent must be between 1 and 20")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
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


def require_explicit_opt_in():
    if os.getenv("SWARM_ENABLE_LEGACY_EXPERIMENTS") != "I_UNDERSTAND":
        raise SystemExit(
            "Historical experiment disabled. Set "
            "SWARM_ENABLE_LEGACY_EXPERIMENTS=I_UNDERSTAND explicitly."
        )
    target = Path(TARGET_PATH).expanduser()
    if not TARGET_PATH or not target.is_dir() or target.resolve().parent == target.resolve():
        raise SystemExit("SWARM_EXPERIMENT_TARGET must name an existing non-root directory")
    experiment_budget_per_agent()

# 20 verschiedene Auftraege (je 5x = 100)
TASKS = [
    "Wie erstellt man einen Task in BACH?",
    "Wie startet man BACH?",
    "Wo sind die Steuerbelege in BACH?",
    "Welche offenen Tasks gibt es in BACH?",
    "Welche Python-Tools gibt es in BACH?",
    "Schreibe einen kurzen Wiki-Artikel ueber ein Thema deiner Wahl in BACH",
    "Wo findet man die BACH-Logs?",
    "Welche Agenten gibt es in BACH?",
    "Wie exportiert man Daten aus der BACH-Datenbank?",
    "Was ist der aktuelle System-Status von BACH?",
    "Wie sendet man eine Nachricht in BACH?",
    "Wie erstellt man ein Backup des Systems?",
    "Suche nach Kontakt-Informationen in BACH",
    "Welche Abonnements werden in BACH verwaltet?",
    "Wo werden Gesundheitsdaten in BACH gespeichert?",
    "Wie verbindet man einen Telegram-Bot mit BACH?",
    "Wie delegiert man einen Task an einen anderen Partner?",
    "Wo sind die Haushaltsdaten und monatlichen Fixkosten?",
    "Durchsuche das BACH-Wissen nach interessanten Eintraegen",
    "Wie erstellt man einen neuen Skill oder ein neues Tool in BACH?",
]

PROMPT_TEMPLATE = r"""Du erkundet das BACH-System.
BACH liegt unter: {target_path}

AUFTRAG: {task}

REGELN:
1. Du weisst NUR den Pfad oben, sonst NICHTS ueber BACH
2. Erkunde das System um den Auftrag zu erfuellen
3. Maximal 8 Schritte
4. Am Ende IMMER diese Zusammenfassung:
   BESUCHTE_VERZEICHNISSE: (volle Pfade, eins pro Zeile)
   GELESENE_DATEIEN: (volle Pfade, eine pro Zeile)
   AUFTRAG_ERFUELLT: ja oder nein
   HILFREICHSTE_DATEI: (eine Datei die am meisten half)

Los."""


# --- Globaler Status ---
lock = threading.Lock()
semaphore = threading.Semaphore(MAX_CONCURRENT)
active_count = 0
completed_count = 0
error_count = 0
results = {}
# --- Stream-JSON Parser ---
def parse_stream_json(raw_text):
    """Parst stream-json Output und extrahiert Tool-Aufrufe und Pfade."""
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


# --- Probe-Runner ---
def run_probe(probe_num, task_text):
    """Startet eine einzelne Probe."""
    global active_count, completed_count, error_count

    prompt = PROMPT_TEMPLATE.format(task=task_text, target_path=TARGET_PATH)
    stream_file = RESULTS_DIR / f"probe_{probe_num:03d}.stream.jsonl"
    stderr_file = RESULTS_DIR / f"probe_{probe_num:03d}.stderr.txt"
    output_file = RESULTS_DIR / f"probe_{probe_num:03d}.json"

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
        "--tools", "Glob,Grep,Read",
        "--allowedTools", "Glob", "Grep", "Read",
        "--output-format", "stream-json",
        prompt,
    ]

    # Warte auf freien Slot
    semaphore.acquire()

    with lock:
        active_count += 1
        print(f"  >> [{probe_num:3d}] GESTARTET (aktiv: {active_count})")
        sys.stdout.flush()

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

        # Rohdaten speichern
        with open(stream_file, "wb") as f:
            f.write(stdout_data)
        if stderr_data:
            with open(stderr_file, "wb") as f:
                f.write(stderr_data)

        # Parsen
        raw_text = stdout_data.decode("utf-8", errors="replace") if stdout_data else ""
        parsed = parse_stream_json(raw_text)

        if not parsed["tool_calls"] and stderr_data:
            stderr_text = stderr_data.decode("utf-8", errors="replace")
            parsed_stderr = parse_stream_json(stderr_text)
            if parsed_stderr["tool_calls"]:
                parsed = parsed_stderr

        result_data = {
            "probe_num": probe_num,
            "task": task_text,
            "task_index": (probe_num - 1) % len(TASKS),
            "model": MODEL,
            "status": "timeout" if timed_out else "completed",
            "returncode": returncode,
            "duration_seconds": round(elapsed, 1),
            "num_turns": parsed["num_turns"],
            "total_cost_usd": parsed["total_cost_usd"],
            "stdout_bytes": len(stdout_data),
            "stderr_bytes": len(stderr_data),
            "tool_calls_count": len(parsed["tool_calls"]),
            "visited_paths": parsed["visited_paths"],
            "tool_calls": parsed["tool_calls"],
            "final_result": parsed["final_result"][:2000] if parsed["final_result"] else None,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        with lock:
            paths = len(parsed["visited_paths"])
            turns = parsed["num_turns"]
            if timed_out:
                error_count += 1
                status = f"TIMEOUT ({elapsed:.0f}s, {paths} Pfade, {len(stdout_data)}B)"
            elif returncode != 0:
                error_count += 1
                status = f"ERR rc={returncode} ({elapsed:.0f}s, {len(stderr_data)}B stderr)"
            else:
                completed_count += 1
                status = f"OK ({elapsed:.0f}s, {turns} turns, {paths} Pfade, {len(stdout_data)}B)"
            results[probe_num] = result_data
            done = completed_count + error_count
            print(f"  [{probe_num:3d}] {status} | aktiv: {active_count - 1} | {done}/{NUM_PROBES} fertig")
            sys.stdout.flush()

    except Exception as e:
        elapsed = time.time() - start_time
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "probe_num": probe_num, "task": task_text,
                "status": "error", "error": str(e),
                "duration_seconds": round(elapsed, 1),
            }, f, ensure_ascii=False, indent=2)
        with lock:
            error_count += 1
            done = completed_count + error_count
            print(f"  [{probe_num:3d}] EXCEPTION: {e} | {done}/{NUM_PROBES} fertig")
            sys.stdout.flush()

    finally:
        with lock:
            active_count -= 1
        semaphore.release()


def main():
    global NUM_PROBES, MAX_CONCURRENT, TIMEOUT_SECONDS, semaphore
    args = parse_cli()
    NUM_PROBES = args.probes
    MAX_CONCURRENT = args.max_concurrent
    TIMEOUT_SECONDS = args.timeout
    semaphore = threading.Semaphore(MAX_CONCURRENT)
    require_explicit_opt_in()
    validate_total_budget(NUM_PROBES, args.max_total_budget_usd)
    RESULTS_DIR.mkdir(exist_ok=True)

    print(f"{'='*60}")
    print(f"  ELEPHANT PATH EXPERIMENT v6.1 - POST-SCHILDER-TEST")
    print(f"  {NUM_PROBES} {MODEL.title()}, max {MAX_CONCURRENT} parallel")
    print(f"  Timeout: {TIMEOUT_SECONDS}s, Ziel: {TARGET_PATH}")
    print("  Naive Mode: Claude --safe-mode, nur Glob/Grep/Read")
    print(f"  Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Output: {RESULTS_DIR}")
    print(f"{'='*60}")
    print()

    experiment_start = time.time()

    # Alle Threads sofort starten (Semaphore regelt Parallelitaet)
    print(f"  Starte {NUM_PROBES} Threads (Semaphore limitiert auf {MAX_CONCURRENT} gleichzeitig)...")
    threads = []
    for i in range(1, NUM_PROBES + 1):
        task_idx = (i - 1) % len(TASKS)
        task_text = TASKS[task_idx]
        t = threading.Thread(target=run_probe, args=(i, task_text), daemon=True)
        t.start()
        threads.append(t)

    print(f"  {NUM_PROBES} Threads erstellt.")
    print()

    # Auf alle Ergebnisse warten
    print(f"  Warte auf Ergebnisse...")
    for t in threads:
        t.join(timeout=TIMEOUT_SECONDS + 60)

    experiment_elapsed = time.time() - experiment_start

    # Zusammenfassung
    experiment = {
        "name": "Elephant Path / Trampelpfadanalyse - POST-SCHILDER",
        "version": "6.1",
        "mode": "naive-post-signs",
        "naive_setup": {
            "memory_cleared": False,
            "safe_mode": True,
            "tools_restricted": "Glob,Grep,Read",
            "mcp_disabled": True,
            "skills_disabled": True,
        },
        "target_path": TARGET_PATH,
        "start_time": datetime.fromtimestamp(experiment_start).isoformat(),
        "end_time": datetime.now().isoformat(),
        "wall_clock_seconds": round(experiment_elapsed, 1),
        "num_probes": NUM_PROBES,
        "completed": completed_count,
        "errors": error_count,
        "model": MODEL,
        "tasks": TASKS,
        "probes": [
            {
                "num": num,
                "status": r.get("status"),
                "duration": r.get("duration_seconds", 0),
                "turns": r.get("num_turns"),
                "paths_found": len(r.get("visited_paths", [])),
                "cost": r.get("total_cost_usd"),
                "stdout_bytes": r.get("stdout_bytes", 0),
            }
            for num, r in sorted(results.items())
        ],
    }

    with open(RESULTS_DIR / "experiment.json", "w", encoding="utf-8") as f:
        json.dump(experiment, f, ensure_ascii=False, indent=2)

    total_paths = sum(len(r.get("visited_paths", [])) for r in results.values())
    total_cost = sum(r.get("total_cost_usd", 0) for r in results.values())
    total_stdout = sum(r.get("stdout_bytes", 0) for r in results.values())
    print()
    print(f"{'='*60}")
    print(f"  FERTIG!")
    print(f"  Dauer:        {experiment_elapsed/60:.1f} min")
    print(f"  Completed:    {completed_count}")
    print(f"  Errors:       {error_count}")
    print(f"  Pfade total:  {total_paths}")
    print(f"  Kosten:       ${total_cost:.2f}")
    print(f"  Stdout total: {total_stdout:,} Bytes")
    print(f"  Ergebnisse:   {RESULTS_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
