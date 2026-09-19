# TailaBot — RemoteCoding

> A private Telegram bot that turns your phone into a remote control for **opencode** —
> the agent that reads, edits, runs tests and ships files in your projects.

**TailaBot — RemoteCoding** is a dedicated [aiogram](https://docs.aiogram.dev/) (Python)
Telegram bot that acts as a text-and-buttons front-end for [opencode](https://opencode.ai).
You ask for a task from your phone; opencode executes it on your machine and the bot
returns the result — text, file, screenshots and menu shortcuts — in the same chat.

Designed for a single owner (allowlist by `chat_id`), with inline menus organized per
project, real-time progress notifications and persistent sessions.

---

## Features

- **Talk to your codebase from Telegram** — send a prompt such as *"run the tests of
  project X"* or *"what did we do this week?"* and get an actual answer from opencode.
- **Project-aware inline menus** — quick actions per project (run test harness, ZIP a
  deliverable, show a summary, take a screenshot).
- **Exclusive access** — only the owner's `chat_id` is accepted; everyone else is ignored.
- **Progress in real time** — throttled status notifications while a task is running.
- **Session continuity** — each conversation maps to a persistent opencode session
  (`--session`), so follow-up messages keep context.
- **Safe by design** — no credential ever stored in code, docs or logs; everything lives
  in a local, untracked `.env`.
- **Windows-first** — detachable launcher (`start_tailabot.bat`) with log files; works on
  any platform that runs Python + opencode.

---

## Architecture

```
Telegram (owner)
     │  update
     ▼
[tailabot_remote.py]         aiogram 3.x — allowlist, commands, inline keyboards
     │  task (text / file / button)
     ▼
[opencode_bridge.py]         spawns: opencode run --format json --dir <workdir>
     │                          (+ --session for continuity, + --model explicitly)
     ▼
opencode  ◄──►  your projects (run tests, edit files, produce artifacts)
     │
     ├── final text  → sent to chat
     ├── artifact    → sent as document (e.g. a ZIP)
     ├── screenshot  → sent as photo (via Playwright MCP, when the task is UI)
     └── link        → sent when the task produced a URL
```

No `--attach` flag is used: on recent opencode versions it emits only a `step_start`
event and never forwards the text events to the CLI, which made the bot reply
*"(no text response)"*. The bridge now calls `opencode run --format json` directly, which
keeps the real `type:"text"` events flowing and preserves session state in the same
`opencode.db`.

---

## Getting started

### Requirements

- Python 3.10+
- [opencode](https://opencode.ai) installed and available on `PATH`
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### 1. Create the bot

1. Open Telegram and message **@BotFather**.
2. Send `/newbot`, pick a display name (e.g. *Taila Bot*) and a username that ends
   in `bot` (e.g. `TailaBot_RemoteCoding_bot`).
3. Copy the token BotFather returns.
4. Optional polish: `/setdescription RemoteCoding` and `/setabouttext RemoteCoding`.
5. Set the command menu with `/setcommands`:
   ```
   start - Open main menu
   menu - Open menu
   status - opencode server status
   help - Help
   ```
6. Find your numeric `chat_id` — ask [@userinfobot](https://t.me/userinfobot) or run
   `python check_chat_id.py` after messaging the bot once.

### 2. Configure

```bash
pip install -r requirements.txt
copy .env.example .env
```

Fill `.env`:

```ini
BOT_TOKEN=your_token_here
OWNER_CHAT_ID=your_numeric_chat_id
WORK_ROOT=C:\Users\you\Documents\your projects root
OPENCODE_MODEL=your-preferred-model
```

> **Security:** `BOT_TOKEN` and `OWNER_CHAT_ID` are personal credentials. They must live
> **only** in your local `.env` (which is git-ignored). Never paste them into docs, chats
> or generated code.

### 3. Run

```bash
python tailabot_remote.py
```

Or, on Windows, start it detached:

```
start_tailabot.bat
```

Then open the chat with your bot, send `/start`, pick an action or type any task, and
watch opencode execute it.

---

## Repository layout

| File | Purpose |
|---|---|
| `tailabot_remote.py` | Telegram bot: allowlist, commands and inline menus |
| `opencode_bridge.py` | Runs `opencode run` and parses the JSON event stream |
| `remote_log.py` | Persists a local audit log of remote tasks (`REMOTE_LOG.md`, git-ignored) |
| `check_chat_id.py` | Helper to discover your Telegram `chat_id` |
| `rotina.py` | Lightweight local routine/scheduler (optional) |
| `.env.example` | Template variables — never the real values |
| `requirements.txt` | Python dependencies (`aiogram`, `python-dotenv`) |
| `start_tailabot.bat` | Detached Windows launcher with logs |

---

## Roadmap

- **Phase 1 (current)** — local bot with inline menus, real responses, session
  continuity, real-time progress. **Working and validated end-to-end.**
- **Phase 2** — message attachments (document/PDF/MD into a session), screenshots via
  the Playwright MCP server, ZIP delivery, persisted task state.
- **Phase 3** — timeouts, one-task-at-a-time queue, SQLite activity log, optional VPS
  deployment as a service, webhook transport instead of polling.

---

## Security notes

This repository is a portfolio reference. It contains **no** tokens, keys or private
identifiers — mock values only. Production credentials are stored exclusively in a local
`.env` file that is deliberately excluded from version control.

---

## Disclaimer

This is a personal tool tailored to its owner's workflow and machine. It is published
as a reference/portfolio project; run it at your own risk and review the code before
adapting it to your environment. Telegram and opencode are third-party services — this
project is not affiliated with either.