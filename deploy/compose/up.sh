#!/usr/bin/env bash
# Start Voice Stack + Postgres with Docker Compose and check it is healthy.
#   DRY_RUN=1 deploy/compose/up.sh   # print commands only
set -euo pipefail
cd "$(dirname "$0")/../.."
DRY_RUN="${DRY_RUN:-0}"
run() { echo "+ $*"; if [ "$DRY_RUN" != "1" ]; then "$@"; fi; }

if [ ! -f .env ]; then
  run cp .env.example .env
fi
if ! grep -qE '^APP_ENCRYPTION_KEY=.+' .env; then
  KEY="$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  echo "+ setting APP_ENCRYPTION_KEY in .env (value hidden)"
  if [ "$DRY_RUN" != "1" ]; then
    if grep -q '^APP_ENCRYPTION_KEY=' .env; then sed -i.bak "s|^APP_ENCRYPTION_KEY=.*|APP_ENCRYPTION_KEY=${KEY}|" .env && rm -f .env.bak
    else echo "APP_ENCRYPTION_KEY=${KEY}" >> .env; fi
  fi
fi

run docker compose up -d --build
HOST_PORT="$(grep -E '^HOST_PORT=' .env | cut -d= -f2 || true)"
URL="http://localhost:${HOST_PORT:-8000}"
if [ "$DRY_RUN" != "1" ]; then
  echo "Waiting for ${URL}/readyz"
  for _ in $(seq 1 60); do
    if curl -fsS "${URL}/readyz" >/dev/null 2>&1; then break; fi
    sleep 2
  done
fi
run docker compose exec app voicestack doctor --url http://localhost:8000
echo "Open ${URL}"
