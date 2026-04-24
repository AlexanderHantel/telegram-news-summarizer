<!--
Sync Impact Report
==================
Version change: (uninitialized template) -> 1.0.0
Rationale: Initial ratification of the project constitution. MAJOR bump from template
placeholders (0.0.0) to first published version (1.0.0) because all governance and
principle content is newly defined.

Principles defined (7 total, expanded from the 5-slot template per user input):
  I.   Security First (NON-NEGOTIABLE)
  II.  Simplicity (Single-Script Architecture)
  III. Externalized Prompt Configuration
  IV.  Observability (NON-NEGOTIABLE)
  V.   Language Separation
  VI.  Windows-Native Portability
  VII. Graceful Per-Chat Failure

Added sections:
  - Technical Constraints (replaces SECTION_2)
  - Development Workflow (replaces SECTION_3)
  - Governance

Removed sections: none

Templates requiring updates:
  - .specify/templates/plan-template.md (✅ compatible; Constitution Check gate
    should reference the 7 principles defined here — no structural change required)
  - .specify/templates/spec-template.md (✅ compatible; no mandatory section changes)
  - .specify/templates/tasks-template.md (✅ compatible; observability and
    error-handling tasks already represented as cross-cutting categories)
  - README.md (⚠ pending; currently only contains project title, should reference
    this constitution once feature work begins)

Follow-up TODOs:
  - None. All placeholders were filled with concrete values.
-->

# Telegram News Summarizer Constitution

## Core Principles

### I. Security First (NON-NEGOTIABLE)

No credentials, API keys, tokens, phone numbers, session strings, chat identifiers
containing private links, or any other secret values MAY be hardcoded in source
files, prompt files, documentation, or committed configuration. All sensitive
values MUST be loaded exclusively from a local `.env` file or from process
environment variables at runtime. The `.env` file MUST be listed in `.gitignore`,
and a `.env.example` file with empty placeholder values MUST be committed in its
place so new environments can be bootstrapped without exposing real secrets.

**Rationale**: The tool authenticates as a real Telegram user via MTProto against
a private, paid group. A leaked API ID, API hash, session file, or bot token
could compromise the user's personal Telegram account, paid group access, and
Claude billing. Treating this as non-negotiable prevents convenience shortcuts
from ever becoming a breach.

### II. Simplicity (Single-Script Architecture)

The tool MUST be implemented as a single executable Python script (entry point)
supported by a small number of focused helper modules only where splitting
genuinely improves clarity. The following are prohibited unless a later
amendment justifies them: web frameworks, task queues, ORMs, databases,
message brokers, multi-agent orchestration layers, plugin systems, and any
abstraction introduced for hypothetical future needs. Dependencies MUST be
limited to what is strictly required (at minimum: Telethon for MTProto, the
Anthropic SDK for Claude, `python-telegram-bot` or equivalent for bot delivery,
and `python-dotenv` for environment loading).

**Rationale**: This is a personal automation tool with a narrow purpose. Every
added framework is future maintenance debt against a user who runs the script
unattended from Windows Task Scheduler. YAGNI and KISS govern the architecture.

### III. Externalized Prompt Configuration

Claude prompts MUST NOT be embedded as string literals in Python source files.
Every prompt MUST live in a dedicated Markdown file under the `/prompts`
directory at the repository root. Each topic-chat MAY have its own prompt file
so that tone, depth, and focus can be tuned per chat without editing code. The
Python code MUST load prompt files by path and fail loudly with a clear error
message if a required prompt file is missing. Prompt files MUST be
version-controlled and MUST be written so a non-developer user can edit them
safely.

**Rationale**: Prompt engineering is content work, not code work. Forcing prompt
changes through Python edits would make tuning slow and risky for the user, who
is not a developer by trade. Separating prompts from code respects the Single
Responsibility Principle and treats prompts as first-class configuration.

### IV. Observability (NON-NEGOTIABLE)

Every significant action MUST be logged with an ISO-8601 timestamp, a log level,
and enough context to reconstruct what happened. At minimum the following events
MUST be logged: script start and end, Telegram authentication, each chat read
(with message count), each Claude API call (with model, input token estimate,
and outcome), each bot message send, every handled exception, and every skipped
chat. A log file MUST be written per run into a `logs/` directory with a
timestamped filename, in addition to console output. Silent `except` blocks,
bare `except:` without logging, and swallowed exceptions are forbidden.

**Rationale**: The script runs unattended via Task Scheduler. When it fails at
07:00 on a Tuesday, the log file is the only forensic record. "Silent failure
is not acceptable" is a hard rule because a broken summary the user does not
notice is worse than a visible crash.

### V. Language Separation

All code, identifiers, comments, docstrings, configuration keys, environment
variable names, log messages, commit messages, specifications, plans, tasks,
and project documentation MUST be written in English. All AI-generated content
delivered to the user — i.e., the Claude summaries produced from topic-chats
and forwarded via the bot — MUST be written in Russian, because the source
group communicates in Russian and the user consumes the output in Russian.
Prompt files MUST instruct Claude to respond in Russian explicitly. This split
MUST be preserved even when a chat happens to contain non-Russian messages.

