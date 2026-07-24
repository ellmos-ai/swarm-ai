#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parallel-Chunks Stufe 3: LLM-Zusammenfassungen für Chunks
Wissensindexierung

Zweck:
- Lädt alle Chunks aus document_chunks (ohne Summary)
- Generiert LLM-Zusammenfassungen via Claude API (Anthropic SDK)
- Speichert Summaries zurück in DB
- Protokolliert Run in parallel_chunks_runs
- Token-Tracking für Kosten-Schätzung

Usage:
    python summarize_chunks.py [--model haiku|sonnet] [--batch-size 10] [--dry-run]

Author: Lukas Geiger (ellmos-ai)
"""

import argparse
import math
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import anthropic

try:
    import anthropic  # noqa: F811
except ImportError:
    anthropic = None  # noqa: F811

# --- Konstanten ---

SCRIPT_DIR = Path(__file__).parent
SYSTEM_DIR = SCRIPT_DIR.parent
DB_PATH = Path(os.getenv("SWARM_DB_PATH", str(SYSTEM_DIR / "data" / "swarm.db")))

MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-5",
}

# Kosten pro 1M Tokens (USD) - Stand 2025
COST_PER_1M = {
    "haiku": {"input": 1.00, "output": 5.00},
    "sonnet": {"input": 3.00, "output": 15.00},
}

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0
CLAIM_TTL_SECONDS = 86400
MAX_LIMIT = 1000
MAX_CHUNK_BYTES = 100_000
MAX_TOTAL_CHUNK_BYTES = 1_000_000

SYSTEM_PROMPT = (
    "Du bist ein Experte für Textzusammenfassungen in einem Wissensmanagement-System. "
    "Deine Aufgabe ist es, Text-Chunks präzise zusammenzufassen.\n\n"
    "REGELN:\n"
    "- Fasse den Text in 2-3 Sätzen zusammen\n"
    "- Fokus: Kernaussage, wichtigste Konzepte, technische Details\n"
    "- Behalte Fachbegriffe und technische Terme bei\n"
    "- Schreibe in der Sprache des Originals (meist Deutsch oder Englisch)\n"
    "- Keine Einleitungen wie 'Der Text handelt von...'\n"
    "- Direkt und informativ formulieren\n"
    "- Gib NUR die Zusammenfassung zurück, keine Erklärungen"
)


def get_api_key() -> str:
    """Load the Anthropic API key after checking the optional SDK."""
    if anthropic is None:
        raise RuntimeError("anthropic SDK not installed: pip install anthropic")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print("[INFO] API-Key aus Umgebungsvariable geladen")
        return api_key

    raise ValueError(
        "ANTHROPIC_API_KEY nicht konfiguriert!\n\n"
        "Setze die Umgebungsvariable:\n"
        "  export ANTHROPIC_API_KEY=sk-ant-api03-..."
    )


class ChunkSummarizer:
    """LLM-basierte Chunk-Zusammenfassung via Claude API."""

    def __init__(self, model: str = "haiku", db_path: Path = DB_PATH):
        """
        Initialisiert den ChunkSummarizer.

        Args:
            model: LLM-Modell ("haiku" oder "sonnet")
            db_path: Pfad zur Datenbank
        """
        if model not in MODELS:
            raise ValueError(f"unknown model profile: {model}")
        self.model = model
        self.model_id = MODELS[model]
        self.db_path = Path(db_path)
        self.client = None  # Lazy init bei run()
        self.run_id = None
        self.stats = self._empty_stats()

    @staticmethod
    def _empty_stats():
        return {
            'chunks_processed': 0,
            'chunks_summarized': 0,
            'errors': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost_usd': 0.0
        }

    def _get_db(self) -> sqlite3.Connection:
        """Öffnet Datenbankverbindung."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        """Commit or roll back and close every SQLite connection."""
        conn = self._get_db()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        """Create the standalone chunk and run tables when absent."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_index_id INTEGER,
                    chunk_number INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    chunk_tokens INTEGER NOT NULL DEFAULT 0,
                    summary TEXT,
                    summarized_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS parallel_chunks_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    llm_model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    chunks_summarized INTEGER NOT NULL DEFAULT 0,
                    errors_count INTEGER NOT NULL DEFAULT 0,
                    llm_cost_usd REAL NOT NULL DEFAULT 0,
                    log TEXT NOT NULL DEFAULT ''
                )
            """)
            self._create_claim_table(conn)

    @staticmethod
    def _create_claim_table(conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS swarm_chunk_claims (
                chunk_id INTEGER PRIMARY KEY,
                claimed_at REAL NOT NULL,
                run_id INTEGER
            )
        """)

    def _prepare_claims(self) -> None:
        with self._db() as conn:
            self._create_claim_table(conn)
            conn.execute(
                "DELETE FROM swarm_chunk_claims WHERE claimed_at < ?",
                (time.time() - CLAIM_TTL_SECONDS,),
            )

    def _claim_chunk(self, chunk_id: int) -> bool:
        with self._db() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO swarm_chunk_claims
                    (chunk_id, claimed_at, run_id)
                VALUES (?, ?, ?)
            """, (chunk_id, time.time(), self.run_id))
            return cursor.rowcount == 1

    def _release_chunk(self, chunk_id: int) -> None:
        with self._db() as conn:
            conn.execute(
                "DELETE FROM swarm_chunk_claims WHERE chunk_id = ? AND run_id IS ?",
                (chunk_id, self.run_id),
            )

    def _release_run_claims(self) -> None:
        if self.run_id is None:
            return
        with self._db() as conn:
            self._create_claim_table(conn)
            conn.execute(
                "DELETE FROM swarm_chunk_claims WHERE run_id IS ?",
                (self.run_id,),
            )

    def _validate_request_budget(self, chunks, limit, max_budget_usd,
                                 dry_run=False) -> float:
        if limit is not None and not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
        if not dry_run and limit is None:
            raise ValueError("live summarization requires a positive limit")
        byte_lengths = [len(chunk["chunk_text"].encode("utf-8")) for chunk in chunks]
        if any(length > MAX_CHUNK_BYTES for length in byte_lengths):
            raise ValueError(f"a chunk exceeds {MAX_CHUNK_BYTES} UTF-8 bytes")
        total_bytes = sum(byte_lengths)
        if total_bytes > MAX_TOTAL_CHUNK_BYTES:
            raise ValueError(f"chunks exceed {MAX_TOTAL_CHUNK_BYTES} UTF-8 bytes")
        costs = COST_PER_1M[self.model]
        prompt_overhead = len(
            "Fasse den folgenden Text-Chunk zusammen:\n\n---\n\n---".encode("utf-8")
        )
        input_upper = total_bytes + (
            len(SYSTEM_PROMPT.encode("utf-8")) + prompt_overhead
        ) * len(chunks)
        output_upper = 256 * len(chunks)
        cost_upper = MAX_RETRIES * (
            input_upper * costs["input"] + output_upper * costs["output"]
        ) / 1_000_000
        if not dry_run:
            if (max_budget_usd is None or
                    not math.isfinite(float(max_budget_usd)) or
                    max_budget_usd <= 0):
                raise ValueError(
                    "live summarization requires a positive finite max_budget_usd"
                )
            if cost_upper > max_budget_usd:
                raise ValueError(
                    f"conservative cost bound ${cost_upper:.4f} exceeds budget "
                    f"${max_budget_usd:.4f}"
                )
        return cost_upper

    def _create_run(self) -> int:
        """
        Erstellt einen neuen parallel_chunks_runs Eintrag.

        Returns:
            run_id
        """
        with self._db() as conn:
            cursor = conn.execute("""
                INSERT INTO parallel_chunks_runs (started_at, llm_model, status)
                VALUES (?, ?, 'running')
            """, (datetime.now(timezone.utc).isoformat(), self.model_id))
            run_id = cursor.lastrowid
        return run_id

    def _finish_run(self, status: str = "completed", log: str = ""):
        """
        Beendet den parallel_chunks_run.

        Args:
            status: "completed" oder "failed"
            log: Fehler-Log
        """
        with self._db() as conn:
            conn.execute("""
                UPDATE parallel_chunks_runs
                SET finished_at = ?, status = ?, chunks_summarized = ?,
                    errors_count = ?, llm_cost_usd = ?, log = ?
                WHERE id = ?
            """, (
                datetime.now(timezone.utc).isoformat(), status,
                self.stats['chunks_summarized'], self.stats['errors'],
                self.stats['total_cost_usd'], log, self.run_id
            ))

    def get_unsummarized_chunks(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Lädt alle Chunks ohne Summary aus DB.

        Args:
            limit: Maximale Anzahl Chunks (None = alle)

        Returns:
            Liste von Chunks (id, chunk_text, chunk_tokens, ...)
        """
        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            raise ValueError("limit must be a positive integer or None")
        query = """
            SELECT
                id,
                search_index_id,
                chunk_number,
                chunk_text,
                chunk_tokens
            FROM document_chunks
            WHERE summary IS NULL
            ORDER BY search_index_id, chunk_number
        """

        params = []
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self._db() as conn:
            cursor = conn.execute(query, params)
            chunks = [dict(row) for row in cursor.fetchall()]
        return chunks

    def _track_tokens(self, input_tokens: int, output_tokens: int):
        """Token-Verbrauch und Kosten tracken."""
        self.stats['total_input_tokens'] += input_tokens
        self.stats['total_output_tokens'] += output_tokens

        costs = COST_PER_1M.get(self.model, COST_PER_1M["haiku"])
        cost = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000
        self.stats['total_cost_usd'] += cost

    def summarize_chunk(self, chunk_text: str) -> Optional[str]:
        """
        Generiert LLM-Zusammenfassung für einen Chunk via Claude API.

        Args:
            chunk_text: Text des Chunks

        Returns:
            Summary-Text oder None bei Fehler
        """
        user_prompt = (
            "Fasse den folgenden Text-Chunk zusammen:\n\n"
            f"---\n{chunk_text}\n---"
        )

        for attempt in range(MAX_RETRIES):
            try:
                message = self.client.messages.create(
                    model=self.model_id,
                    max_tokens=256,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                summary = message.content[0].text.strip()

                # Token-Tracking
                self._track_tokens(
                    message.usage.input_tokens,
                    message.usage.output_tokens
                )

                return summary

            except Exception as e:
                error_str = str(e)

                # Rate-Limit (429) oder Overloaded (529) -> Retry mit Backoff
                if "rate" in error_str.lower() or "429" in error_str:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    print(f"\n  [RATE-LIMIT] Warte {delay:.0f}s...", end=" ")
                    time.sleep(delay)
                    continue

                if "overloaded" in error_str.lower() or "529" in error_str:
                    delay = RETRY_BASE_DELAY * (attempt + 1)
                    print(f"\n  [OVERLOADED] Warte {delay:.0f}s...", end=" ")
                    time.sleep(delay)
                    continue

                # Andere Fehler: letzter Versuch -> abbrechen
                if attempt >= MAX_RETRIES - 1:
                    print(f"\n  [API-FEHLER] {error_str[:100]}")
                    return None

                # Sonst nochmal versuchen
                time.sleep(RETRY_BASE_DELAY)
                continue

        print(f"\n  [FEHLER] Max Retries ({MAX_RETRIES}) erreicht")
        return None

    def save_summary(self, chunk_id: int, summary: str):
        """
        Speichert Summary in DB.

        Args:
            chunk_id: Chunk-ID
            summary: Zusammenfassungs-Text
        """
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("summary must be a non-empty string")
        with self._db() as conn:
            cursor = conn.execute("""
                UPDATE document_chunks
                SET summary = ?, summarized_at = ?
                WHERE id = ? AND summary IS NULL
            """, (summary, datetime.now(timezone.utc).isoformat(), chunk_id))
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"chunk {chunk_id} was removed or summarized concurrently"
                )

    def _run(self, batch_size: int = 10, dry_run: bool = False,
             limit: Optional[int] = None, max_budget_usd: Optional[float] = None):
        """
        Hauptprozess: Alle Chunks laden, summarizen, speichern.

        Args:
            batch_size: Wie viele Chunks pro Batch? (Rate-Limiting)
            dry_run: Wenn True, nur Simulation (keine DB-Schreibzugriffe)
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        if limit is not None and not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"database not found: {self.db_path}; use --init-db first"
            )
        print("=== Parallel-Chunks Stufe 3: Chunk-Zusammenfassung ===\n")
        print(f"Modell: {self.model} ({self.model_id})")
        print(f"Batch-Size: {batch_size}")
        print(f"Dry-Run: {'Ja' if dry_run else 'Nein'}\n")

        # Run starten
        if not dry_run:
            self._prepare_claims()
            self.run_id = self._create_run()
            print(f"Run-ID: {self.run_id}\n")

        # Chunks laden
        chunks = self.get_unsummarized_chunks(limit=limit)
        total_chunks = len(chunks)
        self._validate_request_budget(chunks, limit, max_budget_usd, dry_run)

        if total_chunks == 0:
            print("✓ Keine Chunks ohne Summary gefunden")
            if not dry_run:
                self._finish_run(status="completed", log="Keine Arbeit")
            return dict(self.stats)

        print(f"Gefunden: {total_chunks} Chunks ohne Summary\n")

        if dry_run:
            total_chars = sum(len(c['chunk_text']) for c in chunks)
            est_input_tokens = total_chars // 4 + total_chunks * 100  # System-Prompt Overhead
            est_output_tokens = total_chunks * 80  # ~80 Tokens pro Summary
            costs = COST_PER_1M.get(self.model, COST_PER_1M["haiku"])
            est_cost = (est_input_tokens * costs["input"] + est_output_tokens * costs["output"]) / 1_000_000

            print("[DRY-RUN] Kosten-Schaetzung:")
            print(f"  Input-Tokens:  ~{est_input_tokens}")
            print(f"  Output-Tokens: ~{est_output_tokens}")
            print(f"  Gesamt-Zeichen: {total_chars}")
            print(f"  Geschaetzte Kosten: ${est_cost:.4f}")
            print("\n  Erste 5 Chunks:")
            for c in chunks[:5]:
                preview = c['chunk_text'][:60].replace('\n', ' ')
                print(f"    Chunk {c['id']}: {preview}...")
            return dict(self.stats)

        # API client is initialized only after limit/input/budget validation.
        api_key = get_api_key()
        self.client = anthropic.Anthropic(api_key=api_key)

        # Chunks durchgehen
        for i, chunk in enumerate(chunks, 1):
            chunk_id = chunk['id']
            chunk_text = chunk['chunk_text']
            chunk_tokens = chunk['chunk_tokens']

            print(f"[{i}/{total_chunks}] Chunk {chunk_id} ({chunk_tokens} Tokens)...", end=" ")

            if not self._claim_chunk(chunk_id):
                print("↷ (bereits von einem anderen Run reserviert)")
                continue

            # Zusammenfassung generieren
            try:
                summary = self.summarize_chunk(chunk_text)
                if summary:
                    # In DB speichern
                    if not dry_run:
                        self.save_summary(chunk_id, summary)
                    self.stats['chunks_summarized'] += 1
                    print("✓")
                else:
                    print("✗ (Fehler bei LLM-API)")
                    self.stats['errors'] += 1

            except Exception as e:
                print(f"✗ (Exception: {e})")
                self.stats['errors'] += 1
            finally:
                self._release_chunk(chunk_id)

            self.stats['chunks_processed'] += 1

            # Batch-Pause (Rate-Limiting)
            if i % batch_size == 0 and i < total_chunks:
                print("  → Batch-Pause (5 Sekunden)...")
                time.sleep(5)

        # Run beenden
        print(f"\n{'=' * 50}")
        print("  ZUSAMMENFASSUNG")
        print(f"{'=' * 50}")
        print(f"  Chunks verarbeitet:  {self.stats['chunks_processed']}")
        print(f"  Chunks summarisiert: {self.stats['chunks_summarized']}")
        print(f"  Fehler:              {self.stats['errors']}")
        print(f"  Input-Tokens:        {self.stats['total_input_tokens']}")
        print(f"  Output-Tokens:       {self.stats['total_output_tokens']}")
        print(f"  Kosten:              ${self.stats['total_cost_usd']:.4f}")
        print(f"{'=' * 50}")

        if not dry_run:
            status = "completed" if self.stats['errors'] == 0 else "completed_with_errors"
            self._finish_run(status=status, log=f"{self.stats['errors']} Fehler")
            print(f"\nRun-ID {self.run_id} abgeschlossen (Status: {status})")
        return dict(self.stats)

    def run(self, batch_size: int = 10, dry_run: bool = False,
            limit: Optional[int] = None,
            max_budget_usd: Optional[float] = None):
        """Run with a durable failed-state and claim cleanup on every abort."""
        self.run_id = None
        self.stats = self._empty_stats()
        try:
            return self._run(batch_size, dry_run, limit, max_budget_usd)
        except BaseException as exc:
            if not dry_run and self.run_id is not None:
                try:
                    self._release_run_claims()
                    self._finish_run(
                        status="failed",
                        log=f"{type(exc).__name__}: {str(exc)[:500]}",
                    )
                except sqlite3.Error:
                    pass
            raise


def main() -> int:
    """CLI-Einstieg."""
    parser = argparse.ArgumentParser(
        description="Parallel-Chunks Stufe 3: LLM-Zusammenfassungen für Chunks"
    )
    parser.add_argument(
        '--model',
        choices=['haiku', 'sonnet'],
        default='haiku',
        help='LLM-Modell (haiku = schnell & günstig, sonnet = präzise)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Wie viele Chunks pro Batch? (Rate-Limiting)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulation (keine DB-Änderungen)'
    )
    parser.add_argument(
        '--db-path', type=Path, default=DB_PATH,
        help='SQLite database path (default: SWARM_DB_PATH or data/swarm.db)'
    )
    parser.add_argument(
        '--init-db', action='store_true',
        help='Initialize standalone database tables and exit'
    )
    parser.add_argument(
        '--limit', type=int,
        help='Maximum chunks; required for live runs'
    )
    parser.add_argument(
        '--max-budget-usd', type=float,
        help='Conservative cost ceiling; required for live runs'
    )

    args = parser.parse_args()

    summarizer = ChunkSummarizer(model=args.model, db_path=args.db_path)
    if args.init_db:
        summarizer.initialize_schema()
        print(f"Datenbank initialisiert: {summarizer.db_path}")
        return 0
    stats = summarizer.run(
        batch_size=args.batch_size, dry_run=args.dry_run, limit=args.limit,
        max_budget_usd=args.max_budget_usd,
    )
    return 1 if stats["errors"] else 0


if __name__ == '__main__':
    raise SystemExit(main())
