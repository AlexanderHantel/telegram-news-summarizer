"""Telegram Bot API delivery.

Plain HTTP POST via ``requests`` — no bot SDK (plan.md Phase 0 Decision 3).
The long-message splitter preserves byte-for-byte equality between the
concatenation of delivered chunks and the original payload (FR-018, SC-006).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests

from logger import get_logger

if TYPE_CHECKING:
    from config import Config


_TELEGRAM_MAX_MESSAGE_LENGTH = 4096
_TELEGRAM_API_BASE_URL = "https://api.telegram.org"
_PARAGRAPH_SEPARATOR = "\n\n"
_REQUEST_TIMEOUT_SECONDS = 30


def send_message(text: str, config: "Config") -> None:
    """POST a single message ≤ 4096 characters to the operator's bot DM.

    Raises :class:`requests.HTTPError` on any non-2xx response so callers can
    classify the failure via the graceful-failure path.
    """
    if len(text) > _TELEGRAM_MAX_MESSAGE_LENGTH:
        raise ValueError(
            "send_message requires text <= 4096 characters; "
            "use send_long_message for longer payloads"
        )

    logger = get_logger("bot_sender")
    endpoint_url = (
        f"{_TELEGRAM_API_BASE_URL}/bot{config.telegram_bot_token}/sendMessage"
    )
    response = requests.post(
        endpoint_url,
        data={"chat_id": config.telegram_chat_id, "text": text},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    logger.info(
        "Bot delivery: chars=%d status=%d",
        len(text),
        response.status_code,
    )
    response.raise_for_status()


def _split_long_paragraph_by_character_budget(
    paragraph_text: str,
) -> list[str]:
    hard_chunks: list[str] = []
    cursor_position = 0
    while cursor_position < len(paragraph_text):
        hard_chunks.append(
            paragraph_text[
                cursor_position : cursor_position + _TELEGRAM_MAX_MESSAGE_LENGTH
            ]
        )
        cursor_position += _TELEGRAM_MAX_MESSAGE_LENGTH
    return hard_chunks


def _split_into_delivery_chunks(text: str) -> list[str]:
    if len(text) <= _TELEGRAM_MAX_MESSAGE_LENGTH:
        return [text]

    paragraphs_with_separators: list[str] = []
    raw_paragraphs = text.split(_PARAGRAPH_SEPARATOR)
    for paragraph_index, paragraph_text in enumerate(raw_paragraphs):
        if paragraph_index < len(raw_paragraphs) - 1:
            paragraphs_with_separators.append(paragraph_text + _PARAGRAPH_SEPARATOR)
        else:
            paragraphs_with_separators.append(paragraph_text)

    delivery_chunks: list[str] = []
    accumulated_chunk = ""
    for paragraph_with_separator in paragraphs_with_separators:
        if len(paragraph_with_separator) > _TELEGRAM_MAX_MESSAGE_LENGTH:
            if accumulated_chunk:
                delivery_chunks.append(accumulated_chunk)
                accumulated_chunk = ""
            delivery_chunks.extend(
                _split_long_paragraph_by_character_budget(paragraph_with_separator)
            )
            continue

        candidate_chunk = accumulated_chunk + paragraph_with_separator
        if len(candidate_chunk) <= _TELEGRAM_MAX_MESSAGE_LENGTH:
            accumulated_chunk = candidate_chunk
        else:
            if accumulated_chunk:
                delivery_chunks.append(accumulated_chunk)
            accumulated_chunk = paragraph_with_separator

    if accumulated_chunk:
        delivery_chunks.append(accumulated_chunk)

    return delivery_chunks


def send_long_message(text: str, config: "Config") -> None:
    """Deliver ``text`` in one or more sequential ≤4096-char chunks.

    Splits preferentially on ``\\n\\n`` paragraph boundaries and falls back
    to hard character splits only for paragraphs that already exceed 4096
    characters. The concatenation of delivered chunks equals ``text``
    verbatim — no inserted prefixes, suffixes, or ordinals (FR-018, SC-006).
    """
    if not text:
        return

    delivery_chunks = _split_into_delivery_chunks(text)
    for chunk_index, chunk_text in enumerate(delivery_chunks, start=1):
        send_message(chunk_text, config)
        get_logger("bot_sender").debug(
            "Delivered chunk %d/%d", chunk_index, len(delivery_chunks)
        )
