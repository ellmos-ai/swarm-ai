# -*- coding: utf-8 -*-
"""
test_summarize_chunks.py -- Tests for summarize_chunks.py.

Tests the ChunkSummarizer class logic without real API calls.
"""
import sqlite3
import pytest

from tools.summarize_chunks import (
    ChunkSummarizer,
    MODELS,
    COST_PER_1M,
    SYSTEM_PROMPT,
    MAX_RETRIES,
)


class TestChunkSummarizerInit:
    """Tests for ChunkSummarizer construction."""

    def test_default_model(self):
        summarizer = ChunkSummarizer(model="haiku")
        assert summarizer.model == "haiku"
        assert summarizer.model_id == MODELS["haiku"]
        assert summarizer.client is None
        assert summarizer.run_id is None

    def test_sonnet_model(self):
        summarizer = ChunkSummarizer(model="sonnet")
        assert summarizer.model_id == MODELS["sonnet"]

    def test_unknown_model_is_rejected(self):
        with pytest.raises(ValueError, match="unknown"):
            ChunkSummarizer(model="unknown")

    def test_initial_stats(self):
        summarizer = ChunkSummarizer()
        assert summarizer.stats["chunks_processed"] == 0
        assert summarizer.stats["chunks_summarized"] == 0
        assert summarizer.stats["errors"] == 0
        assert summarizer.stats["total_input_tokens"] == 0
        assert summarizer.stats["total_output_tokens"] == 0
        assert summarizer.stats["total_cost_usd"] == 0.0


class TestTokenTracking:
    """Tests for token and cost tracking."""

    def test_track_tokens_haiku(self):
        summarizer = ChunkSummarizer(model="haiku")
        summarizer._track_tokens(1000, 500)

        assert summarizer.stats["total_input_tokens"] == 1000
        assert summarizer.stats["total_output_tokens"] == 500

        # Cost: (1000 * 1.00 + 500 * 5.00) / 1_000_000 = 0.0035
        expected_cost = (1000 * 1.00 + 500 * 5.00) / 1_000_000
        assert abs(summarizer.stats["total_cost_usd"] - expected_cost) < 1e-10

    def test_track_tokens_sonnet(self):
        summarizer = ChunkSummarizer(model="sonnet")
        summarizer._track_tokens(1000, 500)

        expected_cost = (1000 * 3.00 + 500 * 15.00) / 1_000_000
        assert abs(summarizer.stats["total_cost_usd"] - expected_cost) < 1e-10

    def test_track_tokens_accumulates(self):
        summarizer = ChunkSummarizer(model="haiku")
        summarizer._track_tokens(100, 50)
        summarizer._track_tokens(200, 100)

        assert summarizer.stats["total_input_tokens"] == 300
        assert summarizer.stats["total_output_tokens"] == 150


class TestSummarizeChunk:
    """Tests for the summarize_chunk method with mocked API."""

    def test_successful_summary(self, mock_anthropic_client):
        summarizer = ChunkSummarizer(model="haiku")
        summarizer.client = mock_anthropic_client

        mock_anthropic_client.messages.create.return_value = (
            mock_anthropic_client._make_response(
                "Dies ist eine Zusammenfassung des Textes.", 100, 30
            )
        )

        result = summarizer.summarize_chunk("Ein langer Text zum Zusammenfassen...")
        assert result == "Dies ist eine Zusammenfassung des Textes."
        assert summarizer.stats["total_input_tokens"] == 100
        assert summarizer.stats["total_output_tokens"] == 30

    def test_api_error_returns_none(self, mock_anthropic_client):
        summarizer = ChunkSummarizer(model="haiku")
        summarizer.client = mock_anthropic_client

        mock_anthropic_client.messages.create.side_effect = Exception("API error")

        result = summarizer.summarize_chunk("Text")
        assert result is None


