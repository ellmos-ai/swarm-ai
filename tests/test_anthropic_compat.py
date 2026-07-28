"""Compatibility contract for supported Anthropic SDK releases."""

import pytest


anthropic = pytest.importorskip("anthropic")
from anthropic.types import Message  # noqa: E402


def test_sync_client_exposes_messages_create():
    client = anthropic.Anthropic(
        api_key="test-key",
        base_url="http://127.0.0.1:9",
    )
    try:
        assert callable(client.messages.create)
    finally:
        client.close()


def test_message_shape_matches_tool_expectations():
    message = Message(
        id="msg_test",
        type="message",
        role="assistant",
        model="test-model",
        content=[{"type": "text", "text": "ok"}],
        stop_reason="end_turn",
        stop_sequence=None,
        usage={"input_tokens": 1, "output_tokens": 2},
    )

    assert message.content[0].text == "ok"
    assert message.usage.input_tokens == 1
    assert message.usage.output_tokens == 2
