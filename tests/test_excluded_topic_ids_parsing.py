"""Tests for the ``EXCLUDED_TOPIC_IDS`` parsing in ``config.load_config``.

Covers the optional integer-list helper added to break the bot's
feedback loop on topics where the bot itself posts summaries.
"""

from __future__ import annotations

import pytest

from config import load_config


_REQUIRED_TELEGRAM_ENV = {
    "TELEGRAM_API_ID": "1",
    "TELEGRAM_API_HASH": "hash",
    "TELEGRAM_PHONE": "+490000000000",
    "TELEGRAM_GROUP_NAME": "group",
    "TELEGRAM_BOT_TOKEN": "token",
    "TELEGRAM_CHAT_ID": "1",
    "ANTHROPIC_API_KEY": "key",
}


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable_name, variable_value in _REQUIRED_TELEGRAM_ENV.items():
        monkeypatch.setenv(variable_name, variable_value)


def test_excluded_topic_ids_defaults_to_empty_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("EXCLUDED_TOPIC_IDS", raising=False)

    config = load_config()

    assert config.excluded_topic_ids == ()


def test_excluded_topic_ids_defaults_to_empty_when_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("EXCLUDED_TOPIC_IDS", "")

    config = load_config()

    assert config.excluded_topic_ids == ()


def test_excluded_topic_ids_parses_single_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("EXCLUDED_TOPIC_IDS", "32391")

    config = load_config()

    assert config.excluded_topic_ids == (32391,)


def test_excluded_topic_ids_parses_comma_separated_list_with_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("EXCLUDED_TOPIC_IDS", "32391, 12345 ,7")

    config = load_config()

    assert config.excluded_topic_ids == (32391, 12345, 7)


def test_excluded_topic_ids_rejects_non_integer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("EXCLUDED_TOPIC_IDS", "abc")

    with pytest.raises(SystemExit) as exit_info:
        load_config()

    assert exit_info.value.code == 1
