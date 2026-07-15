# -*- coding: utf-8 -*-
"""
test_translate_swarm.py -- Tests for translate_swarm.py utility functions.

Pure utilities and local SQLite persistence are tested without real API calls.
"""
import pytest
import json
import sqlite3
from unittest.mock import MagicMock

from tools.translate_swarm import (
    chunk_texts,
    get_missing_translations,
    initialize_translation_db,
    claim_translations,
    release_translation_claims,
    validate_translation_request,
    translate_chunk,
    write_results_to_db,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_WORKERS,
    MAX_RETRIES,
    SYSTEM_PROMPT,
    TABLE,
    SOURCE_TAG,
)


class TestChunkTexts:
    """Tests for the chunk_texts utility."""

    def test_exact_division(self):
        items = list(range(10))
        chunks = chunk_texts(items, 5)
        assert len(chunks) == 2
        assert chunks[0] == [0, 1, 2, 3, 4]
        assert chunks[1] == [5, 6, 7, 8, 9]

    def test_remainder(self):
        items = list(range(7))
        chunks = chunk_texts(items, 3)
        assert len(chunks) == 3
        assert chunks[0] == [0, 1, 2]
        assert chunks[1] == [3, 4, 5]
        assert chunks[2] == [6]

    def test_single_chunk(self):
        items = [1, 2, 3]
        chunks = chunk_texts(items, 10)
        assert len(chunks) == 1
        assert chunks[0] == [1, 2, 3]

    def test_empty_list(self):
        chunks = chunk_texts([], 5)
        assert chunks == []

    def test_chunk_size_one(self):
        items = ["a", "b", "c"]
        chunks = chunk_texts(items, 1)
        assert len(chunks) == 3
        assert all(len(c) == 1 for c in chunks)

    def test_zero_chunk_size_is_rejected(self):
        with pytest.raises(ValueError, match="chunk_size"):
            chunk_texts([1], 0)

    def test_preserves_dict_items(self):
        """chunk_texts should work with any list items including dicts."""
        items = [
            {"key": "a", "value": "Hallo"},
            {"key": "b", "value": "Welt"},
            {"key": "c", "value": "Test"},
        ]
        chunks = chunk_texts(items, 2)
        assert len(chunks) == 2
        assert chunks[0][0]["key"] == "a"
        assert chunks[1][0]["key"] == "c"


class TestConstants:
    """Verify that module constants are sane."""

    def test_default_chunk_size(self):
        assert DEFAULT_CHUNK_SIZE > 0
        assert DEFAULT_CHUNK_SIZE <= 50  # Reasonable upper bound

    def test_default_workers(self):
        assert DEFAULT_WORKERS > 0
        assert DEFAULT_WORKERS <= 20

    def test_max_retries(self):
        assert MAX_RETRIES >= 1

    def test_system_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 50

    def test_system_prompt_mentions_json(self):
        """The prompt should instruct the model to return JSON."""
        assert "JSON" in SYSTEM_PROMPT

    def test_table_name(self):
        assert TABLE == "languages_translations"

    def test_source_tag(self):
        assert SOURCE_TAG == "llm_auto_swarm"


