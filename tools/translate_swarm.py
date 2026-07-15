#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""
translate_swarm.py - Schwarm-Uebersetzung mit Parallel-Chunks (SQ062)
======================================================================

Uebersetzt fehlende Texte in languages_translations via Claude Haiku.
"Parallel-Chunks": Texte in kleine Chunks buendeln, 5-10 parallele Haiku-Instanzen.
Unterstützt 6 Zielsprachen (Referenz: .SOFTWARE/_LANG/LANGUAGE_CODES.md).

Usage:
    python translate_swarm.py                       # Alle fehlenden DE->EN uebersetzen
    python translate_swarm.py --target en            # Explizit: Zielsprache Englisch
    python translate_swarm.py --target es            # Zielsprache Spanisch
    python translate_swarm.py --target zh            # Zielsprache Chinesisch
    python translate_swarm.py --target ja            # Zielsprache Japanisch
    python translate_swarm.py --target ru            # Zielsprache Russisch
    python translate_swarm.py --dry-run              # Nur anzeigen, kein API-Call
    python translate_swarm.py --namespace help        # Nur einen Namespace
    python translate_swarm.py --chunk-size 5          # Chunk-Groesse anpassen
    python translate_swarm.py --workers 5             # Thread-Anzahl anpassen
    python translate_swarm.py --limit 20              # Max. Texte uebersetzen
    python translate_swarm.py --inventory             # Status-Uebersicht

