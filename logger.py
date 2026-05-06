"""Zentrale Logger-Einrichtung mit RotatingFileHandler.

Folgt der globalen Logging-Regel (siehe ``~/.claude/rules/logging-konfiguration.md``):

* Ein benannter Projekt-Logger (``telegram_summarizer``) traegt die Handler;
  Modul-Logger sind Kinder dieses Loggers und erben die Handler ueber
  Propagation zum Projekt-Logger (Root-Logger wird nicht konfiguriert).
* Datei-Handler ist ein ``RotatingFileHandler`` mit hardkodiert
  2 MB pro Datei und 10 Backups (UTF-8, append-only).
* Pfad-Variante A: Log-Ordner liegt neben dem Programm
  (``<programmverzeichnis>/logs/anwendung.log``); siehe
  ``specs/001-telegram-group-summarizer/plan.md``.

Die Einrichtung ist idempotent: jeder Aufruf von ``richte_logging_ein``
entfernt vorhandene Handler, sodass Tests den Logger mit einem
``tmp_path`` neu konfigurieren koennen.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJEKT_LOGGER_NAME = "telegram_summarizer"
LOG_DATEI_NAME = "telegram_summarizer.log"
ROTATION_GROESSE_BYTES = 2 * 1024 * 1024
ROTATION_ANZAHL_BACKUPS = 10
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

_ist_eingerichtet = False


def _ermittle_programmverzeichnis() -> Path:
    """Liefert das Verzeichnis, in dem das Programm liegt (Variante A)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(sys.argv[0]).resolve().parent


def _ermittle_log_datei_pfad() -> Path:
    """Default-Pfad fuer die Log-Datei: ``<programmverzeichnis>/logs/anwendung.log``."""
    return _ermittle_programmverzeichnis() / "logs" / LOG_DATEI_NAME


def _ermittle_log_level_aus_umgebung() -> int:
    """Liest ``LOG_LEVEL`` aus der Umgebung; nur ``DEBUG`` und ``INFO`` zulaessig."""
    raw_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    return logging.DEBUG if raw_level == "DEBUG" else logging.INFO


def richte_logging_ein(log_datei_pfad: Path | None = None) -> logging.Logger:
    """Richtet den Projekt-Logger einmalig ein und liefert ihn zurueck.

    * Idempotent: vorhandene Handler werden zuerst entfernt und geschlossen.
    * Legt das Log-Verzeichnis bei Bedarf an.
    * Setzt ``propagate = False`` auf dem Projekt-Logger, damit Eintraege
      nicht zusaetzlich am Root-Logger landen.
    * Akzeptiert einen optionalen Log-Pfad fuer Tests (``tmp_path``).
    """
    global _ist_eingerichtet

    log_pfad = log_datei_pfad if log_datei_pfad is not None else _ermittle_log_datei_pfad()
    log_pfad.parent.mkdir(parents=True, exist_ok=True)

    projekt_logger = logging.getLogger(PROJEKT_LOGGER_NAME)
    projekt_logger.setLevel(_ermittle_log_level_aus_umgebung())
    projekt_logger.propagate = False

    for vorhandener_handler in list(projekt_logger.handlers):
        projekt_logger.removeHandler(vorhandener_handler)
        vorhandener_handler.close()

    formatierer = logging.Formatter(LOG_FORMAT)

    rotierender_datei_handler = RotatingFileHandler(
        filename=log_pfad,
        maxBytes=ROTATION_GROESSE_BYTES,
        backupCount=ROTATION_ANZAHL_BACKUPS,
        encoding="utf-8",
    )
    rotierender_datei_handler.setFormatter(formatierer)
    projekt_logger.addHandler(rotierender_datei_handler)

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(formatierer)
    projekt_logger.addHandler(stdout_handler)

    _ist_eingerichtet = True
    return projekt_logger


def get_logger(name: str) -> logging.Logger:
    """Liefert einen Modul-Logger als Kind des Projekt-Loggers.

    Der erste Aufruf richtet den Projekt-Logger mit RotatingFileHandler
    und stdout-Handler ein. Der zurueckgegebene Logger heisst
    ``telegram_summarizer.<name>`` und propagiert seine Eintraege an
    den Projekt-Logger, ueber dessen Handler die Datei- und stdout-
    Ausgabe stattfindet.
    """
    if not _ist_eingerichtet:
        richte_logging_ein()
    return logging.getLogger(f"{PROJEKT_LOGGER_NAME}.{name}")
