# Feature Specification: Telegram Group Summarizer

**Feature Branch**: `001-telegram-group-summarizer`
**Created**: 2026-04-24
**Status**: Draft
**Input**: User description: "Telegram Group Summarizer tool: read messages from a private paid Telegram group via MTProto, summarize each topic-chat daily using Claude, deliver the Russian-language summary via a private Telegram bot to the operator's personal chat."

## Clarifications

### Session 2026-04-24

- Q: What format is each message supplied in when packed into the `{{messages}}` placeholder sent to Claude? → A: Sender name + ISO timestamp + message text, plus a reply-to indicator when the message replies to another (Option B).
- Q: Which Claude model is the documented default for summarization? → A: `claude-sonnet-4-6` as default, overridable via an environment variable (Option B).
- Q: How does the tool handle a topic-chat whose collected messages exceed Claude's context window? → A: Send everything in a single call; if the API rejects it for context-size reasons, treat the chat as a per-chat failure under the existing Graceful Failure path (Option A).
- Q: What is delivered on a day when the group had zero new messages in the lookback window? → A: Always deliver a short "no new activity" bot message in Russian so the operator has a daily heartbeat and can distinguish "quiet day" from "tool broke" (Option A).
- Q: What retry strategy covers transient external failures (Claude 429/5xx, Telegram FloodWait)? → A: Rely on the SDKs' built-in retry behavior (Anthropic SDK automatic retries for 429/5xx; Telethon's automatic FloodWait handling). No custom retry code. When the SDK retries are exhausted, the existing Graceful Failure path takes over (Option C).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive a daily Russian digest of the private group (Priority: P1)

The operator is a paying member of a private Russian-language Telegram group that
produces too much traffic to read in full every day. Once a day, without any
manual interaction, the operator wants to receive a compact, well-structured
Russian summary of the last 24 hours of activity — one summary per topic-chat
plus one overall summary — delivered as private chat messages from a dedicated
bot the operator controls.

**Why this priority**: This is the entire reason the tool exists. If this
journey works end-to-end for even a single topic-chat, the operator already
gets the core value (fewer hours of manual reading) and the tool qualifies as
a usable MVP.

**Independent Test**: Configure the required secrets, run the tool manually
once, and verify that the operator's personal chat with the bot receives at
least one Russian-language summary message covering messages from the target
group within the lookback window.

**Acceptance Scenarios**:

1. **Given** valid credentials and a target group that uses forum topics with
   new activity in the last 24 hours, **When** the operator triggers a run,
   **Then** the bot delivers one Russian summary message per topic-chat plus
   one overall Russian summary, in the operator's personal chat, in the
   expected order.
2. **Given** a target group that is a regular (non-forum) group with new
   activity in the last 24 hours, **When** the operator triggers a run,
   **Then** the bot delivers a Russian summary of that single chat and an
   overall Russian summary, in the operator's personal chat.
3. **Given** a topic-chat has no new messages within the lookback window,
   **When** the operator triggers a run, **Then** that topic-chat is skipped
   from summarization, its skipped status is reflected in the final output,
   and remaining topic-chats are still summarized.
4. **Given** a summary body exceeds the Telegram per-message length limit
   (4096 characters), **When** the tool delivers that summary, **Then** it is
   split into consecutive bot messages whose concatenation equals the full
   summary, with no content truncated or lost.

---

### User Story 2 - Keep the digest useful even when parts fail (Priority: P2)

The external services this tool depends on (Telegram, Claude API, the bot
delivery channel) can fail individually. The operator wants the daily digest
to degrade gracefully: if one topic-chat cannot be summarized, the remaining
topic-chats must still be summarized and delivered, and the failure must be
visible in the same daily message so it cannot be overlooked.

**Why this priority**: Without graceful failure, a single transient error
would cause the operator to miss the digest entirely and not notice the gap.
This priority makes the tool trustworthy for unattended daily use.

**Independent Test**: Simulate a failure for one topic-chat (e.g., by
pointing its prompt configuration at a non-existent file or by forcing a
Claude error for that chat) and verify the remaining topic-chats are still
summarized, delivered, and that the final bot output contains a clearly
labeled error section listing the failed chat and the reason.

