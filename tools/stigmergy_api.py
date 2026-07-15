"""SQLite-backed stigmergic coordination for swarm agents.

The API owns a small standalone table and initializes it on first use.  Older
``shared_memory_working`` pheromones are imported idempotently when present.
"""
from __future__ import annotations

import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_rank(value: object) -> float:
    """Normalize legacy ISO timestamps for deterministic migration ordering."""
    if not isinstance(value, str) or not value.strip():
        return float("-inf")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return float("-inf")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


class StigmergyAPI:
    """Coordinate agents through ranked, persistent pheromone records."""

    NAMESPACE = "stigmergy"
    TABLE = "swarm_pheromones"
    LEGACY_TABLE = "shared_memory_working"

    def __init__(self, db_path: str, agent_id: str = "anonymous", *,
                 strict: bool = False, migrate_legacy: bool = True):
        if not str(db_path).strip():
            raise ValueError("db_path must not be empty")
        if str(db_path).strip() == ":memory:":
            raise ValueError(":memory: is not supported; use a file-backed SQLite path")
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("agent_id must be a non-empty string")
        self.db_path = str(db_path)
        self.agent_id = agent_id.strip()
        self.strict = strict
        self.last_error: Optional[str] = None
        self.initialize_schema(migrate_legacy=migrate_legacy)

    def _connect(self) -> sqlite3.Connection:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Commit or roll back a transaction and always close the handle."""
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _failure(self, exc: Exception, default):
        self.last_error = f"{type(exc).__name__}: {exc}"
        if self.strict:
            raise exc
        return default

    def initialize_schema(self, *, migrate_legacy: bool = True) -> None:
        """Create the standalone schema and optionally import legacy records."""
        with self._connection() as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE} (
                    path_id TEXT PRIMARY KEY,
                    strength REAL NOT NULL CHECK(strength >= 0 AND strength <= 1),
                    metadata_json TEXT NOT NULL DEFAULT '{{}}',
                    agent_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))
                )
            """)
            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.TABLE}_ranking
                ON {self.TABLE}(is_active, strength DESC, updated_at DESC)
            """)
            if migrate_legacy:
                self._migrate_legacy(conn)

    def _migrate_legacy(self, conn: sqlite3.Connection) -> int:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (self.LEGACY_TABLE,),
        ).fetchone()
        if not exists:
            return 0
        columns = {
            row["name"] for row in conn.execute(
                f"PRAGMA table_info({self.LEGACY_TABLE})"
            ).fetchall()
        }
        if not {"content", "is_active"}.issubset(columns):
            return 0
        candidates = {}
        for row in conn.execute(
            f"SELECT rowid AS legacy_rowid, content FROM {self.LEGACY_TABLE} "
            "WHERE is_active = 1 ORDER BY rowid ASC"
        ).fetchall():
            try:
                data = json.loads(row["content"])
                if data.get("namespace") != self.NAMESPACE:
                    continue
                path_id = str(data["path_id"]).strip()
                if not path_id:
                    continue
                strength = float(data.get("strength", 1))
                if not math.isfinite(strength):
                    continue
                strength = max(0.0, min(1.0, strength))
                metadata = data.get("metadata") or {}
                if not isinstance(metadata, dict):
                    continue
                metadata_json = json.dumps(metadata, ensure_ascii=False)
                agent_id = str(data.get("agent_id") or "legacy")
                legacy_timestamp = data.get("timestamp")
                timestamp = (
                    legacy_timestamp.strip()
                    if isinstance(legacy_timestamp, str) and legacy_timestamp.strip()
                    else _utc_now()
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            rank = (_timestamp_rank(legacy_timestamp), strength, row["legacy_rowid"])
            current = candidates.get(path_id)
            if current is None or rank > current[0]:
                candidates[path_id] = (
                    rank,
                    (path_id, strength, metadata_json, agent_id, timestamp, timestamp),
                )

        migrated = 0
        for path_id in sorted(candidates):
            params = candidates[path_id][1]
            cursor = conn.execute(f"""
                INSERT INTO {self.TABLE}
                    (path_id, strength, metadata_json, agent_id, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(path_id) DO NOTHING
            """, params)
            migrated += cursor.rowcount
        return migrated

    @staticmethod
    def _validate_path(path_id: str) -> str:
        if not isinstance(path_id, str) or not path_id.strip():
            raise ValueError("path_id must be a non-empty string")
        return path_id.strip()

    def deposit(self, path_id: str, strength: float = 1.0,
                metadata: Optional[dict] = None) -> bool:
        """Atomically create or update one pheromone."""
        try:
            path_id = self._validate_path(path_id)
            strength = float(strength)
            if not math.isfinite(strength):
                raise ValueError("strength must be finite")
            strength = max(0.0, min(1.0, strength))
            if metadata is not None and not isinstance(metadata, dict):
                raise TypeError("metadata must be a dictionary")
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
            now = _utc_now()
            with self._connection() as conn:
                conn.execute(f"""
                    INSERT INTO {self.TABLE}
                        (path_id, strength, metadata_json, agent_id, created_at, updated_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(path_id) DO UPDATE SET
                        strength = excluded.strength,
                        metadata_json = excluded.metadata_json,
                        agent_id = excluded.agent_id,
                        updated_at = excluded.updated_at,
                        is_active = 1
                """, (path_id, strength, metadata_json, self.agent_id, now, now))
            self.last_error = None
            return True
        except Exception as exc:
            return self._failure(exc, False)

    def sense(self, path_prefix: str = "") -> list[dict]:
        """Return active pheromones ordered by strength and recency."""
        try:
            if not isinstance(path_prefix, str):
                raise TypeError("path_prefix must be a string")
            escaped = (path_prefix.replace("\\", "\\\\")
                       .replace("%", "\\%")
                       .replace("_", "\\_"))
            with self._connection() as conn:
                rows = conn.execute(f"""
                    SELECT path_id, strength, metadata_json, agent_id, created_at, updated_at
                    FROM {self.TABLE}
                    WHERE is_active = 1 AND path_id LIKE ? ESCAPE '\\'
                    ORDER BY strength DESC, updated_at DESC, path_id ASC
                """, (f"{escaped}%",)).fetchall()
            results = []
            for row in rows:
                try:
                    metadata = json.loads(row["metadata_json"])
                except (TypeError, json.JSONDecodeError):
                    metadata = {}
                results.append({
                    "path_id": row["path_id"],
                    "strength": row["strength"],
                    "agent_id": row["agent_id"],
                    "metadata": metadata,
                    "timestamp": row["updated_at"] or row["created_at"],
                })
            self.last_error = None
            return results
        except Exception as exc:
            return self._failure(exc, [])

    def evaporate(self, decay_rate: float = 0.1) -> int:
        """Deactivate the weakest fraction; a zero rate is a true no-op."""
        try:
            decay_rate = float(decay_rate)
            if not math.isfinite(decay_rate):
                raise ValueError("decay_rate must be finite")
            decay_rate = max(0.0, min(1.0, decay_rate))
            if decay_rate == 0:
                return 0
            with self._connection() as conn:
                # Reserve the writer slot before COUNT/SELECT so a concurrent
                # deposit cannot invalidate a WAL read transaction upgrade.
                conn.execute("BEGIN IMMEDIATE")
                total = conn.execute(
                    f"SELECT COUNT(*) FROM {self.TABLE} WHERE is_active = 1"
                ).fetchone()[0]
                if total == 0:
                    return 0
                to_delete = min(total, math.ceil(total * decay_rate))
                rows = conn.execute(f"""
                    SELECT path_id FROM {self.TABLE}
                    WHERE is_active = 1
                    ORDER BY strength ASC, updated_at ASC, path_id ASC
                    LIMIT ?
                """, (to_delete,)).fetchall()
                ids = [row["path_id"] for row in rows]
                conn.executemany(f"""
                    UPDATE {self.TABLE} SET is_active = 0, updated_at = ?
                    WHERE path_id = ?
                """, [(_utc_now(), path_id) for path_id in ids])
            self.last_error = None
            return len(ids)
        except Exception as exc:
            return self._failure(exc, 0)

    def get_best_path(self, path_prefix: str = "") -> Optional[str]:
        results = self.sense(path_prefix)
        return results[0]["path_id"] if results else None

    def dump(self) -> dict:
        return {
            item["path_id"]: {
                "strength": item["strength"],
                "agent_id": item["agent_id"],
                "metadata": item["metadata"],
                "timestamp": item["timestamp"],
            }
            for item in self.sense()
        }


def deposit_pheromone(db_path: str, agent_id: str, path_id: str,
                      strength: float = 1.0,
                      metadata: Optional[dict] = None) -> bool:
    return StigmergyAPI(db_path, agent_id).deposit(path_id, strength, metadata)


def sense_pheromones(db_path: str, path_prefix: str = "") -> list[dict]:
    return StigmergyAPI(db_path).sense(path_prefix)


def get_best_pheromone_path(db_path: str, path_prefix: str = "") -> Optional[str]:
    return StigmergyAPI(db_path).get_best_path(path_prefix)
