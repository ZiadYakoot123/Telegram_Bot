#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[codespaces] Created .env from .env.example"
fi

if grep -q "your_api_hash_here" .env || grep -q "123456:ABCDEF_your_bot_token" .env; then
  cat <<'MSG'
[codespaces] .env still has example values.
Update .env (or inject secrets) before running production actions.
Required: API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS
MSG
fi

echo "[codespaces] Building and starting containers..."
docker compose up --build -d

echo "[codespaces] Current services:"
docker compose ps

cat <<'NEXT'

Next commands:
1) One-time session authorization
   docker compose run --rm app python -m app.clients.session_login

2) Follow app logs
   docker compose logs -f app

3) Stop services
   docker compose down
NEXT