**Acceptance Scenarios**:

1. **Given** N topic-chats where summarization of one chat fails for any
   reason, **When** the run completes, **Then** the operator receives N-1
   successful summaries plus a clearly labeled error section naming the
   failed chat and the reason.
2. **Given** a run in which any step produced an error, **When** the run
   completes, **Then** the run exits normally (no crash), the error is
   visible in both the log file and in the bot-delivered output, and no
   error is silently swallowed.
3. **Given** the target group cannot be reached at all (e.g., authentication
   has been revoked), **When** the operator triggers a run, **Then** the
   operator receives a clear failure notification via the bot (if the bot is
   still reachable) and the log file records the cause.

---

### User Story 3 - Tune summary style without changing code (Priority: P3)

The operator wants to experiment with the tone, length, and focus of the
summaries (shorter vs. more detailed, more analytical vs. more chronological,
different emphasis per topic-chat) without having to edit Python source files
and without risking breaking the tool.

**Why this priority**: This is a quality-of-life requirement that enables
ongoing tuning. The tool is usable without it, but tuning becomes painful
and risky if prompts live inside code.

**Independent Test**: Edit a prompt file in the prompts directory, trigger a
new run, and verify the delivered summary reflects the change (different
length, tone, or emphasis) without any Python file having been modified.

**Acceptance Scenarios**:

1. **Given** prompt files exist under the prompts directory, **When** the
   operator edits a prompt file and runs the tool, **Then** the summary
   reflects the updated prompt with no code change required.
2. **Given** a required prompt file is missing at runtime, **When** the tool
   attempts to use it, **Then** the tool reports a clear error naming the
   missing file (and either aborts that chat's summarization with graceful
   failure or aborts the whole run with a clear message, depending on
   whether it is a per-chat prompt or the overall prompt).

---

### User Story 4 - One-time login, silent daily runs thereafter (Priority: P3)

The operator sets the tool up once interactively (entering the Telegram code
delivered via SMS/app), after which every subsequent run — including runs
started by Windows Task Scheduler at fixed times with no human present — must
complete without asking for any input.

**Why this priority**: The entire value of an automated daily digest
evaporates if the tool requires manual input every run.

**Independent Test**: Run the tool once interactively, complete login, close
the process, then trigger the tool again via Windows Task Scheduler (or a
detached shell). Verify it completes without prompting.

**Acceptance Scenarios**:

1. **Given** no existing Telegram session, **When** the operator runs the
   tool for the first time, **Then** the tool prompts for the Telegram
   authentication code, accepts it, completes login, and persists the
   session for future runs.
2. **Given** a valid persisted Telegram session, **When** the tool runs
   (including via Task Scheduler), **Then** login is silent and no
   interactive input is required at any point of the run.
3. **Given** the persisted session has expired or been revoked, **When** the
   tool runs unattended, **Then** the tool does not hang waiting for input;
   it logs the authentication failure and reports it via the bot (if the bot
   is reachable).

---

### Edge Cases

- The target group is empty or the operator is no longer a member.
- Zero messages across all topic-chats within the lookback window (the tool
  must still produce a minimal "no new activity" output rather than silent
  absence).
- A topic-chat contains only non-text content (media without captions,
  stickers, service messages). Expected: the summary reflects that the chat
  had activity of that nature, rather than returning an empty or misleading
  summary.
- The target group switches between forum mode (topics) and non-forum mode
  between runs. Both modes must continue to work without manual
  reconfiguration.
- The Claude API returns an empty or malformed response for a chat. Treated
  as a per-chat failure (covered by User Story 2).
- Claude rate limits or returns a retryable error. Expected: the tool
  relies on the Anthropic SDK's built-in retry handling (automatic retries
  with backoff for 429/5xx responses). If the SDK's retries are exhausted,
  the chat is reported as a per-chat failure with a clear reason; the tool
  does not silently drop the chat.
- Telegram temporarily rate-limits the read client (e.g., `FloodWaitError`).
  Expected: the tool relies on Telethon's built-in flood-wait handling. If
  the enforced wait exceeds a reasonable run budget or surfaces as an
  exception, that chat (or the whole read step) is reported as a failure;
  the tool does not introduce its own retry loop on top of Telethon.
