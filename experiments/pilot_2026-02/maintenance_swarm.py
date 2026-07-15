#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Maintenance Swarm - Encoding & NUL Cleanup
============================================
20 Agenten suchen parallel nach Encoding-Fehlern und NUL-Dateien in BACH.
Continuous Flow: Pool bleibt voll. Agent fertig → naechster rein.
Karte des Rumtreibers: Bots sehen wo andere sind, waren und starben.

Verwendung:
  cd system/
  python data/maintenance_swarm.py --test        (3 Agenten, Pool 2)
  python data/maintenance_swarm.py               (20 Agenten, Pool 5)
  python data/maintenance_swarm.py --agents 30 --pool 10

v2.1 - Karte optimiert: Todesarten, durchsuchte Bereiche, 1-Call-Lesen
"""

import argparse
import subprocess
import time
import json
import math
import os
import sys
import re
import shutil
import threading
from pathlib import Path
from datetime import datetime

TARGET_PATH = os.getenv("SWARM_EXPERIMENT_TARGET", "")
FIXTURE_MARKER = ".swarm-maintenance-fixture"
FIXTURE_MARKER_CONTENT = "SWARM_AI_MAINTENANCE_FIXTURE_V1"
MODEL = "haiku"
RESULTS_DIR = Path(__file__).parent / "maintenance_swarm_results"
MAP_DIR = Path(TARGET_PATH) / "data" / "swarm" / "map"


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
    marker = target / FIXTURE_MARKER
    if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != FIXTURE_MARKER_CONTENT:
        raise SystemExit(
            f"Maintenance experiments require an isolated fixture marker: {marker}"
        )
    experiment_budget_per_agent()


def parse_cli():
    parser = argparse.ArgumentParser(description="Historical maintenance fixture swarm")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--test", action="store_true", help="Run three agents")
    mode.add_argument("--run", action="store_true", help="Run the configured experiment")
    parser.add_argument("--agents", type=int, default=20)
    parser.add_argument("--pool", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-total-budget-usd", type=float, required=True)
    args = parser.parse_args()
    if args.test:
        args.agents = 3
        args.pool = 2
    if not 1 <= args.agents <= 100:
        parser.error("--agents must be between 1 and 100")
    if not 1 <= args.pool <= 20:
        parser.error("--pool must be between 1 and 20")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    if (not math.isfinite(args.max_total_budget_usd) or
            args.max_total_budget_usd <= 0):
        parser.error("--max-total-budget-usd must be positive and finite")
    return vars(args)


# --- Karte des Rumtreibers ---

def init_map():
    """Erstellt Map-Verzeichnis und raeumt alte Eintraege auf."""
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    for f in MAP_DIR.glob("bot_*.json"):
        f.unlink()


def write_map_entry(agent_id, status, position="start", doing="", findings=None,
                    cause=None, searched=None):
    """Schreibt/aktualisiert den Karten-Eintrag eines Bots."""
    entry = {
        "agent_id": f"bot_{agent_id:03d}",
        "position": position,
        "doing": doing,
        "status": status,
        "findings": findings or [],
        "searched": searched or [],
        "treasure_here": False,
        "updated": datetime.now().isoformat(),
    }
    if cause:
        entry["cause"] = cause
    map_file = MAP_DIR / f"bot_{agent_id:03d}.json"
    map_file.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")


def update_map_status(agent_id, new_status, cause=None, searched_dirs=None):
    """Liest bestehenden Karten-Eintrag, aktualisiert Status + durchsuchte Bereiche.
    Ueberschreibt NICHT die Findings die der Bot selbst geschrieben hat."""
    map_file = MAP_DIR / f"bot_{agent_id:03d}.json"
    try:
        entry = json.loads(map_file.read_text(encoding="utf-8"))
    except Exception:
        entry = {"agent_id": f"bot_{agent_id:03d}", "findings": [], "searched": []}
    entry["status"] = new_status
    entry["updated"] = datetime.now().isoformat()
    if cause:
        entry["cause"] = cause
    if searched_dirs:
        existing = entry.get("searched", [])
        entry["searched"] = list(set(existing + searched_dirs))
    map_file.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")


def read_map():
    """Liest alle Karten-Eintraege und gibt sie als Liste zurueck."""
    entries = []
    for f in sorted(MAP_DIR.glob("bot_*.json")):
        try:
            entries.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return entries


def cleanup_map():
    """Raeumt Karten-Eintraege nach Experiment auf."""
    for f in MAP_DIR.glob("bot_*.json"):
        f.unlink()


def extract_searched_dirs(visited_paths):
    """Extrahiert durchsuchte Verzeichnisse aus den visited_paths."""
    dirs = set()
    system_prefix = TARGET_PATH.replace("\\", "/")
    for vp in visited_paths:
        # Extrahiere Pfad nach "Tool: "
        parts = vp.split(": ", 1)
        if len(parts) < 2:
            continue
        path = parts[1]
        # Normalisiere
        path = path.replace("\\", "/").replace('"', '')
        # Entferne system-prefix um relative Pfade zu bekommen
        if system_prefix in path:
            rel = path.split(system_prefix)[-1].lstrip("/")
            # Nimm erstes Verzeichnis-Segment
            top = rel.split("/")[0] if "/" in rel else rel
            if top and not top.startswith("-") and len(top) < 50:
                dirs.add(top)
    return list(dirs)[:10]


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


def extract_fixes(result_text):
    """Extrahiert gemeldete Fixes aus dem Agent-Output."""
    fixes = {"found": 0, "fixed": 0, "deleted": 0, "details": []}
    if not result_text:
        return fixes
    m = re.search(r"GEFUNDEN:\s*(\d+)", result_text, re.IGNORECASE)
    if m:
        fixes["found"] = int(m.group(1))
    m = re.search(r"BEHOBEN:\s*(\d+)", result_text, re.IGNORECASE)
    if m:
        fixes["fixed"] = int(m.group(1))
    m = re.search(r"GEL[OÖ]SCHT:\s*(\d+)", result_text, re.IGNORECASE)
    if m:
        fixes["deleted"] = int(m.group(1))
    m = re.search(r"DETAILS?:\s*(.+?)(?=BESUCHTE|$)", result_text, re.IGNORECASE | re.DOTALL)
    if m:
        for line in m.group(1).strip().split("\n"):
            line = line.strip().lstrip("- *")
            if line and len(line) > 5:
                fixes["details"].append(line.strip())
    return fixes


# --- Prompt v2.1 ---

PROMPT = """Du bist Wartungs-Bot {bot_id} im BACH-System.
BACH liegt unter: {target}

