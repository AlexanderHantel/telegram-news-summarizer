"""Pytest configuration for the Telegram Summarizer test suite.

Adds the repository root to ``sys.path`` so the flat-layout modules
(``telegram_reader``, ``summarizer``, ``bot_sender``, ...) can be imported
without a package installation step.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))