**Rationale**: Mixing natural languages inside code slows review and onboarding.
Producing summaries in the reader's language is a usability requirement. Making
the split explicit removes ambiguity for every future contribution.

### VI. Windows-Native Portability

The tool MUST run on Windows 10 or later using a standard CPython installation
and MUST be scheduleable through Windows Task Scheduler without any additional
runtime layer. WSL, Linux virtual machines, Docker, and containerization of any
kind are explicitly out of scope for the execution environment. File paths,
newline handling, and process invocation MUST be written so they work correctly
on Windows (e.g., use `pathlib.Path`, avoid POSIX-only shell calls). Any
dependency that requires a non-Windows runtime MUST be rejected.

**Rationale**: The user operates exclusively on Windows and requires a scheduled
daily run. Adding WSL or Docker would break the "just double-click to test,
Task Scheduler to automate" workflow and violate the Simplicity principle.

### VII. Graceful Per-Chat Failure

If summarizing a single topic-chat fails for any reason (Telegram read error,
Claude API error, prompt file missing, rate limit, timeout, malformed content),
the tool MUST catch the failure, log it with full context, and continue
processing the remaining chats. The final bot message delivered to the user
MUST include a clearly labeled error section listing every chat that failed
and why, in addition to the successful summaries. A single failing chat MUST
NOT cause the entire run to abort or to deliver no message at all.

**Rationale**: A daily digest is only useful if it is delivered daily. The user
would rather receive nine summaries plus one visible error than receive nothing
because the tenth chat had a transient issue. This principle also protects the
user from silent data loss: every failure is surfaced in the same place the
summaries are read.

## Technical Constraints

- **Language**: Python 3.11 or later.
- **Telegram read path**: Telethon (MTProto User API). The script acts as the
  authenticated user, not as a bot, because bots cannot read messages in
  private paid groups they are not members of.
- **Telegram delivery path**: a separate private Telegram bot owned by the user,
  sending to the user's personal chat only. The bot MUST NOT be added to any
  group.
- **Summarization model**: Claude via the Anthropic API, model selection
  configurable via environment variable with a documented default.
- **Configuration surface**: `.env` for secrets, `/prompts/*.md` for prompt
  content, and a small committed config file (e.g., list of topic-chat IDs and
  their associated prompt filenames) that contains no secrets.
- **State**: a single Telethon session file, listed in `.gitignore`, stored
  outside the repository root if feasible.
- **Output artifacts**: a per-run log file under `logs/` (gitignored).

## Development Workflow

- **Specifications and plans**: feature-level changes MUST go through the
  Spec Kit workflow (`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`). Each plan MUST pass the Constitution Check gate
  against the seven principles above.
- **Prompt changes**: edits to files under `/prompts` MAY be made without a
  full spec cycle, but MUST be committed with a Conventional Commits message
  of type `docs` or `chore(prompts)` and a short description of the tuning
  intent.
- **Commits**: Conventional Commits format (e.g.,
  `feat(summarizer): add per-chat prompt loading`). Commit messages are in
  English (see Principle V).
- **Reviews**: every change MUST be reviewed against this constitution before
  merging. Any deviation MUST either be justified in a Complexity Tracking
  section of the relevant plan or be resolved by amending the constitution
  first.
- **Secrets hygiene check**: before every commit, the author MUST verify that
  no `.env`, session file, token, or phone number is staged. This is a hard
  gate on top of the `.gitignore` rules.

## Governance

- This constitution supersedes all other development practices, style guides,
  and conventions within the project. Where a global rule and this constitution
  conflict, this constitution wins for this repository.
- **Amendment procedure**: amendments MUST be proposed via `/speckit-constitution`,
  MUST update the Sync Impact Report at the top of this file, MUST bump the
  version according to the policy below, and MUST update `LAST_AMENDED_DATE`.
- **Versioning policy** (semantic):
  - **MAJOR**: removing a principle, redefining a principle in a way that
    invalidates prior work, or any backward-incompatible governance change.
  - **MINOR**: adding a new principle or materially expanding guidance.
  - **PATCH**: clarifications, typo fixes, wording refinements with no change
    in meaning.
- **Compliance review**: every pull request description MUST list which
  principles the change touches and confirm compliance. Reviewers MUST reject
  changes that violate NON-NEGOTIABLE principles (I and IV) without exception.
- **Runtime guidance**: day-to-day development guidance (setup, commands,
  coding style) lives in `CLAUDE.md` and `README.md`. Those files MUST remain
  consistent with this constitution; when they drift, this constitution is the
  source of truth.

**Version**: 1.0.0 | **Ratified**: 2026-04-24 | **Last Amended**: 2026-04-24