class TestModelsAndCosts:
    """Tests for model and cost configuration."""

    def test_haiku_model_id(self):
        assert "haiku" in MODELS["haiku"]

    def test_sonnet_model_id(self):
        assert "sonnet" in MODELS["sonnet"]

    def test_haiku_costs(self):
        assert COST_PER_1M["haiku"]["input"] == 1.00
        assert COST_PER_1M["haiku"]["output"] == 5.00

    def test_sonnet_costs(self):
        assert COST_PER_1M["sonnet"]["input"] == 3.00
        assert COST_PER_1M["sonnet"]["output"] == 15.00

    def test_sonnet_more_expensive_than_haiku(self):
        assert COST_PER_1M["sonnet"]["input"] > COST_PER_1M["haiku"]["input"]
        assert COST_PER_1M["sonnet"]["output"] > COST_PER_1M["haiku"]["output"]


class TestSystemPrompt:
    """Tests for the system prompt configuration."""

    def test_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 50

    def test_prompt_mentions_summary(self):
        assert "zusammen" in SYSTEM_PROMPT.lower() or "Zusammenfassung" in SYSTEM_PROMPT

    def test_max_retries(self):
        assert MAX_RETRIES >= 1
        assert MAX_RETRIES <= 10


class TestGetUnsummarizedChunks:
    """Test chunk loading from DB."""

    def test_with_empty_db(self, tmp_path):
        """Should return empty list when no chunks exist."""
        db_path = tmp_path / "test_chunks.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE document_chunks (
                id INTEGER PRIMARY KEY,
                search_index_id INTEGER,
                chunk_number INTEGER,
                chunk_text TEXT,
                chunk_tokens INTEGER,
                summary TEXT
            )
        """)
        conn.commit()
        conn.close()

        summarizer = ChunkSummarizer(model="haiku", db_path=db_path)
        chunks = summarizer.get_unsummarized_chunks()
        assert chunks == []

    def test_returns_only_unsummarized(self, tmp_path):
        """Should only return chunks where summary IS NULL."""
        db_path = tmp_path / "test_chunks.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE document_chunks (
                id INTEGER PRIMARY KEY,
                search_index_id INTEGER,
                chunk_number INTEGER,
                chunk_text TEXT,
                chunk_tokens INTEGER,
                summary TEXT
            )
        """)
        conn.execute(
            "INSERT INTO document_chunks VALUES (1, 1, 1, 'Text A', 50, NULL)"
        )
        conn.execute(
            "INSERT INTO document_chunks VALUES (2, 1, 2, 'Text B', 60, 'Already summarized')"
        )
        conn.execute(
            "INSERT INTO document_chunks VALUES (3, 2, 1, 'Text C', 40, NULL)"
        )
        conn.commit()
        conn.close()

        summarizer = ChunkSummarizer(model="haiku", db_path=db_path)
        chunks = summarizer.get_unsummarized_chunks()
        assert len(chunks) == 2
        assert chunks[0]["chunk_text"] == "Text A"
        assert chunks[1]["chunk_text"] == "Text C"

    def test_respects_limit(self, tmp_path):
        db_path = tmp_path / "test_chunks.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE document_chunks (
                id INTEGER PRIMARY KEY,
                search_index_id INTEGER,
                chunk_number INTEGER,
                chunk_text TEXT,
                chunk_tokens INTEGER,
                summary TEXT
            )
        """)
        for i in range(10):
            conn.execute(
                f"INSERT INTO document_chunks VALUES ({i+1}, 1, {i+1}, 'Text {i}', 50, NULL)"
            )
        conn.commit()
        conn.close()

        summarizer = ChunkSummarizer(model="haiku", db_path=db_path)
        chunks = summarizer.get_unsummarized_chunks(limit=3)
        assert len(chunks) == 3

    def test_rejects_non_positive_limit(self, tmp_path):
        summarizer = ChunkSummarizer(db_path=tmp_path / "missing.db")
        with pytest.raises(ValueError, match="limit"):
            summarizer.get_unsummarized_chunks(limit=0)


class TestStandaloneSchema:
    def test_initializes_new_database(self, tmp_path):
        db_path = tmp_path / "data" / "chunks.db"
        summarizer = ChunkSummarizer(db_path=db_path)
        summarizer.initialize_schema()
        assert db_path.exists()
        assert summarizer.get_unsummarized_chunks() == []

    def test_chunk_claim_is_exclusive(self, tmp_path):
        db_path = tmp_path / "chunks.db"
        first = ChunkSummarizer(db_path=db_path)
        first.initialize_schema()
        first.run_id = 1
        first._prepare_claims()
        second = ChunkSummarizer(db_path=db_path)
        second.run_id = 2
        assert first._claim_chunk(42) is True
        assert second._claim_chunk(42) is False
        first._release_chunk(42)
        assert second._claim_chunk(42) is True

    def test_live_request_requires_limit_and_budget(self, tmp_path):
        summarizer = ChunkSummarizer(db_path=tmp_path / "chunks.db")
        chunk = [{"chunk_text": "short"}]
        with pytest.raises(ValueError, match="positive limit"):
            summarizer._validate_request_budget(chunk, None, 1.0, False)
        with pytest.raises(ValueError, match="max_budget"):
            summarizer._validate_request_budget(chunk, 1, None, False)
        for budget in (float("nan"), float("inf")):
            with pytest.raises(ValueError, match="finite"):
                summarizer._validate_request_budget(chunk, 1, budget, False)

    def test_summary_budget_bound_includes_all_retries(self, tmp_path):
        summarizer = ChunkSummarizer(db_path=tmp_path / "chunks.db")
        chunk = [{"chunk_text": "x" * 1000}]
        bound = summarizer._validate_request_budget(chunk, 1, None, True)
        prompt_overhead = len(
            "Fasse den folgenden Text-Chunk zusammen:\n\n---\n\n---".encode("utf-8")
        )
        one_attempt = (
            (1000 + len(SYSTEM_PROMPT.encode("utf-8")) + prompt_overhead)
            * COST_PER_1M["haiku"]["input"]
            + 256 * COST_PER_1M["haiku"]["output"]
        ) / 1_000_000
        assert bound == pytest.approx(one_attempt * MAX_RETRIES)

    def test_save_summary_refuses_concurrent_overwrite(self, tmp_path):
        summarizer = ChunkSummarizer(db_path=tmp_path / "chunks.db")
        summarizer.initialize_schema()
        with summarizer._db() as conn:
            chunk_id = conn.execute(
                "INSERT INTO document_chunks (chunk_number, chunk_text) VALUES (1, 'x')"
            ).lastrowid
        summarizer.save_summary(chunk_id, "first")
        with pytest.raises(RuntimeError, match="concurrently"):
            summarizer.save_summary(chunk_id, "second")

    def test_failed_wrapper_closes_run_ledger(self, tmp_path, monkeypatch):
        db_path = tmp_path / "chunks.db"
        summarizer = ChunkSummarizer(db_path=db_path)
        summarizer.initialize_schema()

        def interrupted(*args, **kwargs):
            summarizer.run_id = summarizer._create_run()
            summarizer._prepare_claims()
            assert summarizer._claim_chunk(99)
            raise KeyboardInterrupt("stop")

        monkeypatch.setattr(summarizer, "_run", interrupted)
        with pytest.raises(KeyboardInterrupt):
            summarizer.run(limit=1, max_budget_usd=1)
        with sqlite3.connect(db_path) as conn:
            status, finished = conn.execute(
                "SELECT status, finished_at FROM parallel_chunks_runs"
            ).fetchone()
            claims = conn.execute("SELECT COUNT(*) FROM swarm_chunk_claims").fetchone()[0]
        assert status == "failed"
        assert finished is not None
        assert claims == 0

    def test_reusing_instance_resets_per_run_stats(self, tmp_path, monkeypatch):
        summarizer = ChunkSummarizer(db_path=tmp_path / "chunks.db")

        def one_chunk(*args, **kwargs):
            summarizer.stats["chunks_processed"] += 1
            summarizer.stats["total_input_tokens"] += 10
            return dict(summarizer.stats)

        monkeypatch.setattr(summarizer, "_run", one_chunk)
        first = summarizer.run(dry_run=True)
        second = summarizer.run(dry_run=True)
        assert first["chunks_processed"] == second["chunks_processed"] == 1
        assert first["total_input_tokens"] == second["total_input_tokens"] == 10
