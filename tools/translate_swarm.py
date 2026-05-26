#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""
translate_swarm.py - Schwarm-Uebersetzung mit Epstein-Methode (SQ062)
=====================================================================

Uebersetzt fehlende Texte in languages_translations via Claude Haiku.
"Epstein-Methode": Texte in kleine Chunks buendeln, 5-10 parallele Haiku-Instanzen.
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
import os
import sqlite3
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("[FEHLER] anthropic SDK nicht installiert: pip install anthropic")
    sys.exit(1)

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


def get_system_prompt(target_lang: str) -> str:
    target_name = LANGUAGE_NAMES.get(target_lang, 'English')
    return (
        f"You are a professional translator. Translate German UI/help texts "
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
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print("[INFO] API-Key aus Umgebungsvariable geladen")
        return api_key

    raise ValueError(
        "ANTHROPIC_API_KEY nicht konfiguriert!\n\n"
        "Setze die Umgebungsvariable:\n"
        "  export ANTHROPIC_API_KEY=sk-ant-api03-..."
    )


def get_db_path():
    """Ermittelt DB-Pfad: SWARM_DB_PATH env oder data/swarm.db relativ zum Script."""
    env_path = os.getenv("SWARM_DB_PATH")
    if env_path:
        db_path = Path(env_path)
    else:
        db_path = Path(__file__).parent.parent / "data" / "swarm.db"
    if not db_path.exists():
        print(f"[FEHLER] Datenbank nicht gefunden: {db_path}")
        print("         Setze SWARM_DB_PATH oder lege data/swarm.db an.")
        sys.exit(1)
    return db_path


def get_missing_translations(db_path, namespace=None, limit=0, target_lang='en'):
    """
    Holt alle DE-Texte ohne Übersetzung in der Zielsprache.

    Returns:
        Liste von Dicts: {id, key, namespace, value}
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    query = f"""
        SELECT t1.id, t1.key, t1.namespace, t1.value
        FROM {TABLE} t1
        WHERE t1.language = 'de'
        AND NOT EXISTS (
            SELECT 1 FROM {TABLE} t2
            WHERE t2.key = t1.key
            AND t2.namespace = t1.namespace
            AND t2.language = ?
            AND t2.value != ''
        )
    """
    params = [target_lang]

    if namespace:
        query += " AND t1.namespace = ?"
        params.append(namespace)

    query += " ORDER BY t1.namespace, t1.key"

    if limit > 0:
        query += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def chunk_texts(texts, chunk_size):
    """Teilt Texte in Chunks der Groesse chunk_size."""
    return [texts[i:i + chunk_size] for i in range(0, len(texts), chunk_size)]


# --- Kern: API-Call pro Chunk ---


def translate_chunk(client, chunk, chunk_index, total_chunks, target_lang='en'):
    """
    Uebersetzt einen Chunk von Texten via Haiku API.

    Returns:
        (chunk_index, results_list, error_or_none)
    """
    target_name = LANGUAGE_NAMES.get(target_lang, 'English')
    texts_for_api = [
        {"key": item["key"], "namespace": item["namespace"], "de": item["value"]}
        for item in chunk
    ]

    user_prompt = (
        f"Translate these {len(chunk)} German texts to {target_name}.\n\n"
        f"INPUT (JSON array):\n"
        f"{json.dumps(texts_for_api, ensure_ascii=False, indent=2)}\n\n"
        f"OUTPUT FORMAT (JSON array, same order, same keys + \"{target_lang}\" field):\n"
        f'[{{"key": "...", "namespace": "...", "{target_lang}": "translated text"}}, ...]\n\n'
        f"Return ONLY the JSON array, no explanation."
    )

    system_prompt = get_system_prompt(target_lang)

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

            mapped = []
            for orig, translated in zip(chunk, results):
                trans_text = (translated.get(target_lang, "")
                              or translated.get("translation", ""))
                mapped.append({
                    "key": orig["key"],
                    "namespace": orig["namespace"],
                    "translation": trans_text,
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

            return (chunk_index, [], f"Chunk {chunk_index + 1}: {error_str}")

    return (chunk_index, [], f"Chunk {chunk_index + 1}: Max retries ({MAX_RETRIES}) erreicht")


# --- DB-Writer ---


def write_results_to_db(db_path, all_results, target_lang='en'):
    """
    Schreibt Uebersetzungs-Ergebnisse gesammelt in die DB.
    Single-threaded, wird NACH allen API-Calls aufgerufen.
    """
    conn = sqlite3.connect(str(db_path))
    now = datetime.now().isoformat()
    success = 0
    errors = 0

    for item in all_results:
        try:
            conn.execute(
                f"INSERT INTO {TABLE} "
                "(key, namespace, language, value, is_verified, source, created_at, updated_at) "
                f"VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
                (item["key"], item["namespace"], target_lang, item["translation"],
                 SOURCE_TAG, now, now),
            )
            success += 1
        except sqlite3.IntegrityError:
            errors += 1
        except Exception as e:
            print(f"  [DB-ERROR] {item['key']}: {e}")
            errors += 1

    conn.commit()
    conn.close()
    return (success, errors)


# --- Haupt-Orchestrierung ---


def run_swarm(source_lang="de", target_lang="en", namespace=None,
              chunk_size=DEFAULT_CHUNK_SIZE, workers=DEFAULT_WORKERS,
              limit=0, dry_run=False):
    """Schwarm-Übersetzung mit Epstein-Methode."""
    db_path = get_db_path()

    # 1. Fehlende laden
    missing = get_missing_translations(db_path, namespace, limit, target_lang)

    if not missing:
        target_name = LANGUAGE_NAMES.get(target_lang, target_lang)
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
    api_key = get_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    # 4. Parallel uebersetzen
    all_results = []
    all_errors = []
    completed = 0
    lock = threading.Lock()
    start_time = time.time()

    print(f"\n[SWARM] Starte Uebersetzung mit {workers} Workern...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(translate_chunk, client, chunk, i, len(chunks), target_lang): i
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
    print(f"  ERGEBNIS")
    print(f"{'=' * 60}")
    print(f"  Gesamt zu übersetzen:   {len(missing)}")
    print(f"  Erfolgreich übersetzt:  {len(all_results)}")
    print(f"  Fehler (API):           {len(all_errors)}")
    print(f"  Dauer:                  {elapsed:.1f}s")
    print(f"  Chunks:                 {len(chunks)} (a {chunk_size} Texte)")
    print(f"  Parallele Worker:       {workers}")
    print(f"{'=' * 60}")

    if all_errors:
        print("\n[FEHLER-DETAILS]:")
        for err in all_errors:
            print(f"  - {err}")

    return len(all_errors) == 0


def show_inventory(namespace=None, target_lang='en'):
    """Zeigt Inventar der fehlenden Übersetzungen."""
    db_path = get_db_path()
    target_name = LANGUAGE_NAMES.get(target_lang, target_lang)
    missing = get_missing_translations(db_path, namespace, target_lang=target_lang)

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
        description="Schwarm-Übersetzung mit Epstein-Methode (SQ062)"
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
        help="Max. Texte übersetzen (0 = alle)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, kein API-Call")
    parser.add_argument("--inventory", action="store_true", help="Inventar anzeigen")
    parser.add_argument("--source", default="de", help="Quellsprache (default: de)")
    parser.add_argument("--target", default="en", help="Zielsprache (default: en)")

    args = parser.parse_args()

    if args.inventory:
        show_inventory(args.namespace, args.target)
        return

    success = run_swarm(
        source_lang=args.source,
        target_lang=args.target,
        namespace=args.namespace,
        chunk_size=args.chunk_size,
        workers=args.workers,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