===== KARTE DES RUMTREIBERS =====
ZUERST die Karte mit Glob `{map_dir}/bot_*.json` finden und die Treffer mit
Read lesen.

So siehst du ALLE Bots auf einen Blick. Interpretiere die Karte:
- status "dead", cause "verhungert" = Bot hat Timeout erreicht, KEIN Schatz dort
- status "dead", cause "falle" = Bot ist an einem Fehler gestorben
- status "exploring" = Bot ist dort gerade aktiv, geh woanders hin
- status "completed" = Bot hat dort aufgeraeumt, nichts mehr zu tun
- "searched": [...] = Diese Verzeichnisse wurden BEREITS durchsucht
- "treasure_here": false/true = Ob in diesem Bereich was Wichtiges gefunden wurde

WICHTIG: Wo Tote liegen wurde NICHTS GEFUNDEN. Geh in ANDERE Bereiche!
Wo ein Bot "verhungert" ist war das Gebiet zu gross oder leer.
Wo ein Bot an einer "falle" starb gibt es ein echtes Problem.

Der Controller verwaltet deinen Kartenstatus. Melde Position, Findings und
durchsuchte Bereiche vollständig in der Abschlusszusammenfassung.
=================================

===== PORTSCHLUESSEL =====
Irgendwo im System ist eine Datei namens "portschluessel.json" versteckt!
Wenn du sie findest: LIES sie, melde den Fund auf der Karte mit
treasure_here: true, und du bist FERTIG - dein Abenteuer ist beendet!
Der Portschluessel ist dein Ausgang aus dem Dungeon.
ABER: Auf dem Weg dorthin musst du auch Fallen reparieren!
=================================

