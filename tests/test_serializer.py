"""Tests for ``telegram_reader.serialize_messages``.

Pure-helper coverage per plan.md Phase 0 Decision 7.
"""

from __future__ import annotations

from datetime import datetime, timezone

from telegram_reader import Message, serialize_messages


def _build_message(
    message_id: int,
    sender: str,
    timestamp: datetime,
    text: str,
    reply_to_id: int | None = None,
) -> Message:
    return Message(
        message_id=message_id,
        sender=sender,
        timestamp=timestamp,
        text=text,
        reply_to_id=reply_to_id,
    )


def test_serialize_messages_returns_empty_string_for_empty_list() -> None:
    assert serialize_messages([]) == ""


def test_serialize_messages_orders_chronologically() -> None:
    later_message = _build_message(
        message_id=2,
        sender="Alice",
        timestamp=datetime(2026, 4, 24, 10, 30, tzinfo=timezone.utc),
        text="second",
    )
    earlier_message = _build_message(
        message_id=1,
        sender="Bob",
        timestamp=datetime(2026, 4, 24, 9, 15, tzinfo=timezone.utc),
        text="first",
    )

    serialized_output = serialize_messages([later_message, earlier_message])

    assert serialized_output.splitlines() == [
        "[2026-04-24T09:15:00] Bob: first",
        "[2026-04-24T10:30:00] Alice: second",
    ]


def test_serialize_messages_uses_iso_8601_timestamp_format() -> None:
    single_message = _build_message(
        message_id=1,
        sender="Alice",
        timestamp=datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        text="hello",
    )

    serialized_output = serialize_messages([single_message])

    assert serialized_output == "[2026-12-31T23:59:59] Alice: hello"


def test_serialize_messages_prefixes_reply_to_indicator_only_when_parent_is_set() -> None:
    parent_message = _build_message(
        message_id=1,
        sender="Alice",
        timestamp=datetime(2026, 4, 24, 9, 0, tzinfo=timezone.utc),
        text="topic",
    )
    reply_message = _build_message(
        message_id=2,
        sender="Bob",
        timestamp=datetime(2026, 4, 24, 9, 5, tzinfo=timezone.utc),
        text="response",
        reply_to_id=1,
    )

    serialized_output = serialize_messages([parent_message, reply_message])

    assert serialized_output.splitlines() == [
        "[2026-04-24T09:00:00] Alice: topic",
        "[2026-04-24T09:05:00] Bob [reply to: 1]: response",
    ]


def test_serialize_messages_omits_reply_indicator_when_reply_to_id_is_none() -> None:
    single_message = _build_message(
        message_id=1,
        sender="Alice",
        timestamp=datetime(2026, 4, 24, 9, 0, tzinfo=timezone.utc),
        text="standalone",
        reply_to_id=None,
    )

    assert (
        serialize_messages([single_message])
        == "[2026-04-24T09:00:00] Alice: standalone"
    )