Author: Lukas Geiger (ellmos-ai)
Created: 2026-02-22
"""

import argparse
import json
import math
import os
import re
import sqlite3
import sys
import time
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import anthropic

try:
    import anthropic  # noqa: F811
except ImportError:
    anthropic = None  # noqa: F811

# --- Konstanten ---

MODEL = "claude-haiku-4-5-20251001"
DEFAULT_CHUNK_SIZE = 10
DEFAULT_WORKERS = 8
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0

TABLE = "languages_translations"
SOURCE_TAG = "llm_auto_swarm"

SUPPORTED_LANGUAGES = ['de', 'en', 'es', 'zh', 'ja', 'ru']
LANGUAGE_NAMES = {
    'de': 'German', 'en': 'English', 'es': 'Spanish',
    'zh': 'Chinese (Simplified)', 'ja': 'Japanese', 'ru': 'Russian',
}
DEFAULT_SOURCE = 'de'
DEFAULT_TARGET = 'en'
CLAIM_TABLE = "swarm_translation_claims"
CLAIM_TTL_SECONDS = 86400
MAX_WORKERS = 20
MAX_CHUNK_SIZE = 50
MAX_LIMIT = 1000
MAX_TEXT_BYTES = 100_000
MAX_TOTAL_TEXT_BYTES = 1_000_000
MAX_IDENTITY_BYTES = 10_000

_BRACE_PLACEHOLDER = re.compile(
    r"(?<!\{)\{[A-Za-z_][A-Za-z0-9_.]*(?:![rsa])?(?::[^{}\n]+)?\}(?!\})"
)
_PERCENT_PLACEHOLDER = re.compile(
    r"%(?:\([A-Za-z_][A-Za-z0-9_.]*\))?[#0\- +]?\d*(?:\.\d+)?[diouxXeEfFgGcrs]"
)


def _validate_language(language: str, label: str) -> str:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"{label} language must be one of: {', '.join(SUPPORTED_LANGUAGES)}"
        )
    return language


def get_system_prompt(target_lang: str, source_lang: str = DEFAULT_SOURCE) -> str:
    _validate_language(source_lang, "source")
    _validate_language(target_lang, "target")
    source_name = LANGUAGE_NAMES[source_lang]
    target_name = LANGUAGE_NAMES.get(target_lang, 'English')
    return (
        f"You are a professional translator. Translate {source_name} UI/help texts "
        f"to {target_name}.\n\n"
        "RULES:\n"
        "- Keep markdown formatting, code blocks, headings (===, ---) unchanged\n"
        "- Keep placeholders like {variable}, {count}, {name} unchanged\n"
        "- Keep CLI commands (python ..., npm ..., --flags) unchanged\n"
        "- Keep technical terms: Skill, Agent, Handler, Hub, Kernel, Daemon, Workflow, Task, Wiki, Memory\n"
        "- Keep SQL statements unchanged\n"
        "- Maintain the same tone (professional but friendly)\n"
        "- If text contains ONLY code/commands/variables, return it unchanged\n"
        "- Output ONLY valid JSON, nothing else"
    )


# Legacy constant for backwards compatibility
SYSTEM_PROMPT = get_system_prompt('en')


# --- Hilfsfunktionen ---


def get_api_key():
    """API-Key aus Umgebungsvariable laden."""
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


def get_db_path(require_exists=True):
    """Ermittelt DB-Pfad: SWARM_DB_PATH env oder data/swarm.db relativ zum Script."""
    env_path = os.getenv("SWARM_DB_PATH")
    if env_path:
        db_path = Path(env_path)
    else:
        db_path = Path(__file__).parent.parent / "data" / "swarm.db"
    if require_exists and not db_path.exists():
        raise FileNotFoundError(
            f"Datenbank nicht gefunden: {db_path}. "
            "Setze SWARM_DB_PATH oder verwende --init-db."
        )
    return db_path


@contextmanager
def _db_connection(db_path, *, timeout=5) -> Iterator[sqlite3.Connection]:
    """Open one transaction and always close the SQLite handle."""
    conn = sqlite3.connect(str(db_path), timeout=timeout)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _placeholder_counts(text):
    """Return format placeholders that a translation must preserve exactly."""
    placeholders = [f"brace:{value}" for value in _BRACE_PLACEHOLDER.findall(text)]
    placeholders.extend(
        f"percent:{value}" for value in _PERCENT_PLACEHOLDER.findall(text)
    )
    return Counter(placeholders)


def initialize_translation_db(db_path):
    """Create the standalone translation table when it does not exist."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _db_connection(path) as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                namespace TEXT,
                language TEXT NOT NULL,
                value TEXT NOT NULL DEFAULT '',
                is_verified INTEGER NOT NULL DEFAULT 0,
                source TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{TABLE}_lookup
            ON {TABLE}(key, namespace, language)
        """)
        try:
            conn.execute(f"""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_{TABLE}_identity
                ON {TABLE}(key, COALESCE(namespace, ''), language)
            """)
        except sqlite3.IntegrityError as exc:
            raise RuntimeError(
                "duplicate translation identities block schema migration; "
                "back up the database, deduplicate by "
                "(key, COALESCE(namespace, ''), language), "
                "then rerun --init-db"
            ) from exc
        _create_claim_table(conn)


def _create_claim_table(conn):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {CLAIM_TABLE} (
            claim_key TEXT PRIMARY KEY,
            claim_token TEXT NOT NULL,
            claimed_at REAL NOT NULL
        )
    """)


