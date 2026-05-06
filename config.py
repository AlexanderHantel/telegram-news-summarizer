"""Environment-driven configuration loader.

Fails fast at startup with a single error naming the offending variable
before any Telegram, Claude, or bot interaction happens. No secret value
is ever logged.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from logger import get_logger


_DEFAULT_LOOKBACK_HOURS = 24
_DEFAULT_LOG_LEVEL = "INFO"
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO"}
_FIXED_SESSION_PATH = Path("telegram.session")


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration.

    All required fields are validated at construction time in
    :func:`load_config`. ``session_path`` is intentionally not read from the
    environment — it is a deployment detail, not a tunable.
    """

    telegram_api_id: int
    telegram_api_hash: str
    telegram_phone: str
    telegram_group_name: str
    telegram_bot_token: str
    telegram_chat_id: int
    anthropic_api_key: str
    lookback_hours: int
    log_level: str
    anthropic_model: str
    excluded_topic_ids: tuple[int, ...]
    session_path: Path


class _ConfigError(Exception):
    """Raised internally when a variable fails validation."""


def _read_required_string(environment: dict[str, str], variable_name: str) -> str:
    raw_value = environment.get(variable_name, "").strip()
    if not raw_value:
        raise _ConfigError(f"Missing required environment variable: {variable_name}")
    return raw_value


def _read_required_integer(environment: dict[str, str], variable_name: str) -> int:
    raw_value = _read_required_string(environment, variable_name)
    try:
        return int(raw_value)
    except ValueError as conversion_error:
        raise _ConfigError(
            f"Environment variable {variable_name} must be an integer"
        ) from conversion_error


def _read_optional_integer(
    environment: dict[str, str],
    variable_name: str,
    default_value: int,
) -> int:
    raw_value = environment.get(variable_name, "").strip()
    if not raw_value:
        return default_value
    try:
        return int(raw_value)
    except ValueError as conversion_error:
        raise _ConfigError(
            f"Environment variable {variable_name} must be an integer"
        ) from conversion_error


def _read_optional_string(
    environment: dict[str, str],
    variable_name: str,
    default_value: str,
) -> str:
    raw_value = environment.get(variable_name, "").strip()
    return raw_value if raw_value else default_value


def _read_optional_integer_list(
    environment: dict[str, str],
    variable_name: str,
) -> tuple[int, ...]:
    raw_value = environment.get(variable_name, "").strip()
    if not raw_value:
        return ()
    parsed_values: list[int] = []
    for raw_token in raw_value.split(","):
        token = raw_token.strip()
        if not token:
            continue
        try:
            parsed_values.append(int(token))
        except ValueError as conversion_error:
            raise _ConfigError(
                f"Environment variable {variable_name} must be a "
                "comma-separated list of integers"
            ) from conversion_error
    return tuple(parsed_values)


def load_config() -> Config:
    """Load ``.env``, validate every variable, return a frozen :class:`Config`.

    On any validation failure, log exactly one error naming the offending
    variable and exit with a non-zero status before any network call.
    """
    load_dotenv()
    import os

    environment = dict(os.environ)
    logger = get_logger("config")

    try:
        telegram_api_id = _read_required_integer(environment, "TELEGRAM_API_ID")
        telegram_api_hash = _read_required_string(environment, "TELEGRAM_API_HASH")
        telegram_phone = _read_required_string(environment, "TELEGRAM_PHONE")
        telegram_group_name = _read_required_string(environment, "TELEGRAM_GROUP_NAME")
        telegram_bot_token = _read_required_string(environment, "TELEGRAM_BOT_TOKEN")
        telegram_chat_id = _read_required_integer(environment, "TELEGRAM_CHAT_ID")
        anthropic_api_key = _read_required_string(environment, "ANTHROPIC_API_KEY")

        lookback_hours = _read_optional_integer(
            environment, "LOOKBACK_HOURS", _DEFAULT_LOOKBACK_HOURS
        )
        if lookback_hours <= 0:
            raise _ConfigError(
                "Environment variable LOOKBACK_HOURS must be greater than 0"
            )

        log_level = _read_optional_string(
            environment, "LOG_LEVEL", _DEFAULT_LOG_LEVEL
        ).upper()
        if log_level not in _ALLOWED_LOG_LEVELS:
            raise _ConfigError(
                "Environment variable LOG_LEVEL must be DEBUG or INFO"
            )

        anthropic_model = _read_optional_string(
            environment, "ANTHROPIC_MODEL", _DEFAULT_ANTHROPIC_MODEL
        )

        excluded_topic_ids = _read_optional_integer_list(
            environment, "EXCLUDED_TOPIC_IDS"
        )
    except _ConfigError as validation_error:
        logger.error(str(validation_error))
        sys.exit(1)

    return Config(
        telegram_api_id=telegram_api_id,
        telegram_api_hash=telegram_api_hash,
        telegram_phone=telegram_phone,
        telegram_group_name=telegram_group_name,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        anthropic_api_key=anthropic_api_key,
        lookback_hours=lookback_hours,
        log_level=log_level,
        anthropic_model=anthropic_model,
        excluded_topic_ids=excluded_topic_ids,
        session_path=_FIXED_SESSION_PATH,
    )
