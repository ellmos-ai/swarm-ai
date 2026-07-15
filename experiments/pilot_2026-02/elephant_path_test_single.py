#!/usr/bin/env python3
"""Historical single-probe launcher with explicit, read-only opt-in."""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Historical single read-only probe")
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--max-total-budget-usd", type=float, required=True)
    args = parser.parse_args()
    if (not math.isfinite(args.max_total_budget_usd) or
            args.max_total_budget_usd <= 0):
        parser.error("--max-total-budget-usd must be positive and finite")
    if os.getenv("SWARM_ENABLE_LEGACY_EXPERIMENTS") != "I_UNDERSTAND":
        raise SystemExit(
            "Historical experiment disabled. Set "
            "SWARM_ENABLE_LEGACY_EXPERIMENTS=I_UNDERSTAND explicitly."
        )
    target_value = os.getenv("SWARM_EXPERIMENT_TARGET", "")
    target = Path(target_value).expanduser()
    if not target_value or not target.is_dir() or target.resolve().parent == target.resolve():
        raise SystemExit("SWARM_EXPERIMENT_TARGET must name an existing non-root directory")
    try:
        budget = float(os.getenv("SWARM_EXPERIMENT_MAX_BUDGET_USD_PER_AGENT", ""))
    except ValueError as exc:
        raise SystemExit(
            "SWARM_EXPERIMENT_MAX_BUDGET_USD_PER_AGENT must be a positive number"
        ) from exc
    if not math.isfinite(budget) or budget <= 0:
        raise SystemExit(
            "SWARM_EXPERIMENT_MAX_BUDGET_USD_PER_AGENT must be a positive number"
        )
    if budget > args.max_total_budget_usd:
        raise SystemExit(
            f"per-agent cap ${budget:.2f} is above the run budget "
            f"${args.max_total_budget_usd:.2f}"
        )

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env["PYTHONIOENCODING"] = "utf-8"
    prompt = (
        f"Explore the directory {target.resolve()} read-only. List its top-level "
        "directories and the files you read. Use at most four steps."
    )
    cmd = [
        "claude", "-p", "--model", "haiku", "--verbose",
        "--max-budget-usd", str(budget),
        "--permission-mode", "dontAsk", "--no-session-persistence",
        "--safe-mode", "--disallowedTools", "mcp__*",
        "--tools", "Glob,Grep,Read",
        "--allowedTools", "Glob", "Grep", "Read",
        "--output-format", "stream-json",
        prompt,
    ]
    started = time.time()
    result = subprocess.run(
        cmd, capture_output=True, timeout=120, env=env, cwd=str(target.resolve())
    )
    output_dir = Path(__file__).parent / "results" / "single_probe"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "stdout.jsonl").write_bytes(result.stdout)
    (output_dir / "stderr.txt").write_bytes(result.stderr)
    tool_count = 0
    for line in result.stdout.decode("utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for block in event.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_count += 1
    print(
        f"Return code: {result.returncode}; duration: {time.time() - started:.1f}s; "
        f"tool calls: {tool_count}"
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
