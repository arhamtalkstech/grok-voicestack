---
name: deploy-compose
description: Run Voice Stack with Docker Compose (app + Postgres) on a laptop or a single VM, and check it is healthy. Use when asked to run, start, or self-host Voice Stack locally or on one machine.
---

# Run Voice Stack with Docker Compose

Details are in `docs/deploy/local.md`.

1. Check Docker is running: `docker info`.
2. Run `DRY_RUN=1 deploy/compose/up.sh` and show the commands. Then run `deploy/compose/up.sh`. It creates `.env` from `.env.example` if missing and generates `APP_ENCRYPTION_KEY`. It never prints secret values.
3. The script ends with `voicestack doctor`. Report any `fail` lines and fix them. `warn` lines about a missing xAI key or `PUBLIC_BASE_URL` are expected until the user provides them.
4. On a VM, follow the TLS proxy and `AUTH_MODE` guidance in the doc before exposing the port.

To stop: `docker compose down`. Add `-v` only if the user wants their data deleted.