- The delivery bot is blocked by the operator, deleted, or its token has
  been revoked. Expected: the failure is recorded in the log file with full
  context, even if it cannot reach the operator.
- A message body from the source group contains characters that could be
  misinterpreted by Telegram's message formatting. The delivered summary
  must not crash on special characters or inadvertently change formatting.
- The configured lookback window is set to zero or a negative value.
  Expected: a clear configuration error at startup, not a silent empty run.
- Two consecutive runs happen within the lookback window (e.g., manual +
  scheduled). Expected: both runs complete successfully and independently;
  duplicate summaries are acceptable (the tool is not responsible for
  deduplicating digests).

## Requirements *(mandatory)*

### Functional Requirements

**Configuration**

- **FR-001**: The tool MUST load all configuration values (secrets and
  tunables) exclusively from a local `.env` file or process environment
  variables. No configuration value MAY be hardcoded in source files or in
  prompt files.
- **FR-002**: The tool MUST define the following required configuration
  variables and MUST validate at startup that each one is present and
  non-empty:
  - `TELEGRAM_API_ID` — MTProto app ID obtained from my.telegram.org
  - `TELEGRAM_API_HASH` — MTProto app hash obtained from my.telegram.org
  - `TELEGRAM_PHONE` — operator's phone number in international format
  - `TELEGRAM_GROUP_NAME` — exact display name of the target Telegram group
  - `TELEGRAM_BOT_TOKEN` — token of the operator's private delivery bot
  - `TELEGRAM_CHAT_ID` — operator's personal chat ID with the delivery bot
  - `ANTHROPIC_API_KEY` — Claude API key
- **FR-003**: The tool MUST accept the following optional configuration
  variables with documented defaults:
  - `LOOKBACK_HOURS` — integer, default 24
  - `LOG_LEVEL` — one of `DEBUG` or `INFO`, default `INFO`
  - `ANTHROPIC_MODEL` — Claude model identifier, default `claude-sonnet-4-6`.
    The same model MUST be used for per-chat and overall summaries unless
    the operator explicitly overrides it.
- **FR-004**: If any required configuration variable is missing or empty at
  startup, the tool MUST log a single clear error message that names the
  missing variable and MUST exit immediately with a non-zero status. It
  MUST NOT attempt any subsequent step.

**Telegram reading**

- **FR-005**: The tool MUST authenticate to Telegram as the operator using
  MTProto (not a bot account), because the target group is private and paid
  and cannot be read by bots.
- **FR-006**: On first run, the tool MUST run an interactive login flow
  (phone number plus the authentication code delivered by Telegram) and
  MUST persist the resulting session to a local session file so subsequent
  runs do not require interactive input.
- **FR-007**: On runs where a valid persisted session exists, the tool MUST
  reuse that session silently and MUST NOT prompt for any input.
- **FR-008**: The tool MUST detect at runtime whether the target group uses
  forum topics (producing multiple topic-chats) or is a regular group
  (producing a single chat) and MUST handle both cases.
- **FR-009**: For each topic-chat (or the single chat in the non-forum
  case), the tool MUST collect only messages whose timestamp is newer than
  `now - LOOKBACK_HOURS`.
- **FR-010**: The tool MUST log, at minimum: the group name, the number of
  topic-chats discovered, and the number of messages collected per chat.

**Summarization**

- **FR-011**: The tool MUST load the per-chat summarization prompt from
  `prompts/chat_summary.md` and the overall summarization prompt from
  `prompts/overall_summary.md`. No prompt text MAY be embedded in source
  code.
- **FR-012**: Prompt templates MUST support the placeholders `{{chat_name}}`,
  `{{messages}}`, and `{{summaries}}`. The tool MUST substitute these at
  runtime with the corresponding values. Unknown placeholders MUST NOT
  cause a silent failure.
- **FR-013**: For each topic-chat with at least one collected message, the
  tool MUST call the Claude API with the per-chat prompt (populated with
  chat name and collected messages) and obtain a summary.
