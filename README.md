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
- Interactive account add flow from bot (phone -> code -> optional 2FA)
- Welcome messages management (text/photo/video)
- Auto-reply system:
  - custom keyword replies from database
  - enable/disable auto reply globally
  - allow-list users for auto replies
  - optional media reply support
- Public/bulk messaging:
  - send to usernames
  - send to extracted users (`all` mode)
  - duplicate prevention
  - runtime delay control from dashboard (min/max)
  - batch sending + randomized delays
  - emergency stop support
- Extract users from groups/channels (`/extract_group`)
- Templates, analytics, top words, exports
- Export usernames as Excel file (`.xlsx`) sent directly in bot chat
- Random number suffix in outgoing userbot messages (anti-pattern variation)
- Welcome random-number toggle
- Auto REST mode schedule by time (daily on/off)
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

Recommended optional values:
- `ADMIN_PASSWORD`
- `PREFERRED_SESSION`
- `REST_MODE`
- `DEFAULT_DELAY`
- `RANDOM_DELAY_RANGE`

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

You can also add new accounts directly from bot dashboard:
- Accounts -> Add Account
- Enter phone number
- Enter session name
- Enter Telegram login code
- If needed, enter 2FA password

## 5) Run bot

```bash
python -m app.main
```

If you run multiple instances with the same `BOT_TOKEN`, Telegram will return a `Conflict` error.
Run only one active bot process per token.

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
- `/help` show full commands help inside bot
- `/auth <password>` authenticate admin (if enabled)
- `/stats` quick stats
- `/template_save name | content`
- `/template_send <name> <@username>`
- `/extract_group <group_id_or_username>` extract and save users
- `/extract_private [days]` extract users from recent private chats (default: 30 days)
- `/cancel` cancel any active interactive flow

Most management flows are handled through inline dashboard buttons.

## Dashboard Manual

### Welcome Section

- Enable/disable welcome
- Add welcome message with optional photo/video
- Delete/list welcome messages
- Toggle random number in welcome text
- Test welcome message

### Auto Reply Section

- Enable/disable auto reply
- Add custom keyword reply
- Add optional media for custom reply
- Manage allowed users (add/remove/toggle/list)

### Delay Section

- Set minimum delay in seconds
- Set maximum delay in seconds
- Delay is applied at runtime to sending flows

### REST Mode Section

- Enable/disable rest mode immediately
- Set daily automatic ON time (UTC)
- Set daily automatic OFF time (UTC)

### Accounts Section

- List sessions
- Switch active session
- Add account interactively from bot
- Export usernames as Excel file directly in chat
- Cleanup user profiles (keeps logs)

## Public/Bulk Messaging Flow

1. Extract users first:
   - `/extract_group @group_username`
  - or `/extract_private 30` for private-chat interactions
2. Open bulk messaging from dashboard
3. Send message text
4. For targets:
   - use `all` to send to extracted users
   - or provide usernames manually (`@user1,@user2` or one per line)

If `all` returns zero users, extraction has not been done yet (or failed).

The sender now applies runtime delay values configured from the dashboard.

## Auto Reply Flow

1. Enable auto replies from dashboard
2. Add custom keyword reply
3. Optional: manage allowed auto-reply users
4. Incoming message matching keyword triggers reply

Auto-reply delay also follows runtime delay settings (`delay_min`/`delay_max`) from dashboard.

Detailed guide: see [AUTO_REPLY_GUIDE.md](AUTO_REPLY_GUIDE.md)

Arabic user manual: see [USER_MANUAL_AR.md](USER_MANUAL_AR.md)
Dashboard screenshots folder: [docs/images/dashboard/](docs/images/dashboard/)

## Data and Logs

- App logs: `data/logs/app.log`
- Exports: `data/exports/`
- Backups: `data/backups/`
- Sessions: `data/sessions/`
- Media files: `data/media/`

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
or
/extract_private 30
```

3. Username format issues
- Use `@username` or `username`
- Comma-separated and line-separated targets are both supported

4. Flood/Rate limits
- Keep `DEFAULT_DELAY` and `RANDOM_DELAY_RANGE` conservative
- Keep batch sizes small

5. Images/videos are not saved from bot flow
- Ensure `data/media/` exists and is writable

6. Delay settings seem not working
- Set both min and max from dashboard Delay section
- Use flows that send messages (bulk/auto-reply)
- Confirm bot is restarted after major updates

7. REST auto schedule not triggering
- Times are interpreted as UTC
- Configure both ON and OFF times in HH:MM format

## Safety

- Respect Telegram limits and anti-spam policies
- Use opt-in targeting where possible
- Keep REST mode available as emergency pause
- Keep randomization and delay settings conservative to reduce account risk

## License

This repository is licensed under the terms in [LICENSE](LICENSE).
