# Telegram Manager Bot (Ethical Automation)

Production-ready, modular Telegram management system built with:
- Telethon (MTProto user client)
- python-telegram-bot (admin control panel)
- SQLite by default, optional PostgreSQL
- APScheduler for recurring jobs
- Pandas for CSV/Excel reports

This project is designed for **ethical, safety-limited automation** and should be used in compliance with Telegram Terms of Service.

## Features

- Data extraction from groups/channels (with delay control)
- Interaction-based contact detection and filtering windows (7/30/custom days)
- Messaging by username or phone (text/file/image/link)
- Duplicate prevention (never send same target twice)
- Batch sending + randomized delays + emergency stop
- Safe gradual group additions (daily safety cap)
- Number checks and country-based number filtering
- Keyword auto-replies with configurable delay
- One-time and recurring scheduling
- Analytics: sent/received counts, top users, top words
- CSV/Excel exports
- InlineKeyboard admin dashboard bot
- Optional admin password on top of admin Telegram IDs
- Templates save/reuse
- Daily backup (SQLite)
- Multi-session support and safe active-session switching
- Rest mode to pause automation

## Project Structure

```text
telegram_manager/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── logger.py
│   ├── clients/
│   │   ├── telegram_client.py
│   │   ├── sessions_manager.py
│   │   └── session_login.py
│   ├── modules/
│   │   ├── extractor.py
│   │   ├── sender.py
│   │   ├── auto_reply.py
│   │   ├── scheduler.py
│   │   ├── analytics.py
│   │   ├── filters.py
│   │   ├── batch_system.py
│   │   └── backup.py
│   ├── bot/
│   │   ├── control_bot.py
│   │   └── keyboards.py
│   └── utils/
│       ├── delays.py
│       ├── validators.py
│       └── helpers.py
├── data/
│   ├── backups/
│   ├── exports/
│   ├── logs/
│   └── sessions/
├── .env.example
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## 1. Prerequisites

- Python 3.11+
- Telegram account for Telethon user session
- Bot token from `@BotFather`

## 2. Get Telegram API ID / API HASH

1. Open `https://my.telegram.org`
2. Log in with your phone number
3. Go to `API development tools`
4. Create an app and copy:
- `api_id`
- `api_hash`

## 3. Setup

```bash
# Windows PowerShell
cd telegram_manager
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

```bash
# Linux/macOS
cd telegram_manager
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and fill at minimum:
- `API_ID`
- `API_HASH`
- `BOT_TOKEN`
- `ADMIN_IDS=12345,67890`
- `DATABASE_URL` (optional; leave empty for SQLite)
- `DEFAULT_DELAY`
- `RANDOM_DELAY_RANGE`

## 4. Authorize Telethon Session (one-time per account)

```bash
python -m app.clients.session_login
```

Enter a session name (example: `default`) and complete Telegram login. Session file will be stored in `data/sessions/`.

## 5. Run

```bash
python -m app.main
```

This is the one-command runtime entrypoint.

## 6. Control Panel Bot Usage

Open your bot in Telegram and use:
- `/start` for dashboard
- `/auth <password>` if `ADMIN_PASSWORD` is set
- `/stats` for quick stats
- `/template_save name | content`
- `/template_send <name> <@username>`

Inline dashboard includes:
- Start Sending / Stop Sending
- Rest Mode
- Stats
- Templates
- Accounts / Sessions

## 7. Docker (optional)

```bash
docker compose up --build -d
```

If using PostgreSQL container, set in `.env`:
```env
DATABASE_URL=postgresql+asyncpg://telegram:telegram@postgres:5432/telegram_manager
```

## 8. Safety Notes (Important)

- Use only opt-in or interaction-based targeting.
- Respect Telegram anti-spam limits and local law.
- Keep conservative delays and small batch sizes.
- Avoid unsolicited mass campaigns.
- Do not bypass Telegram restrictions.
- `Rest Mode` can pause automation quickly.
- Emergency stop is available via dashboard `Stop Sending`.

## 9. Logging, Reports, Backups

- Runtime logs: `data/logs/app.log`
- Analytics export location: `data/exports/`
- SQLite backups: `data/backups/`
- Flood waits and errors are written to operation logs and file logs.

## 10. Development Notes

- Architecture is async-safe (`asyncio`, APScheduler async scheduler, SQLAlchemy async engine).
- Secrets are loaded from `.env`; no hardcoded credentials.
- The system is structured for extension by adding modules and handlers.

## 11. GitHub Codespaces (Docker In Cloud)

You can run this project fully in Codespaces without Docker on your local machine.

### What was added

- `.devcontainer/devcontainer.json` for a Codespaces-ready Python + Docker-in-Docker environment
- `scripts/codespaces-start.sh` as the one-command startup flow

### Steps

1. Open repository in GitHub Codespaces.
2. Wait for container setup to complete (`postCreateCommand` installs requirements and creates `.env` if missing).
3. Configure `.env` values (or inject secrets) for:
	- `API_ID`
	- `API_HASH`
	- `BOT_TOKEN`
	- `ADMIN_IDS`
4. Run the one-command startup:

```bash
bash scripts/codespaces-start.sh
```

### First-time Telegram session authorization

Run once per account/session:

```bash
docker compose run --rm app python -m app.clients.session_login
```

### Useful commands in Codespaces

```bash
# Show container status
docker compose ps

# App logs
docker compose logs -f app

# Stop stack
docker compose down
```

### Notes

- Codespaces is great for development/testing and remote runs.
- It is not ideal for always-on production because Codespaces can suspend/stop.
- For 24/7 production, deploy the same compose stack to a VPS.
