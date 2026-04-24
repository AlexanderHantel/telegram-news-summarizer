---
description: "Task list for Telegram Group Summarizer implementation"
---

# Tasks: Telegram Group Summarizer

**Input**: Design documents from `/specs/001-telegram-group-summarizer/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/module-contracts.md, quickstart.md

**Tests**: Tests are included (pytest for pure helpers only, per plan.md
Phase 0 Decision 7). External I/O paths (Telegram, Claude, Bot API) are
validated by the quickstart smoke run, not by mocks.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps task to a user story from spec.md (US1–US4)
- All file paths are relative to the repository root
  `c:\Hantel\Projekte\CLAUDE\telegram-news-summarizer\`

## Path Conventions

Single-project flat layout at the repository root: `main.py` and helper
modules (`config.py`, `logger.py`, `telegram_reader.py`, `summarizer.py`,
`bot_sender.py`), plus `prompts/`, `tests/`, and `logs/` (runtime).
No `src/` wrapper (see plan.md Structure Decision).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and repository hygiene

- [ ] T001 Create runtime folder layout: `prompts/`, `tests/`, `logs/` (all at repo root; `logs/` only needs to be creatable at runtime, not pre-populated)
- [ ] T002 [P] Create `requirements.txt` at repo root with pinned versions of `telethon`, `anthropic`, `requests`, `python-dotenv`
- [ ] T003 [P] Create `.gitignore` at repo root containing at minimum `.env`, `*.session`, `logs/`, `__pycache__/` (FR-030)
- [ ] T004 [P] Create `.env.example` at repo root listing every required and optional variable from data-model.md Entity 1 with English one-line comments and empty placeholder values

**Checkpoint**: Fresh clone + `pip install -r requirements.txt` succeeds; `.env.example` documents every configurable surface.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Logging and configuration are required by every other module (Constitution Principles I and IV).

**⚠️ CRITICAL**: No user story work may begin until this phase is complete — every downstream module calls `get_logger()` and consumes a `Config` object.

- [ ] T005 Implement `logger.py` at repo root exposing `get_logger(name: str) -> logging.Logger` with dual handlers (stdout + `logs/YYYY-MM-DD.log`), formatter `[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s`, `datefmt='%Y-%m-%dT%H:%M:%S'`, idempotent root configuration, level driven by `Config.log_level` (FR-022, FR-023, FR-025)
- [ ] T006 Implement `config.py` at repo root: frozen `@dataclass Config` per data-model.md Entity 1 plus `load_config() -> Config` that uses `python-dotenv`, validates all required fields, rejects `lookback_hours <= 0`, validates `LOG_LEVEL ∈ {DEBUG, INFO}`, and on failure logs a single error naming the offending variable then calls `sys.exit(1)` before any network call (FR-002, FR-003, FR-004, SC-008). `session_path` is NOT read from `.env` — `load_config()` sets it unconditionally to `pathlib.Path("telegram.session")` (fixed default; deployment detail, not a tunable)

**Checkpoint**: `python -c "from config import load_config; load_config()"` runs green with a valid `.env` and exits non-zero with a clear message when any required variable is blanked out.

---

## Phase 3: User Story 1 - Receive daily Russian digest (Priority: P1) 🎯 MVP

**Goal**: End-to-end happy path — read the target group's last `LOOKBACK_HOURS`, produce one Russian summary per topic-chat plus one overall Russian summary, deliver them to the operator's bot DM in stable order; on a fully-quiet day deliver exactly one Russian "no new activity" heartbeat.

**Independent Test**: Configure `.env`, run `python main.py` once, verify the operator's bot DM receives at least one Russian summary covering the target group within the lookback window (spec §User Story 1 Independent Test + Acceptance Scenarios 1–4 + FR-021a heartbeat).

### Implementation for User Story 1

- [ ] T007 [P] [US1] Define the `Message` dataclass in `telegram_reader.py` per data-model.md Entity 2 (fields: `message_id`, `sender`, `timestamp` UTC tz-aware, `text`, `reply_to_id | None`)
- [ ] T008 [P] [US1] Create `prompts/chat_summary.md` with `{{chat_name}}` and `{{messages}}` placeholders and an explicit instruction to Claude to respond exclusively in Russian (highlight key announcements, tool recommendations, technical solutions, interesting discussions); additionally instruct Claude that a message line with an empty text body represents media or service activity and must be acknowledged as such in the Russian summary instead of being ignored (FR-011, FR-015, spec §Edge Cases non-text-content chat)
- [ ] T009 [P] [US1] Create `prompts/overall_summary.md` with `{{summaries}}` placeholder and an explicit instruction to Claude to respond in Russian with 3–5 key takeaways for the day (FR-011, FR-014, FR-015)
- [ ] T010 [US1] Implement `serialize_messages(messages: list[Message]) -> str` in `telegram_reader.py` — chronological ISO-8601 lines; reply-to indicator prefix when `reply_to_id is not None` (FR-013a, contracts/module-contracts.md)
- [ ] T011 [US1] Implement `get_messages(config: Config) -> dict[str, list[Message]]` in `telegram_reader.py` using Telethon `TelegramClient` with `config.session_path`; auto-detect forum-topic vs regular group (FR-008); filter each chat by `timestamp > now - lookback_hours` (FR-009); log group name, topics discovered, and per-chat message count (FR-010); rely on Telethon's built-in FloodWait handling — no custom retry loop (FR-026b); set `reply_to_id` only when the parent message lies inside the collected window (data-model.md Entity 2 invariant); return the result dict with keys inserted in ascending Telegram topic ID order (non-forum group: single entry keyed by the group display name) so the iteration order in `main.py` directly produces the FR-019 delivery order
- [ ] T012 [P] [US1] Implement `load_prompt(filename: str) -> str` in `summarizer.py` — reads from `prompts/` and raises `FileNotFoundError` with the concrete path if the file is absent (FR-011, contracts/module-contracts.md)
- [ ] T013 [P] [US1] Implement `fill_prompt(template: str, **kwargs: str) -> str` in `summarizer.py` — replaces `{{placeholder}}` tokens; for each unresolved `{{token}}` remaining after substitution emit `logger.warning()` naming the token; do NOT raise (FR-012, contracts/module-contracts.md)
- [ ] T014 [US1] Implement `summarize_chat(chat_name, messages, config) -> str` in `summarizer.py` — calls `serialize_messages`, loads `chat_summary.md`, fills `{{chat_name}}` and `{{messages}}`, invokes Claude via the `anthropic` SDK with `config.anthropic_model` in a single request (no chunking, no truncation — FR-026a); log chat name, input message count, response length (FR-016); let the SDK handle 429/5xx retries (FR-026b)
- [ ] T015 [US1] Implement `summarize_overall(chat_summaries: list[tuple[str, str]], overall_template: str, config) -> str` in `summarizer.py` — the template is **passed in pre-loaded** (main.py loads `prompts/overall_summary.md` itself via `load_prompt`, see T022); fill `{{summaries}}` in `overall_template` and call Claude; log input summary count and response length. `summarize_overall` MUST NOT call `load_prompt` itself — this keeps `FileNotFoundError` for the overall prompt out of the T021 generic handler (FR-014, FR-016, contracts/module-contracts.md)
- [ ] T016 [P] [US1] Implement `send_message(text: str, config) -> None` in `bot_sender.py` — HTTP POST to `https://api.telegram.org/bot<TOKEN>/sendMessage` via `requests` with `chat_id=config.telegram_chat_id`; log character count and HTTP status; raise `requests.HTTPError` on non-2xx (FR-017, FR-020)
- [ ] T017 [US1] Implement `send_long_message(text: str, config) -> None` in `bot_sender.py` — if `len(text) <= 4096` delegate to `send_message` once; otherwise split on `"\n\n"` boundaries, greedily pack ≤4096-char chunks, hard-split single paragraphs that exceed 4096; concatenation of delivered chunks MUST equal `text` verbatim with no prefix/suffix markers (FR-018, SC-006)
- [ ] T018 [US1] Implement `main.py` happy-path orchestration at repo root: call `load_config()`, `get_logger("main")`, log non-secret config summary and run start; call `get_messages(config)`; for each `(chat_name, messages)` with non-empty messages call `summarize_chat` and accumulate results; deliver per-chat summaries in `get_messages` iteration order via `send_long_message` (FR-019 ascending topic-id order comes from T011); when at least one per-chat summary was produced, load `overall_template = load_prompt("overall_summary.md")` in `main.py` (not inside `summarize_overall`), then call `summarize_overall(chat_summaries, overall_template, config)` and deliver it last; when total messages across all chats is zero, skip both the overall prompt load and the Claude calls entirely and send exactly one Russian "no new activity" bot message (FR-021a); log run-end summary (processed/failed/sent/duration) (FR-024, FR-017, FR-019, spec §User Story 1 Acceptance Scenarios 1–4)

**Checkpoint**: Running `python main.py` against the real target group delivers the expected Russian digest to the operator's bot DM. Running against a quiet hour (`LOOKBACK_HOURS=1` during no activity) delivers exactly one Russian heartbeat message.

---

## Phase 4: User Story 2 - Keep the digest useful when parts fail (Priority: P2)

**Goal**: A failure in any single topic-chat (Telegram read, Claude, prompt, delivery) never aborts the run — the operator still receives the remaining summaries plus a clearly labeled error section naming each failed chat and its reason.

**Independent Test**: Force a per-chat failure (e.g., temporarily rename `prompts/chat_summary.md` during mid-run is not realistic — instead, point `ANTHROPIC_MODEL` to a non-existent model id to make every Claude call fail, and verify the delivered output contains a labeled error section listing every chat with its reason; or drop one chat's name into a test fixture that forces the Claude call to raise). Remaining successful summaries must still be delivered (spec §User Story 2 Independent Test).

### Implementation for User Story 2

- [ ] T019 [US2] Add a `failures: list[tuple[str, str]]` accumulator and per-chat `try/except` in `main.py` wrapping each chat's summarize cycle; on any exception call `logger.exception(...)` and append `(chat_name, reason)` to `failures`; continue to the next chat without re-raising (FR-026, FR-025, Principle VII)
- [ ] T020 [US2] After per-chat and overall delivery in `main.py`, when `failures` is non-empty build a Russian-language error section and deliver it as the final bot message via `send_long_message`. Header exactly: `"Ошибки этого запуска:"`. Each failure line exactly: `"- {chat_name}: {reason}"`. The `{reason}` may remain in its original English form (SDK/filesystem text) per FR-021. Example:<br>```<br>Ошибки этого запуска:<br>- Общий чат: anthropic.APIStatusError: overloaded_error<br>- overall: FileNotFoundError: prompts/overall_summary.md<br>```<br>(FR-021, spec §User Story 2 Acceptance Scenario 1)
- [ ] T021 [US2] Wrap **only** the `summarize_overall(...)` call itself in `main.py` with the same try/except pattern (not the preceding `load_prompt("overall_summary.md")` — that is handled separately by T022). On Claude-level failure append `("overall", reason)` to `failures` and still attempt failures-section delivery afterwards so a broken overall Claude call never silences per-chat summaries (FR-026 extended to the overall Claude step)
- [ ] T021a [US2] In `main.py`, wrap every `send_long_message` call site (per-chat summary, overall summary, failures section, no-activity heartbeat) in its own try/except. On `requests.HTTPError` or any delivery exception: `logger.exception(...)` with the target chat and the payload size, set a `delivery_failed = True` flag, and continue with the next delivery attempt. At the end of `main()`, if `delivery_failed` is `True`, return a non-zero exit code so Task Scheduler registers the run as failed (spec §Edge Cases bot blocked/revoked, FR-020)

**Checkpoint**: With any one chat's Claude call forced to fail, N−1 summaries plus a final labeled error section are delivered; the run exits with code 0 and the log file contains the full traceback for the failing chat (FR-025, SC-002).

---

## Phase 5: User Story 3 - Tune summary style without code changes (Priority: P3)

**Goal**: The operator edits a file under `prompts/` and a subsequent run reflects the edit, with no Python source change required. A missing prompt file is reported with a clear error that names the file.

**Independent Test**: Edit `prompts/chat_summary.md` (e.g., ask for a one-line summary instead of a structured one) and rerun — the delivered summary reflects the edit. Separately, temporarily rename `prompts/overall_summary.md` and rerun — the tool exits with a clear error naming the missing path, without delivering a broken summary (spec §User Story 3 Acceptance Scenarios 1 and 2).

### Implementation for User Story 3

- [ ] T022 [US3] In `main.py`, classify prompt-load failures correctly per spec §User Story 3 Acceptance Scenario 2:<br>• `FileNotFoundError` from the per-chat `load_prompt("chat_summary.md")` path (called inside `summarize_chat`) is converted to a `ChatFailure` via the Phase 4 try/except and the run continues normally for other chats.<br>• The **overall** prompt is loaded explicitly in `main.py` between the per-chat delivery loop and the `summarize_overall` call: `overall_template = load_prompt("overall_summary.md")`. This line is wrapped in its own `try/except FileNotFoundError` that is **separate from and NOT nested inside** the T021 generic try/except around `summarize_overall`. On `FileNotFoundError`: all already-collected per-chat summaries have already been delivered by T018; log the missing overall prompt with its absolute path via `logger.exception(...)`; skip the `summarize_overall` call entirely; skip adding anything to the failures section; proceed to end-of-run logging; return a non-zero exit code from `main()`. The operator sees the whole-run failure via the log file and the non-zero exit code — not via the per-chat labeled error section (which is reserved for per-chat graceful failures under FR-026). The flow therefore is:<br>```python<br># ... after per-chat summaries delivered ...<br>try:<br>    overall_template = load_prompt("overall_summary.md")<br>except FileNotFoundError:<br>    logger.exception("Missing overall prompt — whole-run abort")<br>    return NON_ZERO_EXIT<br>try:                                    # T021 handler<br>    overall = summarize_overall(chat_summaries, overall_template, config)<br>    send_long_message(overall, config)<br>except Exception as exc:<br>    logger.exception("Overall summary failed")<br>    failures.append(("overall", repr(exc)))<br>```

**Checkpoint**: Renaming `overall_summary.md` for one run yields per-chat summaries and a non-zero exit code; the dated log file names the missing path with its absolute location. No overall summary and no labeled error section are delivered in this specific case. Editing `chat_summary.md` content changes subsequent summaries with no code change (SC-003).

---

## Phase 6: User Story 4 - One-time login, silent daily runs (Priority: P3)

**Goal**: The first run logs in interactively and persists the session; every subsequent run (including Task Scheduler triggers) completes without any interactive prompt.

**Independent Test**: Run `python main.py` once interactively, enter the SMS/app code, verify a `.session` file appears. Close the shell. Re-run via Task Scheduler (or a detached shell) and confirm no prompt is ever issued (spec §User Story 4 Independent Test).

### Implementation for User Story 4

- [ ] T023 [US4] Confirm `telegram_reader.get_messages` constructs `TelegramClient(config.session_path, config.telegram_api_id, config.telegram_api_hash)` and calls `client.start(phone=config.telegram_phone)` exactly once — Telethon handles the interactive prompt on first run and reuses the session silently thereafter (FR-006, FR-007, FR-029); add a log line at the start of `get_messages` reporting whether `config.session_path` already exists so the run transcript shows silent-reuse vs first-run login
- [ ] T024 [US4] In `main.py`, wrap the top-level `get_messages(config)` call in its own `try/except` that catches Telethon authentication-revoked errors (e.g., `SessionRevokedError`, `AuthKeyUnregisteredError`): log the exception with full context, attempt to deliver a short Russian failure notice via `send_long_message` when the bot is reachable, then `sys.exit(non-zero)` — the tool must never hang waiting for input (spec §User Story 4 Acceptance Scenario 3, FR-027)
- [ ] T025 [US4] Create `README.md` at repo root with a Windows Task Scheduler section: Python executable path, absolute path to `main.py`, the critical "Start in" working-directory setting, recommended daily trigger time, where to find the dated log file, and the one-time interactive login flow that must happen before the scheduler takes over (mirrors quickstart.md §8 but lives in the repo root for operator discoverability; spec §User Story 4 + SC-004)

**Checkpoint**: After the first interactive login, the next 30 scheduled runs complete with zero human interaction (SC-004). A run executed after session revocation exits with a non-zero code, logs the cause, and attempts a bot-delivered failure notice.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Coverage of pure helpers and a final end-to-end smoke validation.

- [ ] T026 [P] Write `tests/test_serializer.py` covering `serialize_messages`: chronological ordering, ISO-8601 timestamp format, reply-to prefix when `reply_to_id is not None`, absence of the prefix when `None`, and empty-list handling
- [ ] T027 [P] Write `tests/test_prompt_filler.py` covering `fill_prompt`: successful substitution of `{{chat_name}}`, `{{messages}}`, `{{summaries}}`; an unresolved `{{token}}` emits exactly one warning and leaves the literal `{{token}}` in the output (no raise)
- [ ] T028 [P] Write `tests/test_long_message_split.py` covering `send_long_message` chunker: chunks ≤ 4096 characters each; concatenation of chunks equals input verbatim (no prefixes, no inserted markers); paragraph boundaries preferred over hard splits; pathological single-paragraph input longer than 4096 still terminates with a hard split (FR-018, SC-006)
- [ ] T029 [P] Expand the existing `README.md` (created in T025) with repository intro, `.env` setup walkthrough, and troubleshooting (missing prompt, revoked session, Claude context-length rejection). Preserve the Task Scheduler section from T025 verbatim — only append new sections before or after it. No other Polish task touches `README.md`, so the `[P]` marker is safe
- [ ] T030 Run the quickstart.md end-to-end smoke validation against a live Telegram group, Claude API, and bot DM; verify every checkbox under quickstart.md §5, §6, and §7 passes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Requires Phase 1; BLOCKS every user story because every downstream module consumes `get_logger` and `Config`.
- **User Story 1 (Phase 3)**: Depends on Phase 2. MVP and must be completed before the tool is usable.
- **User Story 2 (Phase 4)**: Depends on Phase 2 and on the existence of `main.py` orchestration from T018 (extends it with error handling).
- **User Story 3 (Phase 5)**: Depends on Phase 2, T012 (`load_prompt`), and T019 (per-chat try/except from US2). Note: US3's architectural core (externalized prompts) is delivered by US1 — this phase only adds the failure-classification wiring.
- **User Story 4 (Phase 6)**: Depends on Phase 2 and T011 (`get_messages`). Independent of US2/US3.
- **Polish (Phase 7)**: Tests (T026–T028) require their respective helpers from US1. T030 requires all prior phases.

### User Story Dependencies

- **US1 (P1, MVP)**: Standalone; depends only on Phase 2.
- **US2 (P2)**: Extends US1's `main.py` (T018) with graceful-failure wrapping. Cannot deliver value without US1.
- **US3 (P3)**: Depends on US1 (prompt externalization + `load_prompt`) and on US2 (per-chat failure path). Tiny delta — one task.
- **US4 (P3)**: Depends on US1's `get_messages`. Independent of US2 and US3.

### Within Each User Story

- Models and prompt files ([P] inside the same story phase) can be built in parallel.
- Pure helpers precede the orchestration task that consumes them (`serialize_messages` → `summarize_chat`; `load_prompt`/`fill_prompt` → `summarize_chat`/`summarize_overall`; `send_message` → `send_long_message`; everything → `main.py` T018).
- Inside US2: T019 must land before T020/T021 (the accumulator they write into).
- Inside US4: T023 must land before T024 (T024 handles the authentication failure that T023 surfaces).

### Parallel Opportunities

- **Phase 1**: T002, T003, T004 all run in parallel (distinct files at repo root).
- **Phase 3 (US1)**: T007 (Message dataclass), T008/T009 (prompt files), T012/T013 (pure helpers in summarizer.py), T016 (`send_message`) are all [P] — distinct files/functions with no inter-dependencies.
- **Phase 7 (Polish)**: T026/T027/T028/T029 all run in parallel.
- Across stories: once T018 ships, US2 and US4 can progress in parallel by different developers without collision.

---

## Parallel Example: User Story 1

```bash
# Launch the independent US1 scaffolding in parallel:
Task: "T007 [P] [US1] Define Message dataclass in telegram_reader.py"
Task: "T008 [P] [US1] Create prompts/chat_summary.md"
Task: "T009 [P] [US1] Create prompts/overall_summary.md"
Task: "T012 [P] [US1] Implement load_prompt in summarizer.py"
Task: "T013 [P] [US1] Implement fill_prompt in summarizer.py"
Task: "T016 [P] [US1] Implement send_message in bot_sender.py"

# Once the above are done, sequential tasks chain:
# T010 -> T011 -> T014 -> T015 -> T017 -> T018
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (US1).
3. **STOP and VALIDATE**: run quickstart.md §5 (happy path) and §6 (zero-activity heartbeat).
4. If both pass, the tool is already delivering daily value — stop here and ship.

### Incremental Delivery

1. Phase 1 + Phase 2 → foundation ready (no user-visible value yet).
2. Phase 3 (US1) → MVP; operator receives the daily Russian digest.
3. Phase 4 (US2) → the digest survives per-chat failures (trustworthy for unattended daily use).
4. Phase 5 (US3) → prompt edits flow through without code changes; missing-prompt errors are clear.
5. Phase 6 (US4) → first-run login is persisted; Task Scheduler takes over silently.
6. Phase 7 → pytest suite for pure helpers and full quickstart smoke validation.

### Single-Operator Strategy

This tool has one operator and one maintainer. There is no parallel team
workflow. The [P] markers indicate *which independent tasks can be
dispatched as concurrent agent work* if the implementer chooses to
parallelize agent calls; they are not a staffing plan.

---

## Notes

- [P] tasks touch different files and have no open dependencies at their launch point.
- [Story] label maps each task to a user story from spec.md for traceability.
- Every user story phase ends with a checkpoint that matches its Independent Test in spec.md.
- No secret value may appear in any file written by any task (Constitution Principle I, FR-001, SC-007).
- Commit after each task or logical group using Conventional Commits (e.g., `feat(summarizer): implement summarize_chat`).
- Avoid: cross-story dependencies that would break independent testability; modifying `main.py` outside the story phase that owns that delta; reintroducing retry loops on top of Telethon or the anthropic SDK (FR-026b).
