#!/usr/bin/env python3
"""Initialize the standalone stigmergy database schema."""
from __future__ import annotations

import argparse

try:
    from .stigmergy_api import StigmergyAPI
except ImportError:  # Direct script execution.
    from stigmergy_api import StigmergyAPI


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db_path", help="SQLite database path")
    parser.add_argument(
        "--no-migrate-legacy", action="store_true",
        help="Do not import legacy shared_memory_working pheromones",
    )
    args = parser.parse_args()
    api = StigmergyAPI(
        args.db_path,
        strict=True,
        migrate_legacy=not args.no_migrate_legacy,
    )
    print(f"Initialized {api.TABLE} in {api.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
