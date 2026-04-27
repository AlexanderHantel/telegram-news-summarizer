"""Dual-handler logger (stdout + dated file under logs/).

Writes ISO-8601 timestamps and the module name on every line so scheduled-run
transcripts can be correlated across modules without extra tooling.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
_LOGS_DIRECTORY = Path("logs")
_root_configured = False


def _build_log_file_path() -> Path:
    current_date_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _LOGS_DIRECTORY / f"{current_date_iso}.log"


def _configure_root_logger_once(effective_level: int) -> None:
    global _root_configured
    if _root_configured:
        return

    _LOGS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        filename=_build_log_file_path(),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(effective_level)
    root_logger.handlers.clear()
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(file_handler)

    _root_configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger; configures root handlers exactly once.

    The effective level comes from ``Config.log_level`` via the environment
    variable ``LOG_LEVEL`` (defaults to ``INFO``). Resolving the level here
    avoids a circular import between ``logger.py`` and ``config.py``.
    """
    import os

    raw_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    effective_level = logging.DEBUG if raw_level == "DEBUG" else logging.INFO

    _configure_root_logger_once(effective_level=effective_level)
    return logging.getLogger(name)
