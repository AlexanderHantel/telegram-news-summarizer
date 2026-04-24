# Phase 1 Data Model

**Feature**: Telegram Group Summarizer
**Date**: 2026-04-24

This tool is a pass-through pipeline with no persistent application
state beyond the Telethon session file and the dated log file. The
"data model" therefore describes in-memory entities that flow through
the pipeline, not database tables.

---

## Entity 1 — `Config`

Loaded once at startup by `config.py` from `.env`. Immutable.

| Field | Type | Required | Default | Source | Notes |
|-------|------|----------|---------|--------|-------|
| `telegram_api_id` | `int` | yes | — | `TELEGRAM_API_ID` | MTProto app id |
| `telegram_api_hash` | `str` | yes | — | `TELEGRAM_API_HASH` | MTProto app hash |
| `telegram_phone` | `str` | yes | — | `TELEGRAM_PHONE` | international format |
| `telegram_group_name` | `str` | yes | — | `TELEGRAM_GROUP_NAME` | exact display name |
| `telegram_bot_token` | `str` | yes | — | `TELEGRAM_BOT_TOKEN` | BotFather token |
| `telegram_chat_id` | `int` | yes | — | `TELEGRAM_CHAT_ID` | operator's DM id with the bot |
| `anthropic_api_key` | `str` | yes | — | `ANTHROPIC_API_KEY` | Claude key |
| `lookback_hours` | `int` | no | `24` | `LOOKBACK_HOURS` | must be `> 0` — else fatal config error (FR-004) |
| `log_level` | `str` | no | `"INFO"` | `LOG_LEVEL` | `DEBUG` or `INFO` |
| `anthropic_model` | `str` | no | `"claude-sonnet-4-6"` | `ANTHROPIC_MODEL` | same model for per-chat + overall (FR-003) |
| `session_path` | `pathlib.Path` | derived | `./telegram.session` | — | fixed; NOT read from `.env`; `Config.load()` always sets it to `pathlib.Path("telegram.session")` resolved against the current working directory. Rationale: per Constitution Technical Constraints the session file path is a deployment detail, not a tunable. Listed here only so downstream modules consume it uniformly via `config.session_path`. |

**Validation rules (fail-fast at startup, FR-004):**
- Every required field must be present and non-empty.
- `lookback_hours` must parse as `int` and be `> 0`.
- `log_level` must be `"DEBUG"` or `"INFO"` (case-insensitive normalized).
- `telegram_api_id` and `telegram_chat_id` must parse as `int`.

Any violation causes a single log error naming the offending variable
and a non-zero exit, before any Telegram / Claude / bot interaction.

---

## Entity 2 — `Message`

Represents one Telegram message collected within the lookback window.
Defined as a dataclass in `telegram_reader.py`.

| Field | Type | Notes |
|-------|------|-------|
| `message_id` | `int` | Telegram message id (needed so replies can point back by id) |
| `sender` | `str` | display name of the sender; empty string replaced with a neutral placeholder |
| `timestamp` | `datetime` | UTC, timezone-aware |
| `text` | `str` | message body; for media-with-caption, the caption; empty string for media without caption / service messages |
| `reply_to_id` | `int \| None` | parent message id if this is a reply to a message *within the collected window*; `None` otherwise |

**Validation rules:**
- `timestamp` must be within `[now - lookback_hours, now]`.
- `reply_to_id` is set to `None` if the parent is outside the collected
  window (prevents dangling reply pointers in the serialized prompt
  payload).

**State transitions:** none — messages are immutable snapshots.

---

## Entity 3 — `ChatMessages`

Not a formal class; the logical shape returned by
`telegram_reader.get_messages(config)`:

```python
dict[str, list[Message]]
```

- **Key**: topic-chat display name (FR-008 — forum topic name, or the
  group name itself if the group is non-forum).
- **Value**: chronologically ordered list of `Message` objects.

**Invariants:**
- Keys are stable run-to-run for a given forum topology, so delivery
  ordering (FR-019) is deterministic.
- Empty lists are preserved (the caller decides whether to skip the
  chat or treat the whole run as "no activity" per FR-021a).

---

## Entity 4 — `ChatSummary`

Produced by `summarizer.summarize_chat()`. In memory only.

| Field | Type | Notes |
|-------|------|-------|
| `chat_name` | `str` | topic-chat name |
| `summary_text` | `str` | Russian-language text returned by Claude |
| `input_message_count` | `int` | logged per FR-016 |

Implementation may use a plain dataclass or a simple tuple — the
downstream consumer (`main.py`) only needs `chat_name` and
`summary_text`.

---

## Entity 5 — `ChatFailure`

Accumulated by `main.py` whenever a per-chat cycle (read, summarize,
or prompt-load) raises. Drives the labeled error section in the
delivered output (FR-021).

| Field | Type | Notes |
|-------|------|-------|
| `chat_name` | `str` | which chat failed |
| `reason` | `str` | one-line human-readable cause (e.g. `"Claude: context_length_exceeded"`, `"Telethon: authentication revoked"`) |

Stored as a list (`list[ChatFailure]`), preserving the order in which
failures occurred.

---

## Entity 6 — `RunReport`

The aggregate artifact assembled at the end of a run. Not a class;
delivered as a sequence of bot messages.

Order (FR-019):
1. One bot message per successful `ChatSummary` (stable chat order).
2. One bot message with the overall Russian summary (skipped only in the
   zero-activity case per FR-021a).
3. If `failures` is non-empty: one final bot message containing the
   labeled error section that lists each `ChatFailure`.

Parallel artifact: the dated log file under `logs/YYYY-MM-DD.log` (the
on-disk record).

**Zero-activity exception (FR-021a):** when every `ChatMessages` value
is empty, the delivered output is a single Russian "no new activity"
heartbeat message; no Claude calls happen.

---

## Entity 7 — `PromptTemplate`

Not a runtime class — it's a Markdown file under `prompts/`. Listed
here for completeness because it's a first-class project entity
(constitution Principle III).

| Property | Value |
|----------|-------|
| `path` | `prompts/chat_summary.md` or `prompts/overall_summary.md` |
| `content` | UTF-8 Markdown with `{{placeholder}}` tokens |
| Supported placeholders | `{{chat_name}}`, `{{messages}}`, `{{summaries}}` |

**Load-time rule (FR-011 / FR-012):**
- Missing file → `FileNotFoundError` with the concrete path; the
  caller converts this to a per-chat failure (for `chat_summary.md`) or
  a whole-run failure (for `overall_summary.md`).
- Unknown placeholder in the template → `logger.warning()` per unresolved
  token; the call continues with the literal `{{token}}` left in place
  (never silent).
