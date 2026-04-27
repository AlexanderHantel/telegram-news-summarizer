"""Telethon-based MTProto reader for the target group.

Handles both forum-topic supergroups (one bucket per topic, ordered by
ascending topic id) and regular groups (a single bucket keyed by the group
display name). Telethon's built-in FloodWait handling is relied upon — no
custom retry loop is layered on top (plan.md Phase 0 Decision 1, FR-026b).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Sequence

from telethon import TelegramClient
from telethon.tl import functions, types

from logger import get_logger

if TYPE_CHECKING:
    from config import Config


_EMPTY_SENDER_PLACEHOLDER = "Unknown"
_FORUM_TOPICS_PAGE_LIMIT = 100


@dataclass(frozen=True)
class Message:
    """One Telegram message collected within the lookback window."""

    message_id: int
    sender: str
    timestamp: datetime
    text: str
    reply_to_id: int | None


def serialize_messages(messages: list[Message]) -> str:
    """Produce the string that fills the ``{{messages}}`` prompt placeholder.

    One line per message, chronological order. Reply-to indicator only
    appears when the parent lies inside the collected window.
    """
    chronological_messages = sorted(messages, key=lambda entry: entry.timestamp)
    serialized_lines: list[str] = []
    for message in chronological_messages:
        iso_timestamp = message.timestamp.strftime("%Y-%m-%dT%H:%M:%S")
        sender_label = message.sender if message.sender else _EMPTY_SENDER_PLACEHOLDER
        if message.reply_to_id is not None:
            serialized_lines.append(
                f"[{iso_timestamp}] {sender_label} [reply to: {message.reply_to_id}]: {message.text}"
            )
        else:
            serialized_lines.append(
                f"[{iso_timestamp}] {sender_label}: {message.text}"
            )
    return "\n".join(serialized_lines)


def _format_sender_display_name(raw_sender: Any) -> str:
    if raw_sender is None:
        return _EMPTY_SENDER_PLACEHOLDER
    first_name = getattr(raw_sender, "first_name", None) or ""
    last_name = getattr(raw_sender, "last_name", None) or ""
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name
    username = getattr(raw_sender, "username", None)
    if username:
        return f"@{username}"
    title = getattr(raw_sender, "title", None)
    if title:
        return title
    return _EMPTY_SENDER_PLACEHOLDER


def _extract_parent_message_id(raw_message: Any) -> int | None:
    reply_descriptor = getattr(raw_message, "reply_to", None)
    if reply_descriptor is None:
        return None
    parent_id = getattr(reply_descriptor, "reply_to_msg_id", None)
    if parent_id is None:
        return None
    return int(parent_id)


async def _collect_topic_buckets(
    telegram_client: TelegramClient,
    group_entity: Any,
    window_start_utc: datetime,
    logger: Any,
) -> dict[str, list[Message]]:
    """Return a dict keyed by forum topic title in ascending topic-id order."""
    topics_response = await telegram_client(
        functions.channels.GetForumTopicsRequest(
            channel=group_entity,
            offset_date=None,
            offset_id=0,
            offset_topic=0,
            limit=_FORUM_TOPICS_PAGE_LIMIT,
        )
    )

    topic_entries = [
        forum_topic
        for forum_topic in topics_response.topics
        if isinstance(forum_topic, types.ForumTopic)
    ]
    topic_entries.sort(key=lambda topic: topic.id)

    logger.info(
        "Detected %d forum topic(s) in group '%s'",
        len(topic_entries),
        getattr(group_entity, "title", "<unknown>"),
    )

    topic_buckets: dict[str, list[Message]] = {}
    for topic_entry in topic_entries:
        topic_messages = await _read_messages_for_topic(
            telegram_client=telegram_client,
            group_entity=group_entity,
            topic_id=topic_entry.id,
            window_start_utc=window_start_utc,
        )
        topic_buckets[topic_entry.title] = topic_messages
        logger.info(
            "Topic '%s' (id=%d): collected %d message(s) in window",
            topic_entry.title,
            topic_entry.id,
            len(topic_messages),
        )
    return topic_buckets


async def _read_messages_for_topic(
    telegram_client: TelegramClient,
    group_entity: Any,
    topic_id: int,
    window_start_utc: datetime,
) -> list[Message]:
    collected_raw_messages: list[Any] = []
    collected_ids_in_window: set[int] = set()

    async for raw_message in telegram_client.iter_messages(
        group_entity,
        reply_to=topic_id,
    ):
        message_timestamp = raw_message.date
        if message_timestamp is None:
            continue
        if message_timestamp < window_start_utc:
            break
        collected_ids_in_window.add(raw_message.id)
        collected_raw_messages.append(raw_message)

    return _convert_raw_messages_to_dataclass(
        raw_messages=collected_raw_messages,
        ids_in_window=collected_ids_in_window,
        topic_root_id=topic_id,
    )


async def _read_messages_for_plain_group(
    telegram_client: TelegramClient,
    group_entity: Any,
    window_start_utc: datetime,
) -> list[Message]:
    collected_raw_messages: list[Any] = []
    collected_ids_in_window: set[int] = set()

    async for raw_message in telegram_client.iter_messages(group_entity):
        message_timestamp = raw_message.date
        if message_timestamp is None:
            continue
        if message_timestamp < window_start_utc:
            break
        collected_ids_in_window.add(raw_message.id)
        collected_raw_messages.append(raw_message)

    return _convert_raw_messages_to_dataclass(
        raw_messages=collected_raw_messages,
        ids_in_window=collected_ids_in_window,
        topic_root_id=None,
    )


def _convert_raw_messages_to_dataclass(
    raw_messages: Sequence[Any],
    ids_in_window: set[int],
    topic_root_id: int | None,
) -> list[Message]:
    converted_messages: list[Message] = []
    for raw_message in raw_messages:
        parent_id = _extract_parent_message_id(raw_message)
        if parent_id is not None and parent_id == topic_root_id:
            parent_id = None
        if parent_id is not None and parent_id not in ids_in_window:
            parent_id = None

        sender_display_name = _format_sender_display_name(
            getattr(raw_message, "sender", None)
        )
        message_timestamp = raw_message.date
        if message_timestamp.tzinfo is None:
            message_timestamp = message_timestamp.replace(tzinfo=timezone.utc)
        else:
            message_timestamp = message_timestamp.astimezone(timezone.utc)

        converted_messages.append(
            Message(
                message_id=int(raw_message.id),
                sender=sender_display_name,
                timestamp=message_timestamp,
                text=raw_message.message or "",
                reply_to_id=parent_id,
            )
        )
    converted_messages.sort(key=lambda entry: entry.timestamp)
    return converted_messages


def get_messages(config: Config) -> dict[str, list[Message]]:
    """Read the target group's messages within ``lookback_hours``.

    Detects forum-topic vs regular group automatically (FR-008). Returns a
    dict keyed by topic-chat display name; iteration order is ascending
    topic id (stable delivery order for FR-019). For non-forum groups the
    dict contains a single entry keyed by the group display name.
    """
    logger = get_logger("telegram_reader")
    logger.info(
        "Session file %s at path %s",
        "reuse" if config.session_path.exists() else "first-run login",
        config.session_path,
    )

    telegram_client = TelegramClient(
        session=str(config.session_path),
        api_id=config.telegram_api_id,
        api_hash=config.telegram_api_hash,
    )

    async def _run() -> dict[str, list[Message]]:
        await telegram_client.start(phone=config.telegram_phone)
        try:
            group_entity: Any = await telegram_client.get_entity(
                config.telegram_group_name
            )
            window_start_utc = datetime.now(timezone.utc) - timedelta(
                hours=config.lookback_hours
            )

            is_forum_group = bool(getattr(group_entity, "forum", False))
            logger.info(
                "Group '%s' resolved (forum=%s), window start %s",
                config.telegram_group_name,
                is_forum_group,
                window_start_utc.isoformat(),
            )

            if is_forum_group:
                return await _collect_topic_buckets(
                    telegram_client=telegram_client,
                    group_entity=group_entity,
                    window_start_utc=window_start_utc,
                    logger=logger,
                )

            plain_group_messages = await _read_messages_for_plain_group(
                telegram_client=telegram_client,
                group_entity=group_entity,
                window_start_utc=window_start_utc,
            )
            bucket_key = (
                getattr(group_entity, "title", None) or config.telegram_group_name
            )
            logger.info(
                "Non-forum group '%s': collected %d message(s) in window",
                bucket_key,
                len(plain_group_messages),
            )
            return {bucket_key: plain_group_messages}
        finally:
            await telegram_client.disconnect()

    return telegram_client.loop.run_until_complete(_run())
