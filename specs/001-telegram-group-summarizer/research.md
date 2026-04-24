# Phase 0 Research

**Feature**: Telegram Group Summarizer
**Date**: 2026-04-24

All five spec-level NEEDS CLARIFICATION items were resolved in the
`Clarifications` section of [spec.md](./spec.md) on 2026-04-24. This
document captures the remaining *technology* decisions that drive
Phase 1 design.

---

## Decision 1 — MTProto client for reading the private group

- **Decision**: Telethon `TelegramClient` with a local session file path
  supplied by config.
- **Rationale**:
  - Telegram's MTProto user API is the only way to read messages from a
    private paid group the operator is a member of (bots cannot). The
    constitution (section "Technical Constraints") names Telethon as the
    read path.
  - Telethon natively handles `FloodWaitError` with transparent waits,
    which removes the need for custom retry code (FR-026b).
  - Forum-topic detection is a first-class concept in Telethon
    (`iter_messages(..., reply_to=<topic_id>)` and the forum flag on
    channels/supergroups), so FR-008 can be implemented without any
    manual protocol work.
  - Persistent session files make FR-006 / FR-007 (one-time interactive
    login, silent subsequent runs) trivial.
- **Alternatives considered**:
  - **Pyrogram** — feature-equivalent but has a smaller surface in the
    Windows-first ecosystem and the constitution already committed to
    Telethon.
  - **Raw MTProto over asyncio** — violates Simplicity; rejected.

## Decision 2 — Claude API client

- **Decision**: Official `anthropic` Python SDK, model id from
  `ANTHROPIC_MODEL` env var with default `claude-sonnet-4-6`.
- **Rationale**:
  - The SDK ships built-in retry with exponential backoff for 429/5xx
    responses — which is exactly the behavior FR-026b mandates (no
    custom retry loop on top).
  - The model choice was explicitly clarified in spec session 2026-04-24.
  - Prompt cache can be used later without plan changes; initial
    implementation sends a single fresh call per chat.
- **Alternatives considered**:
  - **HTTP via `requests`** — would force re-implementing retry,
    streaming, and error-class mapping. Rejected for duplicating SDK
    work and violating Simplicity.

## Decision 3 — Bot delivery path

- **Decision**: Plain HTTP POST to `https://api.telegram.org/bot<TOKEN>/sendMessage`
  via `requests`, in the `bot_sender.py` module. No bot SDK.
- **Rationale**:
  - The delivery surface is a single endpoint. The constitution allows
    "python-telegram-bot or equivalent"; a direct call via `requests`
    is the most minimal equivalent and matches the user's attached
    implementation plan ("requests library, no additional SDK").
  - Keeps the dependency surface smaller (no async runtime, no bot
    dispatcher framework).
- **Alternatives considered**:
  - **python-telegram-bot** — pulls in a full async Application /
    dispatcher stack that we never use (we only send outbound, never
    receive updates). Rejected for over-fit.

## Decision 4 — Config loading

- **Decision**: `python-dotenv` to read `.env` at import time of
  `config.py`; a frozen `@dataclass` exposes the validated values.
- **Rationale**:
  - `.env` is the lowest-ceremony secret store that still keeps values
    out of git (FR-001, constitution Principle I).
  - A dataclass gives us type safety and IDE completion without adding
    a validation library like pydantic.
  - Fail-fast validation (FR-004) fits naturally in `Config.load()`.
- **Alternatives considered**:
  - **pydantic-settings** — richer validation but adds a heavyweight
    dependency just to produce a single config object.
  - **Reading `os.environ` directly in each module** — scatters
    configuration policy and makes fail-fast validation harder.

## Decision 5 — Logging strategy

- **Decision**: Stdlib `logging` with two handlers (stdout +
  `logs/YYYY-MM-DD.log`), shared formatter
  `[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s` with
  `datefmt='%Y-%m-%dT%H:%M:%S'` for ISO-8601 compatibility. `get_logger(name)`
  is configured once on first call (idempotent).
- **Rationale**:
  - Standard library only, no extra dep. Works identically on Windows.
  - Dual-handler satisfies FR-022 (console + dated file).
  - ISO-8601 datefmt satisfies FR-023.
  - Filename uses hyphens, not colons — safe on NTFS.
- **Alternatives considered**:
  - **loguru** — nicer API but an extra dep for no additional capability
    we need.

## Decision 6 — Long-message splitting strategy

- **Decision**: Split on `"\n\n"` paragraph boundaries while each
  accumulated chunk stays ≤ 4096 characters; if a single paragraph
  already exceeds 4096 chars, fall back to a hard character-window
  split of that paragraph. Concatenation of all chunks equals the input
  verbatim (no inserted "Part 1/3" markers, no trimmed whitespace).
- **Rationale**:
  - FR-018 / SC-006 require verbatim concatenation equality. Adding any
    prefix or footer to chunks would break that contract.
  - Paragraph-boundary splitting preserves readability in the bot chat;
    the hard fallback guarantees termination for pathological inputs.
- **Alternatives considered**:
  - **Split at 4096-char boundary blindly** — can break mid-word and
    mid-emoji. Rejected on readability grounds.
  - **Split on single newlines** — too granular, produces visually
    choppy chunks.

## Decision 7 — Testing scope

- **Decision**: `pytest` suite covers only pure helpers:
  - `serialize_messages()` output format (ordering, reply-to indicator)
  - `fill_prompt()` placeholder substitution + unknown-placeholder
    warning
  - `send_long_message()` chunker: concatenation equals input;
    each chunk ≤ 4096; paragraph boundaries preferred.
  External I/O (Telegram MTProto, Claude API, Bot API) is validated by
  running the quickstart smoke run against a real but disposable
  configuration. No mocks are introduced for those surfaces.
- **Rationale**:
  - Mirrors the user's global guidance against over-testing and against
    mocking external services.
  - Pure helpers deliver the correctness guarantees called out in
    spec success criteria (SC-006 specifically).
- **Alternatives considered**:
  - **Full integration test harness with recorded MTProto sessions** —
    overkill for a single-operator tool; violates Simplicity.

---

## Resolved Unknowns

| Unknown in Technical Context | Resolution |
|------------------------------|------------|
| Language/Version | Python 3.11+ (constitution Technical Constraints) |
| Primary Dependencies | Telethon, anthropic, requests, python-dotenv (Decisions 1–4) |
| Storage | Telethon `.session` file + dated log files only (no DB) |
| Testing | pytest for pure helpers only (Decision 7) |
| Target Platform | Windows 10/11 (constitution Principle VI) |
| Project Type | Single-script CLI (constitution Principle II) |
| Performance Goals | <10 min per normal run (SC-001) |
| Constraints | No chunking, no custom retry, no silent exceptions |
| Scale/Scope | Single operator, one target group, daily cadence |

No `NEEDS CLARIFICATION` items remain.
