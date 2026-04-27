# Quickstart

**Feature**: Telegram Group Summarizer
**Date**: 2026-04-24

A smoke-run guide that takes a fresh clone to a delivered Russian
summary in the operator's bot DM. All steps are Windows-first.

---

## 1. Prerequisites

- Python 3.11+ installed on Windows, `python --version` reachable from
  `cmd` or PowerShell.
- Telegram account that is a paying member of the target group.
- A delivery bot created via BotFather; the operator has sent that bot
  at least one message already (so the chat exists).
- Anthropic API key with access to `claude-sonnet-4-6`.
- MTProto app credentials from
  [https://my.telegram.org](https://my.telegram.org) (API id + hash).

---

## 2. Clone and install

```powershell
git clone <repo-url> telegram-summary
cd telegram-summary
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 3. Configure `.env`

Copy the template and fill in real values:

```powershell
Copy-Item .env.example .env
notepad .env
```

Required variables (fail-fast at startup if any is missing):

```
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=+4915xxxxxxxxx
TELEGRAM_GROUP_NAME=Exact Display Name Of The Group
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ANTHROPIC_API_KEY=
```

Optional (with documented defaults):

```
LOOKBACK_HOURS=24
LOG_LEVEL=INFO
ANTHROPIC_MODEL=claude-sonnet-4-6
```

---

## 4. One-time interactive login

Run the tool once from an interactive shell so Telethon can prompt for
the SMS/app code and persist a session file:

```powershell
python main.py
```

Expected on first run:

1. Telethon asks for the auth code that Telegram just sent to the
   operator's phone / Telegram app.
2. After the code is accepted, `telegram.session` is written next to
   `main.py` (gitignored).
3. The tool proceeds to read the group and deliver summaries to the
   bot DM.

After this single interactive run, subsequent runs (including from
Windows Task Scheduler) are silent.

---

## 5. Validate the happy path

After the first successful run:

- [ ] The operator's DM with the bot contains one Russian summary per
  topic-chat **in stable order**, plus one Russian overall summary at
  the end. **(User Story 1 acceptance)**
- [ ] If any chat failed, a clearly labeled error section is appended
  as the last bot message and lists each failed chat with a reason.
  **(User Story 2 acceptance)**
- [ ] A dated log file exists under `logs/` with an ISO-8601 timestamp
  on every line and final summary: processed / failed / sent / duration.
  **(FR-022, FR-024)**
- [ ] No secret value appears anywhere in the log file.

---

## 6. Validate the zero-activity heartbeat

Set `LOOKBACK_HOURS=1` during a quiet hour and run:

```powershell
python main.py
```

Expected: exactly one Russian "no new activity" bot message; no Claude
API calls happened (verify in the log); run exits with code 0.
**(FR-021a, spec Edge Case)**

---

## 7. Validate the fail-fast config path

Comment out `ANTHROPIC_API_KEY` in `.env` and run:

```powershell
python main.py
```

Expected: a single error log line naming `ANTHROPIC_API_KEY`, exit code
non-zero, in under 5 seconds, and **no** Telegram / Claude / bot
network calls. **(FR-004, SC-008)**

Restore the value before continuing.

---

## 8. Register the Windows Task Scheduler job

1. Identify the Python executable inside the virtualenv:
   `C:\Hantel\Projekte\...\telegram-summary\.venv\Scripts\python.exe`
2. Identify the absolute path to `main.py`:
   `C:\Hantel\Projekte\...\telegram-summary\main.py`
3. Open Task Scheduler → **Create Task** (not "Create Basic Task" —
   the advanced dialog allows the working-directory setting we need).
4. **General** tab: name `TelegramDailySummary`, set
   *"Run whether user is logged on or not"* if the machine should
   summarize without an active session.
5. **Triggers** tab: *Daily* at a recommended time of **07:00** local,
   *Recur every 1 day*.
6. **Actions** tab: *Start a program*.
   - Program/script: the Python exe path from step 1.
   - Add arguments: `main.py`
   - **Start in (optional)**: the absolute directory from step 2's
     parent. *(Critical — without this, `.env` and `prompts/` do not
     load.)*
7. **Conditions** tab: uncheck *"Start the task only if the computer
   is on AC power"* on laptops.
8. **Settings** tab: enable *"Run task as soon as possible after a
   scheduled start is missed"*.
9. Save; Task Scheduler will prompt for the operator's Windows password.
10. Right-click the task → **Run** to verify it completes without
    interactive input (since step 4 already established the session).

---

## 9. Viewing the log after a scheduled run

- Open `logs\YYYY-MM-DD.log` in the project directory.
- Each line starts with `[<ISO-8601>] [<LEVEL>] [<module>]`.
- The last line is the end-of-run summary: processed / failed / sent /
  duration.

If a scheduled run ever produces no bot message at all, the log file
is still written and is the first forensic artifact to check.
