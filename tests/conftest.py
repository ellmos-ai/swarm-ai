# -*- coding: utf-8 -*-
"""
Shared fixtures for swarm-ai test suite.
"""
import sys
import sqlite3
from pathlib import Path

import pytest

# Ensure tools/ is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def stigmergy_db(tmp_path):
    """
    Creates a temporary SQLite DB with the shared_memory_working table
    that StigmergyAPI expects.
    """
    db_path = tmp_path / "test_swarm.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE shared_memory_working (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT,
            session_id TEXT,
            type TEXT DEFAULT 'note',
            content TEXT,
            priority INTEGER DEFAULT 5,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            tags TEXT DEFAULT '[]',
            related_to TEXT
        )
    """)
    conn.commit()
    conn.close()
    return str(db_path)


@pytest.fixture
def mock_anthropic_client():
    """
    Returns a mock Anthropic client that simulates message creation.
    """
    from unittest.mock import MagicMock

    client = MagicMock()

    def make_response(text="Mocked response", input_tokens=10, output_tokens=5):
        message = MagicMock()
        message.content = [MagicMock(text=text)]
        message.usage.input_tokens = input_tokens
        message.usage.output_tokens = output_tokens
        return message

    client._make_response = make_response
    client.messages.create.return_value = make_response()
    return client