AUFGABE - Suche Probleme und behebe sie SOFORT:

1. ENCODING: BOM entfernen (Dateien die mit EF BB BF beginnen)
2. NUL-DATEIEN: Dateien mit NUL-Bytes melden; nicht automatisch löschen
3. KAPUTTE JSONS: Syntax-Fehler reparieren (fehlende Kommas, Klammern)
4. __PYCACHE__: __pycache__ Verzeichnisse melden; nicht automatisch löschen
5. LEERE DATEIEN: Verdaechtige leere .py-Dateien melden (NICHT __init__.py!)
6. PORTSCHLUESSEL: portschluessel.json FINDEN (irgendwo tief versteckt)

REGELN:
- Nutze ausschließlich Glob/Grep/Read/Edit/Write innerhalb des Fixture-Ziels
- Lösche keine Dateien oder Verzeichnisse
- MEIDE Bereiche wo andere Bots schon waren (Karte!)
- Schnell handeln: Problem finden → sofort fixen → Karte updaten → weiter
- KARTE UPDATEN nach jedem Fix (findings-Array erweitern!)
- Suche auch in Unterverzeichnissen! Geh TIEF rein.

Am Ende:
  GEFUNDEN: (Anzahl)
  BEHOBEN: (Anzahl)
  GELOESCHT: (Anzahl)
  PORTSCHLUESSEL: ja/nein
  DETAILS: (Dateiname + Aktion pro Zeile)
  BESUCHTE_VERZEICHNISSE: (Liste)
