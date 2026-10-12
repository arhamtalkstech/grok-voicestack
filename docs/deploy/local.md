# Run locally or on a VM

## Development (hot reload)

```bash
cp .env.example .env
cd backend && uv sync && uv run voicestack serve --reload     # http://localhost:8000
cd frontend && npm install && npm run dev                      # http://localhost:5173 (proxies /api to :8000)
```

Data lives in `./data` (SQLite, uploads, embedding models, and a development encryption key). Delete the folder to start fresh. The sample landscape is seeded when the database has no agents (`SEED_EXAMPLE=true`).

## Docker Compose (app + Postgres)

```bash
deploy/compose/up.sh          # or: voicestack deploy compose
```

The script:

1. Copies `.env.example` to `.env` if needed.
2. Generates `APP_ENCRYPTION_KEY` if it is empty.
3. Runs `docker compose up -d --build`.
4. Waits for `/readyz`.
5. Runs `voicestack doctor` inside the container.

The UI is at `http://localhost:${HOST_PORT:-8000}`. Use `DRY_RUN=1 deploy/compose/up.sh` to see the commands first.

On a VM, put a TLS-terminating proxy in front of it (Caddy, nginx) and set:

- `AUTH_MODE=token` with `ADMIN_TOKEN`, or `AUTH_MODE=proxy` behind an identity-aware proxy.
- `PUBLIC_BASE_URL=https://your-host` if you want phone numbers.

WebSockets must pass through the proxy with long read timeouts (`proxy_read_timeout 3600s` in nginx).

## Image

```bash
docker build -t voicestack .                                           # about 1.4 GB, non-root, port 8000
docker build --build-arg PRELOAD_EMBEDDINGS=true -t voicestack .       # bakes the local embedding model in
docker run -p 8000:8000 -e APP_ENCRYPTION_KEY=... -e DATABASE_URL=... voicestack
```

The same image serves every role: set `ROLE=app` or `ROLE=telephony` to split them.
