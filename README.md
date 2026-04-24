# telegram-news-summarizer

A Windows-native CLI tool that reads messages from a private paid Telegram
group, asks Claude to produce a Russian-language summary per topic-chat
plus an overall daily summary, and delivers the result via a private bot
to the operator's personal chat. One entry point (`main.py`), five focused
helper modules, and prompts as editable Markdown files under `prompts/`.

## Requirements

- Windows 10 / 11
- Python 3.11 or later on `PATH`
- Membership in the target Telegram group
- Anthropic API key with access to `claude-sonnet-4-6`
- Telegram MTProto app id + hash from <https://my.telegram.org>
- A delivery bot created via BotFather; the operator has already sent the
  bot at least one message so the chat exists

## Install

```powershell
git clone <repo-url> telegram-summary
cd telegram-summary
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configure

Copy the template and fill in real values:

```powershell
Copy-Item .env.example .env
notepad .env
```

Required variables (fail-fast at startup if any is missing or empty):

| Variable | Meaning |
|----------|---------|
| `TELEGRAM_API_ID` | MTProto app id |
| `TELEGRAM_API_HASH` | MTProto app hash |
| `TELEGRAM_PHONE` | international format (e.g. `+4915xxxxxxxxx`) |
| `TELEGRAM_GROUP_NAME` | exact display name of the target group |
| `TELEGRAM_BOT_TOKEN` | BotFather token for the delivery bot |
| `TELEGRAM_CHAT_ID` | numeric id of the operator's DM with the bot |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |

Optional variables (with defaults):

| Variable | Default | Meaning |
|----------|---------|---------|
| `LOOKBACK_HOURS` | `24` | size of the read window; must be > 0 |
| `LOG_LEVEL` | `INFO` | `DEBUG` or `INFO` |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Claude model id |

## First-run interactive login

Telethon needs an SMS/app code on the **first** run. Run the tool once
from an interactive shell:

```powershell
python main.py
```

1. Telethon asks for the auth code sent to the phone.
2. On success, a `telegram.session` file is written next to `main.py`
   (gitignored).
3. Subsequent runs reuse the session silently — no prompt is ever shown.

## Windows Task Scheduler setup

Once the interactive login has persisted `telegram.session`, register a
daily scheduled job:

1. **Identify paths**:
   - Python executable inside the venv, e.g.
     `C:\Hantel\Projekte\CLAUDE\telegram-news-summarizer\.venv\Scripts\python.exe`
   - Absolute directory of `main.py`, e.g.
     `C:\Hantel\Projekte\CLAUDE\telegram-news-summarizer`
2. **Open Task Scheduler** → **Create Task** (not "Create Basic Task" —
   the advanced dialog exposes the critical "Start in" setting).
3. **General tab**: name it `TelegramDailySummary`. Tick
   *"Run whether user is logged on or not"* if the machine should
   summarize without an active session.
4. **Triggers tab**: *Daily* at a recommended time of **07:00** local,
   *Recur every 1 day*.
5. **Actions tab**: *Start a program*.
   - Program/script: the Python executable path from step 1.
   - Add arguments: `main.py`
   - **Start in (optional)**: the absolute project directory from step 1.
     *(Critical — without it `.env` and `prompts/` will not load.)*
6. **Conditions tab**: on laptops, uncheck *"Start the task only if the
   computer is on AC power"*.
7. **Settings tab**: enable *"Run task as soon as possible after a
   scheduled start is missed"*.
8. Save; Task Scheduler will prompt for the operator's Windows password.
9. Right-click the task → **Run** to verify it completes without any
   interactive prompt (the `.session` file from the one-time login is
   being reused).

Logs for each run live under `logs\YYYY-MM-DD.log`. Each line starts with
`[<ISO-8601>] [<LEVEL>] [<module>]`; the last line is the end-of-run
summary: `processed / failed / sent / duration`.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Startup error naming a variable | Missing/empty `.env` entry | Add or correct the variable; rerun. |
| `Prompt file not found: ...\prompts\chat_summary.md` | Per-chat prompt missing | Restore the file; the failing chat's reason appears in the labeled error section, other chats still deliver. |
| `Prompt file not found: ...\prompts\overall_summary.md` | Overall prompt missing | Per-chat summaries still deliver, overall is skipped, run exits non-zero. Restore the file. |
| Claude call fails with `context_length_exceeded` | Window too large | Reduce `LOOKBACK_HOURS`; the failing chat is reported in the labeled error section. |
| Run exits with auth-revoked notice | Telegram session was invalidated | Delete `telegram.session`, rerun interactively to re-authenticate. |
| Bot message never arrives | Bot blocked/revoked or wrong `TELEGRAM_CHAT_ID` | Inspect the dated log file — delivery failure is logged with the payload size and endpoint. Exit code is non-zero. |
| On a quiet day no summary arrives but a Russian heartbeat is sent | Zero new messages in the window | Expected behavior (FR-021a). |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Nominal run (including quiet-day heartbeat; per-chat failures delivered in the labeled error section) |
| 1 | Configuration validation failed |
| 2 | At least one bot delivery failed |
| 3 | Missing overall prompt file — per-chat summaries delivered, overall aborted |
| 4 | Telegram session revoked / authentication unrecoverable |
