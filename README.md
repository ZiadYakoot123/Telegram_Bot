# Telegram Bot Manager

A modular Telegram automation manager built with Telethon + python-telegram-bot.

This project provides:
- Userbot features (Telethon session)
- Admin control bot dashboard
- Auto-reply system (custom replies + user targeting)
- Bulk/public messaging with safety controls
- Extraction, analytics, scheduling, and backups

Use responsibly and follow Telegram Terms of Service.

## Features

- Multi-session Telethon account support
- Admin dashboard via Telegram bot
- Welcome messages management
- Auto-reply system:
  - custom keyword replies from database
  - enable/disable auto reply globally
  - allow-list users for auto replies
  - optional media reply support
- Public/bulk messaging:
  - send to usernames
  - send to extracted users (`all` mode)
  - duplicate prevention
  - batch sending + randomized delays
  - emergency stop support
- Extract users from groups/channels (`/extract_group`)
- Templates, analytics, top words, exports
- Daily SQLite backup job
- REST mode to pause automation quickly

## Project Structure

```text
Telegram_Bot/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── logger.py
│   ├── bot/
│   ├── clients/
│   ├── modules/
│   └── utils/
├── data/
│   ├── backups/
│   ├── exports/
│   ├── logs/
│   └── sessions/
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Requirements

- Python 3.11+
- Telegram API credentials (`API_ID`, `API_HASH`) from https://my.telegram.org
- Telegram bot token (`BOT_TOKEN`) from BotFather
- At least one Telegram account for Telethon session login

## Quick Start (Any Device)

## 1) Clone

```bash
git clone https://github.com/ZiadYakoot123/Telegram_Bot.git
cd Telegram_Bot
```

## 2) Create environment file

```bash
cp .env.example .env
```

Fill these required values in `.env`:
- `API_ID`
- `API_HASH`
- `BOT_TOKEN`
- `ADMIN_IDS`

## 3) Install dependencies

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Alpine Linux note

If pip is restricted by system policy, install `py3-pip` and use a virtual environment.

## 4) Authorize Telethon session (required for userbot features)

```bash
python -m app.clients.session_login
```

- Enter session name (recommended: `default`)
- Enter phone number and Telegram login code

Without this step, extract/public messaging and other Telethon features will not work.

## 5) Run bot

```bash
python -m app.main
```

## Docker Run

```bash
docker compose up --build -d
```

To view logs:

```bash
docker compose logs -f app
```

To stop:

```bash
docker compose down
```

## GitHub Codespaces

```bash
bash scripts/codespaces-start.sh
```

If you need session authorization in containerized setup:

```bash
docker compose run --rm app python -m app.clients.session_login
```

## Core Commands (Telegram Bot)

- `/start` open dashboard
- `/auth <password>` authenticate admin (if enabled)
- `/stats` quick stats
- `/template_save name | content`
- `/template_send <name> <@username>`
- `/extract_group <group_id_or_username>` extract and save users

## Public/Bulk Messaging Flow

1. Extract users first:
   - `/extract_group @group_username`
2. Open bulk messaging from dashboard
3. Send message text
4. For targets:
   - use `all` to send to extracted users
   - or provide usernames manually (`@user1,@user2` or one per line)

If `all` returns zero users, extraction has not been done yet (or failed).

## Auto Reply Flow

1. Enable auto replies from dashboard
2. Add custom keyword reply
3. Optional: manage allowed auto-reply users
4. Incoming message matching keyword triggers reply

Detailed guide: see [AUTO_REPLY_GUIDE.md](AUTO_REPLY_GUIDE.md)

## Data and Logs

- App logs: `data/logs/app.log`
- Exports: `data/exports/`
- Backups: `data/backups/`
- Sessions: `data/sessions/`

## Troubleshooting

1. `Session 'default' is not authorized yet`
- Run:
```bash
python -m app.clients.session_login
```

2. Bulk send to `all` does not send
- Run extraction first:
```text
/extract_group @group_username
```

3. Username format issues
- Use `@username` or `username`
- Comma-separated and line-separated targets are both supported

4. Flood/Rate limits
- Keep `DEFAULT_DELAY` and `RANDOM_DELAY_RANGE` conservative
- Keep batch sizes small

## Safety

- Respect Telegram limits and anti-spam policies
- Use opt-in targeting where possible
- Keep REST mode available as emergency pause

## License

This repository is licensed under the terms in [LICENSE](LICENSE).