- **FR-013a**: The `{{messages}}` placeholder MUST be filled with a
  deterministic, chronologically ordered serialization of the collected
  messages. Each message MUST carry: the sender's display name, an
  ISO-8601 timestamp, and the message text body; when a message is a reply
  to another message within the same collected window, the serialization
  MUST include a reply-to indicator identifying the parent message.
  Reactions, edit markers, and media metadata beyond caption text are out
  of scope for this feature.
- **FR-014**: After all per-chat summaries are produced, the tool MUST call
  the Claude API with the overall prompt (populated with the collected
  per-chat summaries) and obtain an overall summary.
- **FR-015**: Every summary produced by Claude MUST be in Russian. The
  prompt templates MUST instruct Claude to respond in Russian.
- **FR-016**: The tool MUST log, for each Claude call: the chat name (where
  applicable), the number of messages or summaries supplied as input, and
  the length of the returned response.

**Delivery**

- **FR-017**: The tool MUST deliver, to the operator's personal chat
  identified by `TELEGRAM_CHAT_ID`, one bot message per successful per-chat
  summary plus one bot message for the overall summary.
- **FR-018**: If any single delivery message body exceeds 4096 characters
  (Telegram's per-message limit), the tool MUST split it into multiple
  consecutive messages whose concatenation equals the original summary
  verbatim.
- **FR-019**: The tool MUST deliver messages sequentially in a predictable
  order (per-chat summaries first, in a stable order; overall summary
  last).
- **FR-020**: The tool MUST log each delivery attempt, including the target
  chat, the message size, and the outcome (success or error).
- **FR-021**: If any per-chat summarization failed during the run, the tool
  MUST include a clearly labeled error section in the delivered output
  listing each failed chat and the reason for its failure.
- **FR-021a**: If zero messages were collected across all topic-chats in
  the lookback window, the tool MUST still deliver exactly one bot message
  to the operator — a short Russian "no new activity" notice — so that
  every successful run produces a visible heartbeat. The overall-summary
  Claude call MAY be skipped in this case.

**Logging and observability**

- **FR-022**: The tool MUST log to both the console (stdout) and to a file
  under `logs/` whose name encodes the run date (e.g., `YYYY-MM-DD.log`).
- **FR-023**: Every log entry MUST include a timestamp, a log level, the
  module name, and the message. Timestamps MUST be unambiguous
  (ISO-8601-compatible).
- **FR-024**: At the end of every run, the tool MUST log a summary line
  reporting: number of topic-chats processed, number of topic-chats that
  failed, number of bot messages sent, and total run duration.
- **FR-025**: The tool MUST NOT swallow exceptions silently. Every handled
  exception MUST appear in the log file with sufficient context to
  reconstruct what happened.

**Graceful failure**

- **FR-026**: A failure in one topic-chat (Telegram read error, Claude
  error, prompt load error, delivery error) MUST NOT abort the processing
  of the remaining topic-chats.
- **FR-026a**: The tool MUST NOT chunk, truncate, or otherwise pre-process
  a chat's messages to fit the model context window. The entire collected
  message window MUST be sent to Claude in a single call; if that call
  fails because the input exceeds the model's context limit, the chat
  MUST be treated as a per-chat failure under FR-026 and reported under
  FR-021 with the specific reason.
- **FR-026b**: For transient errors from external services (e.g., Claude
  `429`/`5xx`, Telegram `FloodWaitError`), the tool MUST rely exclusively
  on the built-in retry behavior provided by the Anthropic SDK and by
  Telethon. The tool MUST NOT implement its own retry loop on top of
  those SDKs. When the SDK-level retries are exhausted, the resulting
  exception MUST be handled by the Graceful Failure path (FR-026) and
  surfaced in the delivered output (FR-021).
- **FR-027**: If the run cannot proceed at all (e.g., authentication failure,
  missing required config), the tool MUST still produce a log record that
  explains the cause and MUST exit with a non-zero status.

**Execution**

- **FR-028**: The tool MUST provide a single entry point invocable from a
  standard command line on Windows, usable both for manual runs and as the
  action of a Windows Task Scheduler task.
- **FR-029**: After the first-run interactive login, no subsequent run MAY
  require interactive input for any reason during normal operation.

**Project hygiene**

- **FR-030**: The `.gitignore` file MUST include, at minimum: `.env`,
  `*.session`, `logs/`, and `__pycache__/` so that secrets, session state,
  and local artifacts cannot be committed by accident.

### Key Entities

- **Configuration**: the set of required and optional environment-sourced
  values that parameterize a run. Owned by the operator; never committed.
- **Topic-chat**: a distinct conversation surface inside the target group —
  either one of multiple forum topics or the single conversation of a
  non-forum group. Identified by a stable name used in logs and summary
  headers.
- **Message window**: the ordered collection of messages from a single
  topic-chat whose timestamps fall within `[now - LOOKBACK_HOURS, now]`.
- **Prompt template**: a Markdown file under `prompts/` containing the
  instructions sent to Claude, including placeholders that the tool fills
  at runtime. Editable by the operator; version-controlled.
- **Per-chat summary**: the Russian-language text returned by Claude for a
  single topic-chat.
- **Overall summary**: the Russian-language text returned by Claude when
  given the collection of per-chat summaries as input.
- **Run log**: the timestamped record of a single execution, written both
  to stdout and to a dated file under `logs/`.
- **Run report**: the set of bot messages delivered to the operator for a
  single run — per-chat summaries, the overall summary, and any error
  section listing per-chat failures.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a normal day (target group reachable, Claude reachable,
  bot reachable), the operator receives the complete digest (all per-chat
  summaries + overall summary) within 10 minutes of the run being
  triggered.
- **SC-002**: When exactly one topic-chat out of N fails to be summarized,
  the operator still receives the other N-1 summaries plus a visible error
  section naming the failed chat and the reason — in 100% of such runs.
- **SC-003**: The operator can change the tone, length, or focus of
  summaries by editing a single file under the prompts directory and
  triggering a new run, without modifying any Python source file, in 100%
  of tuning attempts.
- **SC-004**: After the initial one-time login, the tool completes a
  scheduled run with zero human interaction on 30 consecutive days of
  routine scheduled execution.
- **SC-005**: For every run (successful or failed), a dated log file exists
  under `logs/` containing enough detail to identify, for each topic-chat,
  whether it was read, whether it was summarized, and whether it was
  delivered — reviewable by the operator without re-running the tool.
- **SC-006**: No run ever delivers a bot message that exceeds Telegram's
  per-message length limit; summaries that would exceed it are split and
  the concatenation equals the original summary verbatim in 100% of cases.
- **SC-007**: No secret value (credentials, tokens, phone number, session
  data) ever appears in a commit to version control. Verifiable by
  inspecting repository history and `.gitignore` coverage.
- **SC-008**: On a misconfigured run (a required variable missing), the
  tool exits in under 5 seconds with a log message that names the missing
  variable — no Telegram connection attempt, no Claude call, no bot
  delivery.

## Assumptions

- The operator is an active paying member of the target Telegram group and
  has been granted the necessary MTProto application credentials from
  my.telegram.org.
- The operator has created a private delivery bot via BotFather and has
  already exchanged at least one message with it, so the bot knows the
  operator's chat ID.
- The operator is the sole user of the tool; there is no multi-tenant
  deployment, no shared inbox, no admin UI.
- The target group's primary language is Russian; Russian is therefore the
  natural output language for summaries even when individual messages are
  in other languages.
- A daily summarization cadence (one run per calendar day) is sufficient;
  near-real-time summarization is out of scope.
- The tool is not responsible for deduplicating digests if the operator
  triggers multiple runs whose lookback windows overlap.
- The tool does not need to archive source messages beyond the lifetime of
  a single run; it is a pass-through summarizer, not a message archive.
- The delivery bot is trusted by the operator and is used only to deliver
  messages to the operator's personal chat; it is not added to any group.
- Per-chat prompt customization beyond a single shared `chat_summary.md`
  is out of scope for this feature; operators who later want distinct
  prompts per topic-chat will request that as a separate feature.
- Single-chat (non-forum) groups still run the overall-summary step; the
  operator may choose to shape the overall prompt to avoid redundancy in
  that case.
