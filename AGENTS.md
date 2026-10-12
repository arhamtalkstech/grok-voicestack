# AGENTS.md: Voice Stack

Working notes for anyone (human or agent) changing this project. The product overview is in `README.md`, and the design is in `docs/architecture.md`.

## Layout and commands

| Task | Command |
|---|---|
| Backend dev server | `cd backend && uv run voicestack serve --reload` |
| Frontend dev server | `cd frontend && npm run dev` |
| Unit tests | `cd backend && uv run pytest tests/unit -q` |
| Live tests | `XAI_API_KEY=... uv run pytest tests/live -m live` |
| API behavior checks | `XAI_API_KEY=... uv run python spikes/phase0.py` |
| Browser test with a real call | `cd frontend && XAI_API_KEY=... npm run e2e` (servers running) |
| Lint / types | `uv run ruff check src tests spikes` · `npm run typecheck` |
| Health check | `uv run voicestack doctor [--url URL]` |

## Rules for changes

- Use xAI's public docs (docs.x.ai) as the source for realtime fields and endpoints. Markdown copies of the voice docs are in `xai-speech-docs/` (refresh with `xai-speech-docs/fetch.sh`). When a behavior is undocumented, add a check to `spikes/phase0.py` before relying on it.
- Use `grok-4.3` for text-model work (optimiser, summaries) through `langchain-xai`. Pin voice-model changes in `VOICE_MODEL`.
- Keep the graph transport-agnostic: nodes return `actions`, and the controller performs them. Do not send realtime events from graph nodes.
- Every tool name the compiler or a prompt mentions must be attached. The linter enforces this, so keep it passing.
- Never log or return secret values. Credentials go through `tools/secrets.py` or `credentials.py`, encrypted with `security/crypto.py`.
- UI tokens live in `frontend/src/styles/tokens.css`. Use the Tailwind theme names (`bg-l1`, `text-fg-2`, `border-line`), not raw hex values.
- Test against real services where possible. If something can only be simulated (SIP calls), say so in the docs.

## Gaps

Open items and unverified paths are tracked in `docs/known-gaps.md`. Update it when you close or find one.

## Skills

Runbooks for common operations are in `.grok/skills/`: `deploy-cloudrun`, `deploy-compose`, `deploy-kubernetes`, `register-sip-number`, `add-connector`, `add-knowledge-provider`. They are plain Markdown, and any coding agent can follow them.