class TestTranslationIntegrity:
    def test_live_request_requires_limit_and_budget(self):
        item = [{"key": "a", "namespace": "ui", "value": "Hallo"}]
        with pytest.raises(ValueError, match="positive limit"):
            validate_translation_request(item, 10, 2, 0, 1.0, False)
        with pytest.raises(ValueError, match="max_budget"):
            validate_translation_request(item, 10, 2, 1, None, False)

    def test_request_rejects_oversized_input(self):
        item = [{"key": "a", "namespace": "ui", "value": "x" * 100_001}]
        with pytest.raises(ValueError, match="exceeds"):
            validate_translation_request(item, 10, 2, 1, 10.0, False)

    def test_budget_bound_includes_all_retries(self):
        item = [{"key": "a", "namespace": "ui", "value": "x" * 1000}]
        bound = validate_translation_request(item, 10, 2, 1, None, True)
        serialized_bytes = len(json.dumps([{
            "key": "a", "namespace": "ui", "source_language": "x" * 1000,
        }], ensure_ascii=False, indent=2).encode("utf-8"))
        one_attempt = (
            (serialized_bytes + 4000) * 1.0 + 4096 * 5.0
        ) / 1_000_000
        assert bound == pytest.approx(one_attempt * MAX_RETRIES)
        with pytest.raises(ValueError, match="exceeds budget"):
            validate_translation_request(
                item, 10, 2, 1, one_attempt * 2, False
            )

    @pytest.mark.parametrize("budget", [float("nan"), float("inf")])
    def test_live_request_rejects_nonfinite_budget(self, budget):
        item = [{"key": "a", "namespace": "ui", "value": "Hallo"}]
        with pytest.raises(ValueError, match="finite"):
            validate_translation_request(item, 10, 2, 1, budget, False)

    def test_request_rejects_oversized_identity(self):
        item = [{"key": "k" * 10_001, "namespace": "ui", "value": "Hallo"}]
        with pytest.raises(ValueError, match="identity"):
            validate_translation_request(item, 10, 2, 1, 10.0, False)

    def test_budget_bound_counts_json_control_character_expansion(self):
        plain = [{"key": "a", "namespace": "ui", "value": "x" * 1000}]
        escaped = [{"key": "a", "namespace": "ui", "value": "\x00" * 1000}]
        plain_bound = validate_translation_request(plain, 10, 2, 1, None, True)
        escaped_bound = validate_translation_request(escaped, 10, 2, 1, None, True)
        assert escaped_bound > plain_bound

    def test_claims_prevent_duplicate_api_work(self, tmp_path):
        db_path = tmp_path / "translations.db"
        initialize_translation_db(db_path)
        item = [{"key": "a", "namespace": "ui", "value": "Hallo"}]
        assert claim_translations(db_path, item, "de", "en", "run-a") == item
        assert claim_translations(db_path, item, "de", "en", "run-b") == []
        release_translation_claims(db_path, "run-a")
        assert claim_translations(db_path, item, "de", "en", "run-b") == item

    def test_source_language_is_used_for_selection(self, tmp_path):
        db_path = tmp_path / "translations.db"
        initialize_translation_db(db_path)
        with sqlite3.connect(db_path) as conn:
            now = "2026-01-01T00:00:00+00:00"
            conn.execute(
                f"INSERT INTO {TABLE} (key, namespace, language, value, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("hello", "ui", "en", "Hello", now, now),
            )
        missing = get_missing_translations(
            db_path, target_lang="de", source_lang="en"
        )
        assert [item["key"] for item in missing] == ["hello"]

    def test_null_and_empty_namespace_share_one_identity(self, tmp_path):
        db_path = tmp_path / "translations.db"
        initialize_translation_db(db_path)
        now = "2026-01-01T00:00:00+00:00"
        with sqlite3.connect(db_path) as conn:
            conn.executemany(
                f"INSERT INTO {TABLE} (key, namespace, language, value, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("hello", None, "de", "Hallo", now, now),
                    ("hello", "", "en", "Hello", now, now),
                ],
            )
        assert get_missing_translations(
            db_path, target_lang="en", source_lang="de"
        ) == []

    def test_api_results_are_mapped_by_identity_not_order(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text='''[
          {"key":"b","namespace":"ui","en":"World"},
          {"key":"a","namespace":"ui","en":"Hello"}
        ]''')]
        client.messages.create.return_value = response
        chunk = [
            {"key": "a", "namespace": "ui", "value": "Hallo"},
            {"key": "b", "namespace": "ui", "value": "Welt"},
        ]
        _, mapped, error = translate_chunk(client, chunk, 0, 1)
        assert error is None
        assert [item["translation"] for item in mapped] == ["Hello", "World"]

    def test_api_result_must_preserve_placeholders(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text='''[
          {"key":"hello","namespace":"ui","en":"Hello Alice, %s"}
        ]''')]
        client.messages.create.return_value = response
        chunk = [{
            "key": "hello", "namespace": "ui",
            "value": "Hallo {name}, %s",
        }]
        _, mapped, error = translate_chunk(client, chunk, 0, 1)
        assert mapped == []
        assert "Placeholder mismatch" in error
        assert client.messages.create.call_count == MAX_RETRIES

    def test_blank_existing_row_is_updated(self, tmp_path):
        db_path = tmp_path / "translations.db"
        initialize_translation_db(db_path)
        with sqlite3.connect(db_path) as conn:
            now = "2026-01-01T00:00:00+00:00"
            conn.execute(
                f"INSERT INTO {TABLE} (key, namespace, language, value, created_at, updated_at) "
                "VALUES (?, ?, ?, '', ?, ?)",
                ("hello", None, "en", now, now),
            )
        success, errors = write_results_to_db(
            db_path,
            [{"key": "hello", "namespace": None, "translation": "Hello"}],
            "en",
        )
        assert (success, errors) == (1, 0)
        with sqlite3.connect(db_path) as conn:
            assert conn.execute(
                f"SELECT value FROM {TABLE} WHERE key='hello'"
            ).fetchone()[0] == "Hello"

    def test_standalone_schema_rejects_duplicate_identity(self, tmp_path):
        db_path = tmp_path / "translations.db"
        initialize_translation_db(db_path)
        now = "2026-01-01T00:00:00+00:00"
        values = ("hello", None, "en", "Hello", now, now)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                f"INSERT INTO {TABLE} (key, namespace, language, value, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)", values,
            )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    f"INSERT INTO {TABLE} (key, namespace, language, value, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)", values,
                )

    def test_legacy_duplicate_migration_has_recovery_message(self, tmp_path):
        db_path = tmp_path / "legacy.db"
        now = "2026-01-01T00:00:00+00:00"
        with sqlite3.connect(db_path) as conn:
            conn.execute(f"""
                CREATE TABLE {TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL, namespace TEXT, language TEXT NOT NULL,
                    value TEXT NOT NULL, is_verified INTEGER DEFAULT 0,
                    source TEXT, created_at TEXT, updated_at TEXT
                )
            """)
            null_namespace = ("hello", None, "en", "Hello", now, now)
            empty_namespace = ("hello", "", "en", "Hello", now, now)
            conn.executemany(
                f"INSERT INTO {TABLE} "
                "(key, namespace, language, value, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [null_namespace, empty_namespace],
            )
        with pytest.raises(RuntimeError, match="COALESCE"):
            initialize_translation_db(db_path)
