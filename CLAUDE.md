# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at [specs/001-telegram-group-summarizer/plan.md](specs/001-telegram-group-summarizer/plan.md).
<!-- SPECKIT END -->

## Constitution overrides global rules

This repo has a project constitution at [.specify/memory/constitution.md](.specify/memory/constitution.md) that takes precedence over the user's global rules where they conflict:

- **Principle V (Language Separation)** — code, identifiers, comments, docstrings, log messages, commit messages, and spec artifacts are written in **English**. Only the summaries delivered to the operator are Russian, and that is enforced inside the prompt files under `prompts/`. Do **not** translate code or commit messages to German here, even though the global rule says so.
- **Principles I and IV are NON-NEGOTIABLE**: never log secret values; never write a bare `except:` or a silent `except` without a logger call.

## Commands

PowerShell, run from the repo root with the venv active (`.\.venv\Scripts\Activate.ps1`):

| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Run the tool end-to-end | `python main.py` |
| Run all tests | `pytest` |
| Run one test file | `pytest tests/test_long_message_split.py` |
| Run one test by node id | `pytest tests/test_serializer.py::test_function_name` |
| Lint | `ruff check .` |
| Type-check | `pyright` |

The test suite uses [tests/conftest.py](tests/conftest.py) to inject the repo root into `sys.path` (flat layout — no package install needed).

There is no build step. The project is shipped as plain `.py` files plus optional PyInstaller packaging (see README scheduler section); no `setup.py` / `pyproject.toml` is present.

## Architecture

Single-script CLI with one entry point and five focused helper modules. The orchestration sequence in [main.py](main.py) is:

1. [config.py](config.py) — `load_config()` reads `.env`, validates every required variable, and **fails fast with `sys.exit(1)`** before any network call. Returns a frozen `Config` dataclass. Optional vars: `LOOKBACK_HOURS` (default 24), `LOG_LEVEL` (DEBUG/INFO), `ANTHROPIC_MODEL` (default `claude-sonnet-4-6`), `EXCLUDED_TOPIC_IDS` (comma-separated forum topic ids; default empty).
2. [logger.py](logger.py) — `get_logger(name)` returns a child of the named project logger `telegram_summarizer`. First call sets up a `RotatingFileHandler` (2 MB × 10 backups, append-only, UTF-8) writing to `logs/telegram_summarizer.log` next to the script (Variante A from the global logging rule). Idempotent — handlers are cleared on each call to `richte_logging_ein` so tests can swap in `tmp_path`.
3. [telegram_reader.py](telegram_reader.py) — `get_messages(config)` opens a Telethon MTProto session, **calls `get_dialogs()` first to populate the entity cache** (otherwise `get_entity` cannot resolve a group by display name), detects forum-topic vs plain group, and returns `dict[chat_name, list[Message]]` ordered by ascending topic id. Topic ids in `config.excluded_topic_ids` are filtered out **before** any per-topic read (used to break feedback loops when the bot itself posts into one of the topics). Wraps everything in `asyncio.run` (Python 3.14 compatibility — see commit `e6fa7f5`). Telethon's built-in FloodWait handling is the only retry layer; **do not add a custom retry loop** (FR-026b).
4. [summarizer.py](summarizer.py) — `load_prompt(filename)` reads from `prompts/`, `fill_prompt(...)` substitutes `{{placeholder}}` tokens (and warns once per unresolved token, never silently drops them), `summarize_chat(...)` and `summarize_overall(...)` call the Anthropic SDK once with `max_tokens=4096`. **No chunking, no truncation** (FR-026a) — the full window goes in one Claude call.
5. [bot_sender.py](bot_sender.py) — `send_long_message(text, config)` POSTs to `api.telegram.org/bot.../sendMessage` via plain `requests` (no bot SDK). Splits messages > 4096 chars on `\n\n` boundaries; concatenated chunks equal the original payload **byte-for-byte** (FR-018, SC-006) — no inserted prefixes, suffixes, or chunk ordinals.

### Failure semantics (Principle VII)

`main.py` follows a strict graceful-failure contract:

- A failing per-chat read or summary is appended to a `failures` list and the run continues.
- Every successful chat summary is delivered, then a labeled error section (`Ошибки этого запуска:`) is delivered as a separate message if `failures` is non-empty.
- A bot delivery error sets a `delivery_failure_box` flag — the run still tries to deliver the remaining items, then exits with code 2.
- Telegram authentication revoked (`SessionRevokedError`, `AuthKeyUnregisteredError`, `UserDeactivatedError`, `UserDeactivatedBanError`) → exit 4 with a Russian notice.
- Missing `prompts/overall_summary.md` → exit 3 (per-chat summaries still delivered, overall aborted). Missing `prompts/chat_summary.md` is per-chat, not whole-run.
- Zero new messages in the window → deliver the Russian heartbeat (`_NO_ACTIVITY_HEARTBEAT_MESSAGE_RUSSIAN`) and exit 0.

When changing this orchestration, preserve the exit-code table in the README and the rule that **per-chat failures never abort the run**.

## Conventions enforced by the constitution

- Prompts live as Markdown under `prompts/`; never inline a prompt as a string literal in Python.
- Logging path is **Variante A** (`<programmverzeichnis>/logs/...`) — fixed by spec, do not switch to `%LOCALAPPDATA%`.
- Rotation parameters (2 MB / 10 backups) are hardcoded — documented exception to the "no hardcodes" rule, see [~/.claude/rules/logging-konfiguration.md](file:///C:/Users/Hantel/.claude/rules/logging-konfiguration.md).
- Windows-only target (Principle VI). Use `pathlib.Path`; do not introduce POSIX-only shell calls, WSL, or Docker.
- No new dependencies beyond `telethon`, `anthropic`, `requests`, `python-dotenv` without a constitution amendment.

## Spec Kit workflow

Feature-level changes go through `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`. The current feature is `001-telegram-group-summarizer` on branch of the same name. Prompt-only edits skip the spec cycle and ship as `chore(prompts): ...` or `docs: ...`.