def _translation_claim_key(item, source_lang, target_lang):
    return json.dumps(
        [source_lang, target_lang, item.get("namespace") or "", item["key"]],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def claim_translations(db_path, items, source_lang, target_lang, claim_token):
    """Atomically claim missing rows before any API call."""
    claimed = []
    with _db_connection(db_path, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("BEGIN IMMEDIATE")
        _create_claim_table(conn)
        conn.execute(
            f"DELETE FROM {CLAIM_TABLE} WHERE claimed_at < ?",
            (time.time() - CLAIM_TTL_SECONDS,),
        )
        for item in items:
            cursor = conn.execute(f"""
                INSERT OR IGNORE INTO {CLAIM_TABLE}
                    (claim_key, claim_token, claimed_at)
                VALUES (?, ?, ?)
            """, (
                _translation_claim_key(item, source_lang, target_lang),
                claim_token,
                time.time(),
            ))
            if cursor.rowcount == 1:
                claimed.append(item)
    return claimed


def release_translation_claims(db_path, claim_token):
    with _db_connection(db_path, timeout=10) as conn:
        _create_claim_table(conn)
        conn.execute(
            f"DELETE FROM {CLAIM_TABLE} WHERE claim_token = ?",
            (claim_token,),
        )


def validate_translation_request(items, chunk_size, workers, limit,
                                 max_budget_usd=None, dry_run=False):
    if not 1 <= chunk_size <= MAX_CHUNK_SIZE:
        raise ValueError(f"chunk_size must be between 1 and {MAX_CHUNK_SIZE}")
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"workers must be between 1 and {MAX_WORKERS}")
    if not 0 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 0 and {MAX_LIMIT}")
    if not dry_run and limit == 0:
        raise ValueError("live translation requires a positive limit")
    byte_lengths = []
    prompt_items = []
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("translation items must be dictionaries")
        if not isinstance(item.get("key"), str) or not item["key"]:
            raise ValueError("translation keys must be non-empty strings")
        if item.get("namespace") is not None and not isinstance(item["namespace"], str):
            raise TypeError("translation namespaces must be strings or None")
        if not isinstance(item.get("value"), str):
            raise TypeError("translation values must be strings")
        identity_bytes = len(json.dumps(
            {"key": item["key"], "namespace": item.get("namespace")},
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8"))
        if identity_bytes > MAX_IDENTITY_BYTES:
            raise ValueError(
                f"a translation identity exceeds {MAX_IDENTITY_BYTES} UTF-8 bytes"
            )
        value_bytes = len(item["value"].encode("utf-8"))
        byte_lengths.append(value_bytes)
        prompt_items.append({
            "key": item["key"],
            "namespace": item.get("namespace"),
            # Longer than any supported two-letter source key and therefore a
            # conservative stand-in for the exact JSON request shape.
            "source_language": item["value"],
        })
    if any(length > MAX_TEXT_BYTES for length in byte_lengths):
        raise ValueError(f"a source text exceeds {MAX_TEXT_BYTES} UTF-8 bytes")
    serialized_bytes = sum(
        len(json.dumps(
            prompt_items[index:index + chunk_size],
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"))
        for index in range(0, len(prompt_items), chunk_size)
    )
    if serialized_bytes > MAX_TOTAL_TEXT_BYTES:
        raise ValueError(
            f"serialized translation inputs exceed {MAX_TOTAL_TEXT_BYTES} UTF-8 bytes"
        )
    chunk_count = (len(items) + chunk_size - 1) // chunk_size
    input_upper = serialized_bytes + chunk_count * 4000
    output_upper = chunk_count * 4096
    cost_upper = (
        (input_upper * 1.0 + output_upper * 5.0)
        * MAX_RETRIES
        / 1_000_000
    )
    if not dry_run:
        if (max_budget_usd is None or
                not math.isfinite(float(max_budget_usd)) or
                max_budget_usd <= 0):
            raise ValueError("live translation requires a positive finite max_budget_usd")
        if cost_upper > max_budget_usd:
            raise ValueError(
                f"conservative cost bound ${cost_upper:.4f} exceeds budget "
                f"${max_budget_usd:.4f}"
            )
    return cost_upper


def get_missing_translations(db_path, namespace=None, limit=0,
                             target_lang='en', source_lang='de'):
    """
    Holt alle DE-Texte ohne Übersetzung in der Zielsprache.

    Returns:
        Liste von Dicts: {id, key, namespace, value}
    """
    _validate_language(source_lang, "source")
    _validate_language(target_lang, "target")
    if source_lang == target_lang:
        raise ValueError("source and target languages must differ")
    if limit < 0:
        raise ValueError("limit must be zero or greater")

    query = f"""
        SELECT t1.id, t1.key, t1.namespace, t1.value
        FROM {TABLE} t1
        WHERE t1.language = ?
        AND NOT EXISTS (
            SELECT 1 FROM {TABLE} t2
            WHERE t2.key = t1.key
            AND COALESCE(t2.namespace, '') = COALESCE(t1.namespace, '')
            AND t2.language = ?
            AND t2.value != ''
        )
    """
    params = [source_lang, target_lang]

    if namespace:
        query += " AND t1.namespace = ?"
        params.append(namespace)

    query += " ORDER BY t1.namespace, t1.key"

    if limit > 0:
        query += " LIMIT ?"
        params.append(limit)

    with _db_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def chunk_texts(texts, chunk_size):
    """Teilt Texte in Chunks der Groesse chunk_size."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    return [texts[i:i + chunk_size] for i in range(0, len(texts), chunk_size)]


# --- Kern: API-Call pro Chunk ---


def translate_chunk(client, chunk, chunk_index, total_chunks, target_lang='en',
                    source_lang='de'):
    """
    Uebersetzt einen Chunk von Texten via Haiku API.

    Returns:
        (chunk_index, results_list, error_or_none)
    """
    _validate_language(source_lang, "source")
    _validate_language(target_lang, "target")
    source_name = LANGUAGE_NAMES[source_lang]
    target_name = LANGUAGE_NAMES[target_lang]
    texts_for_api = [
        {"key": item["key"], "namespace": item["namespace"], source_lang: item["value"]}
        for item in chunk
    ]

    user_prompt = (
        f"Translate these {len(chunk)} {source_name} texts to {target_name}.\n\n"
        f"INPUT (JSON array):\n"
        f"{json.dumps(texts_for_api, ensure_ascii=False, indent=2)}\n\n"
        f"OUTPUT FORMAT (JSON array, same identity keys + \"{target_lang}\" field):\n"
        f'[{{"key": "...", "namespace": "...", "{target_lang}": "translated text"}}, ...]\n\n'
        f"Return ONLY the JSON array, no explanation."
    )

    system_prompt = get_system_prompt(target_lang, source_lang)

    for attempt in range(MAX_RETRIES):
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            response_text = message.content[0].text.strip()

            # Robuste JSON-Extraktion
            start = response_text.find("[")
            end = response_text.rfind("]") + 1
            if start == -1 or end == 0:
                raise ValueError(f"Kein JSON-Array in Antwort: {response_text[:200]}")

            results = json.loads(response_text[start:end])

            if len(results) != len(chunk):
                raise ValueError(
                    f"Erwartet {len(chunk)} Ergebnisse, bekommen {len(results)}"
                )

            expected = {(item["key"], item.get("namespace")): item for item in chunk}
            returned = {}
            for translated in results:
                if not isinstance(translated, dict):
                    raise ValueError("Each translation result must be an object")
                identity = (translated.get("key"), translated.get("namespace"))
                if identity not in expected:
                    raise ValueError(f"Unexpected translation identity: {identity!r}")
                if identity in returned:
                    raise ValueError(f"Duplicate translation identity: {identity!r}")
                trans_text = (translated.get(target_lang, "")
                              or translated.get("translation", ""))
                if not isinstance(trans_text, str) or not trans_text.strip():
                    raise ValueError(f"Blank translation for {identity!r}")
                source_placeholders = _placeholder_counts(expected[identity]["value"])
                translated_placeholders = _placeholder_counts(trans_text)
                if translated_placeholders != source_placeholders:
                    raise ValueError(
                        f"Placeholder mismatch for {identity!r}: expected "
                        f"{dict(source_placeholders)}, got {dict(translated_placeholders)}"
                    )
                returned[identity] = trans_text

            missing = set(expected) - set(returned)
            if missing:
                raise ValueError(f"Missing translation identities: {sorted(missing)!r}")

            mapped = []
            for orig in chunk:
                identity = (orig["key"], orig.get("namespace"))
                mapped.append({
                    "key": orig["key"],
                    "namespace": orig["namespace"],
                    "translation": returned[identity],
                })

            return (chunk_index, mapped, None)

        except Exception as e:
            error_str = str(e)

            if "rate" in error_str.lower() or "429" in error_str:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                time.sleep(delay)
                continue

            if "overloaded" in error_str.lower() or "529" in error_str:
                time.sleep(RETRY_BASE_DELAY * (attempt + 1))
                continue

            if "json" in error_str.lower() and attempt < MAX_RETRIES - 1:
                continue

            if isinstance(e, (KeyError, TypeError, ValueError)) and attempt < MAX_RETRIES - 1:
                continue

            return (chunk_index, [], f"Chunk {chunk_index + 1}: {error_str}")

    return (chunk_index, [], f"Chunk {chunk_index + 1}: Max retries ({MAX_RETRIES}) erreicht")


# --- DB-Writer ---


def write_results_to_db(db_path, all_results, target_lang='en'):
    """
    Schreibt Uebersetzungs-Ergebnisse gesammelt in die DB.
    Single-threaded, wird NACH allen API-Calls aufgerufen.
    """
    now = datetime.now(timezone.utc).isoformat()
    success = 0
    errors = 0

    with _db_connection(db_path) as conn:
        # Serialize writers across processes, including compatible legacy
        # schemas that predate the standalone unique identity index.
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("BEGIN IMMEDIATE")
        for item in all_results:
            try:
                translation = item["translation"]
                if not isinstance(translation, str) or not translation.strip():
                    raise ValueError("blank translation")
                existing = conn.execute(f"""
                    SELECT id, value FROM {TABLE}
                    WHERE key = ?
                      AND COALESCE(namespace, '') = COALESCE(?, '')
                      AND language = ?
                    ORDER BY id LIMIT 1
                """, (item["key"], item.get("namespace"), target_lang)).fetchone()
                if existing:
                    if existing[1]:
                        errors += 1
                        continue
                    conn.execute(f"""
                        UPDATE {TABLE}
                        SET value = ?, is_verified = 0, source = ?, updated_at = ?
                        WHERE id = ?
                    """, (translation, SOURCE_TAG, now, existing[0]))
                else:
                    conn.execute(
                        f"INSERT INTO {TABLE} "
                        "(key, namespace, language, value, is_verified, source, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
                        (item["key"], item.get("namespace"), target_lang, translation,
                         SOURCE_TAG, now, now),
                    )
                success += 1
            except Exception as e:
                print(f"  [DB-ERROR] {item.get('key', '?')}: {e}")
                errors += 1
    return (success, errors)


# --- Haupt-Orchestrierung ---


def _run_swarm(source_lang="de", target_lang="en", namespace=None,
               chunk_size=DEFAULT_CHUNK_SIZE, workers=DEFAULT_WORKERS,
               limit=0, dry_run=False, max_budget_usd=None,
               _claim_token=None):
    """Schwarm-Übersetzung mit Parallel-Chunks."""
    _validate_language(source_lang, "source")
    _validate_language(target_lang, "target")
    if source_lang == target_lang:
        raise ValueError("source and target languages must differ")
    validate_translation_request(
        [], chunk_size, workers, limit, max_budget_usd, dry_run
    )
    db_path = get_db_path()

    # 1. Fehlende laden
    missing = get_missing_translations(
        db_path, namespace, limit, target_lang, source_lang
    )

    validate_translation_request(
        missing, chunk_size, workers, limit, max_budget_usd, dry_run
    )

    if not dry_run:
        candidates = missing
        missing = claim_translations(
            db_path, missing, source_lang, target_lang, _claim_token
        )

    if not missing:
        target_name = LANGUAGE_NAMES.get(target_lang, target_lang)
        if not dry_run and candidates:
            print("[OK] Alle fehlenden Texte sind bereits von einem anderen Run reserviert.")
        else:
            print(f"[OK] Alle Texte sind bereits nach {target_name} übersetzt!")
        return True

    # Namespace-Verteilung anzeigen
    by_ns = {}
    for t in missing:
        ns = t["namespace"] or "general"
        by_ns.setdefault(ns, []).append(t)

    print(f"[SWARM] {len(missing)} Texte zu übersetzen ({source_lang} -> {target_lang})")
    for ns, texts in sorted(by_ns.items()):
        print(f"         {ns}: {len(texts)}")

    # 2. Chunken
    chunks = chunk_texts(missing, chunk_size)
    print(f"[SWARM] {len(chunks)} Chunks a {chunk_size} Texte, {workers} parallele Worker")

    if dry_run:
        print("\n[DRY-RUN] Wuerde folgende Chunks senden:")
        for i, chunk in enumerate(chunks):
            keys = [t["key"][:30] for t in chunk[:3]]
            print(f"  Chunk {i + 1}/{len(chunks)}: {len(chunk)} Texte - {', '.join(keys)}...")

        total_chars = sum(len(t["value"]) for t in missing)
        est_input_tokens = total_chars // 4 + len(chunks) * 200
        est_output_tokens = total_chars // 4
        cost = (est_input_tokens * 1 + est_output_tokens * 5) / 1_000_000
        print(f"\n[DRY-RUN] Geschaetzte Kosten: ${cost:.4f}")
        print(f"           Input-Tokens:  ~{est_input_tokens}")
        print(f"           Output-Tokens: ~{est_output_tokens}")
        print(f"           Gesamt-Zeichen: {total_chars}")
        return True

    # 3. API-Key + Client
    if anthropic is None:
        raise RuntimeError("anthropic SDK not installed: pip install anthropic")
    api_key = get_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    # 4. Parallel uebersetzen
    all_results = []
    all_errors = []
    db_success = 0
    db_errors = 0
    completed = 0
    lock = threading.Lock()
    start_time = time.time()

    print(f"\n[SWARM] Starte Uebersetzung mit {workers} Workern...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                translate_chunk, client, chunk, i, len(chunks), target_lang, source_lang
            ): i
            for i, chunk in enumerate(chunks)
        }

        for future in as_completed(futures):
            chunk_idx, results, error = future.result()

            with lock:
                completed += 1
                if error:
                    all_errors.append(error)
                    print(f"  [{completed}/{len(chunks)}] Chunk {chunk_idx + 1} FEHLER: {error}")
                else:
                    all_results.extend(results)
                    print(f"  [{completed}/{len(chunks)}] Chunk {chunk_idx + 1} OK ({len(results)} Texte)")

    elapsed = time.time() - start_time
    print(f"\n[SWARM] API-Phase abgeschlossen in {elapsed:.1f}s")
    print(f"         Erfolgreich: {len(all_results)} Texte")
    print(f"         Fehler: {len(all_errors)} Chunks")

    # 5. In DB schreiben
    if all_results:
        print(f"\n[SWARM] Schreibe {len(all_results)} Übersetzungen in DB...")
        db_success, db_errors = write_results_to_db(db_path, all_results, target_lang)
        print(f"         Geschrieben: {db_success}")
        if db_errors > 0:
            print(f"         Übersprungen (Duplikate): {db_errors}")

    # 6. Zusammenfassung
    print(f"\n{'=' * 60}")
    print("  ERGEBNIS")
    print(f"{'=' * 60}")
    print(f"  Gesamt zu übersetzen:   {len(missing)}")
    print(f"  Erfolgreich gespeichert: {db_success}")
    print(f"  Fehler (API):           {len(all_errors)}")
    print(f"  Fehler (DB/Konflikte):  {db_errors}")
    print(f"  Dauer:                  {elapsed:.1f}s")
    print(f"  Chunks:                 {len(chunks)} (a {chunk_size} Texte)")
    print(f"  Parallele Worker:       {workers}")
    print(f"{'=' * 60}")

    if all_errors:
        print("\n[FEHLER-DETAILS]:")
        for err in all_errors:
            print(f"  - {err}")

    return len(all_errors) == 0 and db_errors == 0


def run_swarm(source_lang="de", target_lang="en", namespace=None,
              chunk_size=DEFAULT_CHUNK_SIZE, workers=DEFAULT_WORKERS,
              limit=0, dry_run=False, max_budget_usd=None):
    """Run translation with a process-unique claim lifecycle."""
    claim_token = uuid.uuid4().hex
    try:
        return _run_swarm(
            source_lang, target_lang, namespace, chunk_size, workers,
            limit, dry_run, max_budget_usd, claim_token,
        )
    finally:
        if not dry_run:
            try:
                release_translation_claims(get_db_path(), claim_token)
            except (FileNotFoundError, sqlite3.Error):
                pass


def show_inventory(namespace=None, target_lang='en', source_lang='de'):
    """Zeigt Inventar der fehlenden Übersetzungen."""
    db_path = get_db_path()
    target_name = LANGUAGE_NAMES.get(target_lang, target_lang)
    missing = get_missing_translations(
        db_path, namespace, target_lang=target_lang, source_lang=source_lang
    )

    if not missing:
        print(f"[OK] Alle Texte sind bereits nach {target_name} übersetzt!")
        return

    print(f"[INVENTAR] {len(missing)} fehlende {target_name}-Übersetzungen\n")

    by_ns = {}
    for t in missing:
        ns = t["namespace"] or "general"
        by_ns.setdefault(ns, []).append(t)

    for ns, texts in sorted(by_ns.items()):
        print(f"  [{ns.upper()}] {len(texts)} Texte")
        for t in texts[:3]:
            val_short = t["value"][:60].replace("\n", " ")
            print(f"    {t['key'][:30]:<32} {val_short}")
        if len(texts) > 3:
            print(f"    ... und {len(texts) - 3} weitere")
        print()

    # Gesamtstatistik
    total_chars = sum(len(t["value"]) for t in missing)
    avg_len = total_chars // len(missing) if missing else 0
    print(f"  Gesamt: {len(missing)} Texte, {total_chars} Zeichen, avg {avg_len} Zeichen/Text")


# --- CLI ---


def main():
    parser = argparse.ArgumentParser(
        description="Schwarm-Übersetzung mit Parallel-Chunks (SQ062)"
    )
    parser.add_argument(
        "--namespace", "-n",
        help="Nur einen Namespace übersetzen (cli/docs/help/gui/skills)",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
        help=f"Texte pro API-Call (default: {DEFAULT_CHUNK_SIZE})",
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=DEFAULT_WORKERS,
        help=f"Parallele Threads (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max. Texte; positiver Wert ist für Live-Läufe erforderlich",
    )
    parser.add_argument(
        "--max-budget-usd", type=float,
        help="Konservative Kostenobergrenze; für Live-Läufe erforderlich",
    )
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, kein API-Call")
    parser.add_argument("--inventory", action="store_true", help="Inventar anzeigen")
    parser.add_argument(
        "--init-db", action="store_true",
        help="Standalone-Übersetzungsdatenbank initialisieren und beenden",
    )
    parser.add_argument("--source", default="de", help="Quellsprache (default: de)")
    parser.add_argument("--target", default="en", help="Zielsprache (default: en)")

    args = parser.parse_args()

    if args.init_db:
        db_path = get_db_path(require_exists=False)
        initialize_translation_db(db_path)
        print(f"[OK] Datenbank initialisiert: {db_path}")
        return

    if args.inventory:
        show_inventory(args.namespace, args.target, args.source)
        return

    success = run_swarm(
        source_lang=args.source,
        target_lang=args.target,
        namespace=args.namespace,
        chunk_size=args.chunk_size,
        workers=args.workers,
        limit=args.limit,
        dry_run=args.dry_run,
        max_budget_usd=args.max_budget_usd,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
