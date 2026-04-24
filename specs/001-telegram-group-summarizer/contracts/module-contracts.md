# Module Contracts

**Feature**: Telegram Group Summarizer
**Date**: 2026-04-24

This project exposes no HTTP API and no public library surface. The
"contract" between components is the set of public functions each
module offers to its in-process callers. This file captures those
signatures so that tasks and tests can be written against them.

All signatures are Python 3.11+.

---

## `config.py`

```python
@dataclass(frozen=True)
class Config:
    telegram_api_id: int
    telegram_api_hash: str
    telegram_phone: str
    telegram_group_name: str
    telegram_bot_token: str
    telegram_chat_id: int
    anthropic_api_key: str
    lookback_hours: int            # default 24; must be > 0
    log_level: str                 # "DEBUG" or "INFO"; default "INFO"
    anthropic_model: str           # default "claude-sonnet-4-6"
    session_path: pathlib.Path     # derived; default ./telegram.session


def load_config() -> Config:
    """
    Loads .env via python-dotenv, validates all required variables, and
    returns a frozen Config.

    Raises:
        SystemExit(non-zero) with a single logged error message that
        names the offending variable if any required value is missing,
        or if lookback_hours <= 0, or if LOG_LEVEL is invalid.
        (FR-004)
    """
```

---

## `logger.py`

```python
def get_logger(name: str) -> logging.Logger:
    """
    Returns a module-scoped logger that writes to BOTH stdout and
    logs/YYYY-MM-DD.log with format:
        [%(asctime)s] [%(levelname)s] [%(name)s] %(message)s
    (datefmt=%Y-%m-%dT%H:%M:%S, ISO-8601 compatible)

    The root configuration is applied exactly once on the first call;
    subsequent calls just fetch the named logger.

    The effective level is taken from Config.log_level on first call.
    """
```

---

## `telegram_reader.py`

```python
@dataclass(frozen=True)
class Message:
    message_id: int
    sender: str
    timestamp: datetime        # UTC, tz-aware
    text: str                  # empty for media without caption
    reply_to_id: int | None    # only set if the parent is in the collected window


def get_messages(config: Config) -> dict[str, list[Message]]:
    """
    Connects to Telegram via Telethon using config.session_path.
    Detects forum-topic vs regular group automatically (FR-008).
    For each topic-chat (or the single chat, non-forum case), returns
    only messages whose timestamp is newer than now - lookback_hours.

    Returns an empty list for a topic-chat that had no new activity.

    Relies on Telethon's built-in FloodWait handling; no custom retry.
    Raises the underlying Telethon exception on unrecoverable failure
    so main.py can handle it via the graceful-failure path.
    """


def serialize_messages(messages: list[Message]) -> str:
    """
    Produces the string value that fills the {{messages}} placeholder.

    One line per message, chronological order, format:
        [<ISO-8601 timestamp>] <Sender>: <text>
    or when reply_to_id is not None:
        [<ISO-8601 timestamp>] <Sender> [reply to: <parent_id>]: <text>

    Deterministic, reversible-within-limits (we do not attempt to
    escape newlines inside <text> — the prompt instructs Claude to
    treat each chronological line as a message boundary).
    """
```

---

## `summarizer.py`

```python
def load_prompt(filename: str) -> str:
    """
    Reads a file from the prompts/ folder. Returns the file content
    as a string.

    Raises:
        FileNotFoundError with the concrete path if the file is missing.
    """


def fill_prompt(template: str, **kwargs: str) -> str:
    """
    Replaces {{placeholder}} tokens in `template` with the string
    values from kwargs. Supported placeholders: {{chat_name}},
    {{messages}}, {{summaries}}.

    For every {{token}} that remains in the template after
    substitution (no kwarg supplied for it), emits logger.warning()
    naming the unresolved token. Does NOT raise on unresolved tokens —
    the literal {{token}} is left in place so the failure is visible
    in Claude's output and in the warning log.
    """


def summarize_chat(chat_name: str,
                   messages: list[Message],
                   config: Config) -> str:
    """
    Serializes messages, fills prompts/chat_summary.md, calls Claude
    via the anthropic SDK using config.anthropic_model in a single
    request (no chunking, no truncation). Returns the Russian-language
    summary text.

    Relies on the Anthropic SDK's built-in retry behavior for 429/5xx.
    Raises anthropic.* on unrecoverable failure (including
    context_length_exceeded) so main.py can classify it as a
    per-chat failure (FR-026a, FR-026b).

    Logs: chat_name, input message count, response character length.
    """


def summarize_overall(chat_summaries: list[tuple[str, str]],
                      config: Config) -> str:
    """
    `chat_summaries` is a list of (chat_name, summary_text) pairs.

    Loads prompts/overall_summary.md, fills {{summaries}}, calls
    Claude. Returns the Russian-language overall summary text.

    Raises on unrecoverable failure — handled by main.py.
    Logs: input summary count, response character length.
    """
```

---

## `bot_sender.py`

```python
def send_message(text: str, config: Config) -> None:
    """
    POSTs `text` to
        https://api.telegram.org/bot<config.telegram_bot_token>/sendMessage
    with chat_id=config.telegram_chat_id.

    Precondition: len(text) <= 4096. Callers must go through
    send_long_message() for anything else.

    Logs: character count and HTTP response status.
    Raises requests.HTTPError on non-2xx responses.
    """


def send_long_message(text: str, config: Config) -> None:
    """
    If len(text) <= 4096, delegates to send_message() once.

    Otherwise splits `text` on "\n\n" paragraph boundaries, greedily
    packing chunks up to 4096 characters. Paragraphs longer than 4096
    are hard-split at the character boundary. The concatenation of the
    delivered chunks equals `text` verbatim — no prefixes, suffixes,
    or "Part X/Y" markers (FR-018, SC-006).

    Calls send_message() for each chunk sequentially.
    Logs each chunk's character count and HTTP status.
    """
```

---

## `main.py`

```python
def main() -> int:
    """
    Orchestration entry point. Sequence:

    1. config = load_config()         # may sys.exit on bad config
    2. logger = get_logger("main")
    3. Log run start + non-secret config summary.
    4. chat_messages = telegram_reader.get_messages(config)
    5. For each (chat_name, messages) in chat_messages.items():
         try:
             if messages: summary = summarize_chat(chat_name, messages, config)
             accumulate successful summaries
         except Exception as exc:
             logger.exception(...); accumulate ChatFailure(chat_name, reason)
    6. If total collected messages == 0 across all chats:
         send_long_message(RUSSIAN_NO_ACTIVITY_MESSAGE, config)
         skip overall summary (FR-021a)
    7. Else:
         For each summary: send_long_message(summary_text, config)
         try:
             overall = summarize_overall([...], config)
             send_long_message(overall, config)
         except Exception as exc:
             logger.exception(...); append to failures
       Then, if failures: send_long_message(labeled_error_section, config)
    8. Log end-of-run summary: processed, failed, sent, duration.

    Returns exit code: 0 on nominal run, non-zero only on unrecoverable
    whole-run failures (FR-027) like missing config or total Telegram
    auth failure before any per-chat iteration was possible.
    """
```

---

## CLI surface

Single command:

```
python main.py
```

No positional arguments, no flags. All tunables come from `.env`.
Non-zero exit codes are reserved for unrecoverable whole-run
failures (FR-027).