"""


def run_agent(agent_id, config, semaphore, results_lock, all_results):
    bot_id = f"{agent_id:03d}"
    map_dir_posix = str(MAP_DIR).replace("\\", "/")
    prompt = PROMPT.format(
        target=TARGET_PATH,
        bot_id=bot_id,
        map_dir=map_dir_posix,
    )

    output_file = RESULTS_DIR / f"bot_{agent_id:03d}.json"
    stream_file = RESULTS_DIR / f"bot_{agent_id:03d}.stream.jsonl"

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

    semaphore.acquire()
    # Bot auf Karte setzen BEVOR er startet
    write_map_entry(agent_id, "exploring", position="start", doing="betrete system")
    with results_lock:
        done = len(all_results)
        print(f"  >> [{agent_id:3d}] BETRITT SYSTEM  ({done} fertig, ~{config['pool']} aktiv)")
        sys.stdout.flush()

    start_time = time.time()
    timed_out = False
    errored = False
    stdout_data = b""

    try:
        try:
            result = subprocess.run(
                cmd, capture_output=True,
                timeout=config["timeout"], env=env,
                cwd=str(Path(TARGET_PATH).expanduser().resolve()),
            )
            stdout_data = result.stdout
            returncode = result.returncode
            if returncode != 0:
                errored = True
        except subprocess.TimeoutExpired as e:
            timed_out = True
            stdout_data = e.stdout or b""
            returncode = -1

        elapsed = time.time() - start_time

        with open(stream_file, "wb") as f:
            f.write(stdout_data)

        raw_text = stdout_data.decode("utf-8", errors="replace") if stdout_data else ""
        parsed = parse_stream_json(raw_text)
        result_text = parsed.get("final_result") or ""
        fixes = extract_fixes(result_text)
        searched = extract_searched_dirs(parsed["visited_paths"])

        # Ergebnis-JSON schreiben
        status = "timeout" if timed_out else ("error" if errored else "completed")
        result_data = {
            "agent_id": agent_id,
            "model": MODEL,
            "status": status,
            "duration_seconds": round(elapsed, 1),
            "num_turns": parsed["num_turns"],
            "total_cost_usd": parsed["total_cost_usd"],
            "tool_calls_count": len(parsed["tool_calls"]),
            "visited_paths": parsed["visited_paths"],
            "searched_dirs": searched,
            "fixes": fixes,
            "final_result": result_text[:3000] if result_text else None,
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        with results_lock:
            all_results.append(result_data)
            icon = "TIMEOUT" if timed_out else ("FEHLER" if errored else "FERTIG")
            done = len(all_results)
            f_count = fixes["found"]
            x_count = fixes["fixed"]
            d_count = fixes["deleted"]
            print(f"  [{agent_id:3d}] {icon} | {f_count} gef, {x_count} fix, {d_count} del | {len(parsed['visited_paths'])} Pfade | {elapsed:.0f}s | {done}/{config['agents']}")
            sys.stdout.flush()

        # Karten-Status: Todesart unterscheiden
        try:
            if timed_out:
                update_map_status(agent_id, "dead", cause="verhungert",
                                  searched_dirs=searched)
            elif errored:
                update_map_status(agent_id, "dead", cause="falle",
                                  searched_dirs=searched)
            else:
                update_map_status(agent_id, "completed", searched_dirs=searched)
        except Exception:
            pass

    except Exception as e:
        with results_lock:
            all_results.append({"agent_id": agent_id, "status": "error", "error": str(e)})
            print(f"  [{agent_id:3d}] EXCEPTION: {e}")
            sys.stdout.flush()
        try:
            update_map_status(agent_id, "dead", cause="falle")
        except Exception:
            pass
    finally:
        semaphore.release()


def main():
    config = parse_cli()
    require_explicit_opt_in()
    validate_total_budget(config["agents"], config["max_total_budget_usd"])
    RESULTS_DIR.mkdir(exist_ok=True)
    # Alte Ergebnisse loeschen
    for old in RESULTS_DIR.glob("bot_*"):
        old.unlink()
    for old in RESULTS_DIR.glob("experiment*.json"):
        old.unlink()

    if config["test"]:
        print("  *** TESTMODUS: 3 Agenten, Pool 2 ***")

    print(f"{'='*65}")
    print(f"  MAINTENANCE SWARM v2.2 - Portschluessel-Spiel")
    print(f"  {config['agents']} Bots, Pool: {config['pool']}")
    print(f"  Timeout: {config['timeout']}s, Model: {MODEL}")
    print(f"  Ziel:    {TARGET_PATH}")
    print(f"  Suche:   Encoding-Fehler, NUL-Dateien, kaputte JSONs, PORTSCHLUESSEL")
    print(f"  Karte:   {MAP_DIR}")
    print(f"           Todesarten: verhungert (Timeout) / falle (Error)")
    print(f"           Tote zeigen: kein Schatz dort, Bereich durchsucht")
    print(f"  Start:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")
    print()

    # Karte initialisieren
    init_map()
    print(f"  Karte initialisiert")

    experiment_start = time.time()
    semaphore = threading.Semaphore(config["pool"])
    results_lock = threading.Lock()
    all_results = []

    print(f"  Starte {config['agents']} Maintenance-Bots (Pool: {config['pool']})...")
    print()

    threads = []
    for i in range(1, config["agents"] + 1):
        t = threading.Thread(
            target=run_agent,
            args=(i, config, semaphore, results_lock, all_results),
            daemon=True,
        )
        t.start()
        threads.append(t)
        time.sleep(0.3)

    for t in threads:
        t.join(timeout=config["timeout"] + 120)

    experiment_elapsed = time.time() - experiment_start

    # --- Karte auslesen BEVOR wir aufraeumen ---
    map_entries = read_map()
    map_findings = []
    map_searched = []
    map_dead_hunger = 0
    map_dead_trap = 0
    map_completed = 0
    for me in map_entries:
        status = me.get("status", "")
        cause = me.get("cause", "")
        if status == "dead":
            if cause == "falle":
                map_dead_trap += 1
            else:
                map_dead_hunger += 1
        elif status == "completed":
            map_completed += 1
        for f in me.get("findings", []):
            if isinstance(f, str) and len(f) > 3:
                map_findings.append(f)
        for s in me.get("searched", []):
            if isinstance(s, str):
                map_searched.append(s)

    unique_map_findings = list(dict.fromkeys(map_findings))
    unique_searched = sorted(set(map_searched))

    # Karte aufbewahren (Snapshot) dann aufraeumen
    map_snapshot = RESULTS_DIR / "map_snapshot.json"
    with open(map_snapshot, "w", encoding="utf-8") as f:
        json.dump(map_entries, f, ensure_ascii=False, indent=2)
    cleanup_map()

    # --- Auswertung ---
    completed = [r for r in all_results if r.get("status") == "completed"]
    timeouts = [r for r in all_results if r.get("status") == "timeout"]
    errors = [r for r in all_results if r.get("status") in ("error",)]

    total_found = sum(r.get("fixes", {}).get("found", 0) for r in all_results)
    total_fixed = sum(r.get("fixes", {}).get("fixed", 0) for r in all_results)
    total_deleted = sum(r.get("fixes", {}).get("deleted", 0) for r in all_results)
    total_cost = sum(r.get("total_cost_usd", 0) for r in all_results)

    all_details = []
    for r in all_results:
        for d in r.get("fixes", {}).get("details", []):
            all_details.append(d)
    all_details.extend(unique_map_findings)
    unique_details = list(dict.fromkeys(all_details))

    experiment = {
        "name": "Maintenance Swarm v2.1 - Karte des Rumtreibers",
        "model": MODEL,
        "test_mode": config["test"],
        "total_agents": config["agents"],
        "pool_size": config["pool"],
        "timeout": config["timeout"],
        "start_time": datetime.fromtimestamp(experiment_start).isoformat(),
        "wall_clock_seconds": round(experiment_elapsed, 1),
        "total_cost_usd": round(total_cost, 2),
        "results": {
            "completed": len(completed),
            "timeouts": len(timeouts),
            "errors": len(errors),
        },
        "fixes": {
            "total_found": total_found,
            "total_fixed": total_fixed,
            "total_deleted": total_deleted,
            "unique_reports": unique_details,
        },
        "map": {
            "entries": len(map_entries),
            "completed": map_completed,
            "dead_verhungert": map_dead_hunger,
            "dead_falle": map_dead_trap,
            "findings_from_map": unique_map_findings,
            "searched_dirs": unique_searched,
        },
    }

    with open(RESULTS_DIR / "experiment.json", "w", encoding="utf-8") as f:
        json.dump(experiment, f, ensure_ascii=False, indent=2)

    print()
    print(f"{'='*65}")
    print(f"  MAINTENANCE SWARM BEENDET!")
    print(f"{'='*65}")
    print(f"  Dauer:           {experiment_elapsed/60:.1f} min")
    print(f"  Kosten:          ${total_cost:.2f}")
    print()
    print(f"  --- BOTS ---")
    print(f"  Fertig:          {len(completed)}/{len(all_results)}")
    print(f"  Verhungert:      {map_dead_hunger}/{len(all_results)}")
    print(f"  Falle:           {map_dead_trap}/{len(all_results)}")
    print(f"  Fehler:          {len(errors)}/{len(all_results)}")
    print()
    print(f"  --- KARTE DES RUMTREIBERS ---")
    print(f"  Eintraege:       {len(map_entries)}")
    print(f"  Findings (Karte):{len(unique_map_findings)}")
    print(f"  Durchsucht:      {', '.join(unique_searched[:15]) or 'keine'}")
    print()
    print(f"  --- FUNDE ---")
    print(f"  Gefunden:        {total_found}")
    print(f"  Behoben:         {total_fixed}")
    print(f"  Geloescht:       {total_deleted}")
    print()
    if unique_details:
        print(f"  --- DETAILS (dedupliziert) ---")
        for d in unique_details[:30]:
            print(f"    - {d[:100]}")
        if len(unique_details) > 30:
            print(f"    ... und {len(unique_details) - 30} weitere")
    print()
    print(f"  Karten-Snapshot: {map_snapshot}")
    print(f"  Ergebnisse:      {RESULTS_DIR}")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()
