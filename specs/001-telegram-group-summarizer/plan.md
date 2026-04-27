# Implementation Plan: Telegram Group Summarizer

**Branch**: `001-telegram-group-summarizer` | **Date**: 2026-04-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-telegram-group-summarizer/spec.md`

## Summary

A Windows-native CLI tool that reads messages from a private paid Telegram group
via MTProto (Telethon), groups them per topic-chat within a `LOOKBACK_HOURS`
window, asks Claude to produce a Russian-language summary per chat plus an
overall summary, and delivers the result via a private bot (Telegram Bot API
over `requests`) to the operator's personal chat. The tool is a single-script
pipeline (`main.py`) composed of small, focused modules: config loader,
logger, Telegram reader, summarizer (with prompt loader), and bot sender.
Prompts live as Markdown files under `prompts/` so the operator can tune
tone/depth without touching code. All transient failures are surfaced via the
graceful-failure path — per-chat errors are reported in a labeled error
section of the delivered output and in the dated log file.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Telethon (MTProto read), anthropic SDK (Claude),
requests (Telegram Bot API delivery), python-dotenv (config)
**Storage**: local Telethon session file (`*.session`, gitignored);
per-run log file under `logs/YYYY-MM-DD.log`
**Testing**: pytest for module-level unit coverage of pure helpers
(serializer, prompt filler, long-message splitter). External I/O paths
(Telegram, Claude, Bot API) are validated via the quickstart smoke run,
not mocked.
**Target Platform**: Windows 10 / 11 with CPython installed, scheduleable
through Windows Task Scheduler. No WSL, no Docker.
**Project Type**: Single-script CLI / desktop automation tool.
**Performance Goals**: A normal daily run (group reachable, Claude
reachable, bot reachable) completes end-to-end within 10 minutes (SC-001).
**Constraints**: No message chunking for context-size fit (FR-026a) — the
full window goes in one Claude call. No custom retry loop on top of the
SDKs (FR-026b). No secret values in code or logs. No silent exception
swallowing (FR-025). Windows-native file handling via `pathlib.Path`.
**Scale/Scope**: Single operator, one target group, at most a few dozen
topic-chats per run. One run per day by default.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against the 7 principles in
[.specify/memory/constitution.md](../../.specify/memory/constitution.md)
(version 1.0.0):

| # | Principle | Status | How the plan satisfies it |
|---|-----------|--------|---------------------------|
| I | Security First (NON-NEGOTIABLE) | PASS | All secrets come from `.env` via `python-dotenv`. `.gitignore` covers `.env`, `*.session`, `logs/`, `__pycache__/`. `.env.example` with empty placeholders is committed. No secret is ever logged (config summary in main.py logs variable names only, never values). |
| II | Simplicity (Single-Script Architecture) | PASS | One entry point `main.py`; helper modules are small and single-purpose (`config.py`, `logger.py`, `telegram_reader.py`, `summarizer.py`, `bot_sender.py`). Dependencies limited to Telethon, anthropic, requests, python-dotenv. No web framework, queue, ORM, DB. |
| III | Externalized Prompt Configuration | PASS | Prompts live under `prompts/chat_summary.md` and `prompts/overall_summary.md`. Python code only loads them by path (`load_prompt`) and raises a clear, named error if a file is missing. |
| IV | Observability (NON-NEGOTIABLE) | PASS | `logger.py` writes to stdout and `logs/YYYY-MM-DD.log` with format `[ISO-8601] [LEVEL] [module] message`. Every phase (read, summarize, deliver) logs counts and outcomes. No bare `except`; every handled exception is logged with full context. End-of-run summary line records processed / failed / sent / duration. |
| V | Language Separation | PASS | All code, comments, logs, commits, and spec artifacts are in English. Prompt files explicitly instruct Claude to answer in Russian. The "no new activity" heartbeat message is Russian. |
| VI | Windows-Native Portability | PASS | `pathlib.Path` everywhere; ISO-8601 timestamps in filenames are Windows-safe (hyphens, no colons); documented Task Scheduler setup in README; no POSIX-only shell invocation. |
| VII | Graceful Per-Chat Failure | PASS | `main.py` wraps each chat's read+summarize cycle in try/except, accumulates a failures list, and appends a labeled error section to the delivered output. A single failing chat never aborts the run. |

**Post-Phase-1 re-evaluation**: after producing research.md, data-model.md,
contracts/module-contracts.md, and quickstart.md, the design still satisfies
all 7 principles. No new violations were introduced. Complexity Tracking
remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-telegram-group-summarizer/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── module-contracts.md  # Public functions exposed between modules
├── checklists/          # Pre-existing per-spec checklists
├── spec.md              # Feature specification
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
telegram-summary/
├── main.py                    # Entry point: orchestrates read -> summarize -> deliver
├── config.py                  # Loads .env, validates required vars, exposes Config object
├── logger.py                  # get_logger(name); stdout + logs/YYYY-MM-DD.log
├── telegram_reader.py         # Telethon MTProto read + Message dataclass + serializer
├── summarizer.py              # Prompt loader + Claude calls (per-chat + overall)
├── bot_sender.py              # Telegram Bot API delivery (requests); long-message split
├── prompts/
│   ├── chat_summary.md        # Per-chat prompt (Russian output instruction)
│   └── overall_summary.md     # Overall prompt (Russian output instruction)
├── logs/                      # Created at runtime, git-ignored
├── tests/                     # pytest suite for pure helpers
│   ├── test_serializer.py
│   ├── test_prompt_filler.py
│   └── test_long_message_split.py
├── .env.example               # All required + optional variables with English comments
├── .gitignore                 # .env, *.session, logs/, __pycache__/
├── requirements.txt           # Pinned: telethon, anthropic, requests, python-dotenv
└── README.md                  # Setup, first-run login, Task Scheduler instructions
```

**Structure Decision**: Single-project flat layout rooted at
`telegram-summary/`. One entry point (`main.py`) plus five focused helper
modules — matches Constitution Principle II (Simplicity) and the
Clean-Code separation the user's global guidance requires (one module,
one responsibility). No `src/` wrapper because there is no packaging
story; the tool is run as `python main.py` from the checkout. Tests live
under `tests/` and only cover pure helpers — the external I/O surface
is validated by the quickstart smoke run.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. Section intentionally left empty.
