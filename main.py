"""Entry point for the Telegram Group Summarizer.

Orchestrates: config load -> logger init -> Telegram read -> per-chat
Claude summary -> overall Claude summary -> bot delivery. Follows the
graceful per-chat failure contract from Constitution Principle VII — a
single failing chat never aborts the run.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

import requests
from telethon.errors import (
    AuthKeyUnregisteredError,
    SessionRevokedError,
    UserDeactivatedError,
    UserDeactivatedBanError,
)

from bot_sender import send_long_message
from config import load_config
from logger import get_logger
from summarizer import load_prompt, summarize_chat, summarize_overall
from telegram_reader import get_messages

if TYPE_CHECKING:
    from config import Config


_NO_ACTIVITY_HEARTBEAT_MESSAGE_RUSSIAN = (
    "За последние часы в группе не было новой активности."
)
_FAILURE_SECTION_HEADER_RUSSIAN = "Ошибки этого запуска:"
_AUTH_REVOKED_NOTICE_RUSSIAN = (
    "Сессия Telegram отозвана. Требуется повторный вход на хосте summarizer-а."
)

_EXIT_CODE_OK = 0
_EXIT_CODE_DELIVERY_FAILED = 2
_EXIT_CODE_MISSING_OVERALL_PROMPT = 3
_EXIT_CODE_AUTH_REVOKED = 4


def _log_run_start_summary(logger, config: "Config") -> None:
    logger.info(
        "Run start: group='%s' lookback_hours=%d model='%s' log_level=%s",
        config.telegram_group_name,
        config.lookback_hours,
        config.anthropic_model,
        config.log_level,
    )


def _safe_deliver(
    payload_text: str,
    config: "Config",
    logger,
    delivery_label: str,
    delivery_failure_box: list[bool],
) -> None:
    """Deliver ``payload_text`` via send_long_message and trap delivery errors.

    ``delivery_failure_box`` is a mutable single-element list used as an
    out-parameter so that the caller can raise a non-zero exit code once any
    delivery has failed (spec §Edge Cases bot blocked/revoked, FR-020).
    """
    try:
        send_long_message(payload_text, config)
    except (requests.HTTPError, Exception) as delivery_error:  # noqa: BLE001
        logger.exception(
            "Bot delivery failed for '%s' (chars=%d): %r",
            delivery_label,
            len(payload_text),
            delivery_error,
        )
        delivery_failure_box[0] = True


def _build_failures_section(failures: list[tuple[str, str]]) -> str:
    failure_lines = [f"- {chat_name}: {reason}" for chat_name, reason in failures]
    return _FAILURE_SECTION_HEADER_RUSSIAN + "\n" + "\n".join(failure_lines)


def _handle_authentication_revocation(
    config: "Config",
    logger,
    original_error: BaseException,
) -> int:
    logger.exception(
        "Telegram authentication revoked — session file must be recreated: %r",
        original_error,
    )
    try:
        send_long_message(_AUTH_REVOKED_NOTICE_RUSSIAN, config)
    except Exception as delivery_error:  # noqa: BLE001
        logger.exception(
            "Could not deliver auth-revoked notice to bot DM: %r", delivery_error
        )
    return _EXIT_CODE_AUTH_REVOKED


def main() -> int:
    config = load_config()
    logger = get_logger("main")
    run_start_monotonic = time.monotonic()
    _log_run_start_summary(logger=logger, config=config)

    try:
        chat_messages_by_name = get_messages(config)
    except (
        SessionRevokedError,
        AuthKeyUnregisteredError,
        UserDeactivatedError,
        UserDeactivatedBanError,
    ) as authentication_error:
        return _handle_authentication_revocation(
            config=config, logger=logger, original_error=authentication_error
        )

    total_input_messages = sum(
        len(messages_list) for messages_list in chat_messages_by_name.values()
    )
    delivery_failure_box: list[bool] = [False]
    failures: list[tuple[str, str]] = []
    chat_summaries_for_overall: list[tuple[str, str]] = []
    produced_summary_texts: list[tuple[str, str]] = []
    processed_chat_count = 0

    if total_input_messages == 0:
        logger.info(
            "No activity across %d chat(s) in the window — delivering heartbeat",
            len(chat_messages_by_name),
        )
        _safe_deliver(
            payload_text=_NO_ACTIVITY_HEARTBEAT_MESSAGE_RUSSIAN,
            config=config,
            logger=logger,
            delivery_label="no-activity-heartbeat",
            delivery_failure_box=delivery_failure_box,
        )
        return _finalize_run(
            logger=logger,
            run_start_monotonic=run_start_monotonic,
            processed_chat_count=0,
            failure_count=0,
            delivery_count=1,
            delivery_failed=delivery_failure_box[0],
        )

    for chat_name, chat_messages in chat_messages_by_name.items():
        if not chat_messages:
            logger.info("Chat '%s' has no messages in window — skipping", chat_name)
            continue
        try:
            summary_text = summarize_chat(
                chat_name=chat_name, messages=chat_messages, config=config
            )
        except Exception as summarization_error:  # noqa: BLE001
            logger.exception(
                "Per-chat summarization failed for '%s'", chat_name
            )
            failures.append((chat_name, repr(summarization_error)))
            continue

        processed_chat_count += 1
        chat_summaries_for_overall.append((chat_name, summary_text))
        produced_summary_texts.append((chat_name, summary_text))

    for chat_name, summary_text in produced_summary_texts:
        _safe_deliver(
            payload_text=summary_text,
            config=config,
            logger=logger,
            delivery_label=f"chat-summary:{chat_name}",
            delivery_failure_box=delivery_failure_box,
        )

    delivery_count = len(produced_summary_texts)
    if chat_summaries_for_overall:
        try:
            overall_template = load_prompt("overall_summary.md")
        except FileNotFoundError:
            logger.exception(
                "Missing overall prompt — whole-run abort (per-chat summaries "
                "already delivered)"
            )
            _finalize_run(
                logger=logger,
                run_start_monotonic=run_start_monotonic,
                processed_chat_count=processed_chat_count,
                failure_count=len(failures),
                delivery_count=delivery_count,
                delivery_failed=delivery_failure_box[0],
            )
            return _EXIT_CODE_MISSING_OVERALL_PROMPT

        try:
            overall_summary_text = summarize_overall(
                chat_summaries=chat_summaries_for_overall,
                overall_template=overall_template,
                config=config,
            )
        except Exception as overall_error:  # noqa: BLE001
            logger.exception("Overall summary failed")
            failures.append(("overall", repr(overall_error)))
        else:
            _safe_deliver(
                payload_text=overall_summary_text,
                config=config,
                logger=logger,
                delivery_label="overall-summary",
                delivery_failure_box=delivery_failure_box,
            )
            delivery_count += 1

    if failures:
        failures_section_text = _build_failures_section(failures)
        _safe_deliver(
            payload_text=failures_section_text,
            config=config,
            logger=logger,
            delivery_label="failures-section",
            delivery_failure_box=delivery_failure_box,
        )
        delivery_count += 1

    return _finalize_run(
        logger=logger,
        run_start_monotonic=run_start_monotonic,
        processed_chat_count=processed_chat_count,
        failure_count=len(failures),
        delivery_count=delivery_count,
        delivery_failed=delivery_failure_box[0],
    )


def _finalize_run(
    logger,
    run_start_monotonic: float,
    processed_chat_count: int,
    failure_count: int,
    delivery_count: int,
    delivery_failed: bool,
) -> int:
    elapsed_seconds = time.monotonic() - run_start_monotonic
    logger.info(
        "Run end: processed=%d failed=%d sent=%d duration=%.2fs",
        processed_chat_count,
        failure_count,
        delivery_count,
        elapsed_seconds,
    )
    return _EXIT_CODE_DELIVERY_FAILED if delivery_failed else _EXIT_CODE_OK


if __name__ == "__main__":
    sys.exit(main())
