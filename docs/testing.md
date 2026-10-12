# Testing

## Unit tests (no network, no key)

```bash
cd backend && uv run pytest tests/unit -q
```

These cover:

- **Prompting:** linter rules, the compiler's section order and generated tool lines, raw-prompt parsing.
- **Security:** the Standard Webhooks signature, using the spec's published test vector, plus tamper, stale, and wrong-secret cases; AES-GCM round trips; the SSRF guard; SIP number parsing.
- **Runtime:** the real `SessionController` and LangGraph graph, driven by scripted xAI server events through a recording transport. It checks the start sequence, a handoff that switches voice and carries typed context into the next agent's instructions, rejection of a handoff with a missing required field, and the end-call flow. Results are checked in the database and the checkpoint.

To run the runtime tests against Postgres, set `DATABASE_URL=postgresql://…`.

## Live tests (real xAI API)

```bash
XAI_API_KEY=... uv run pytest tests/live -m live -v
```

- REST: the voice list and an ephemeral token.
- **Handoff:** a typed conversation through the controller over a server-side realtime socket. The caller asks about a phone agent and must be handed to the Voice Specialist. The test checks the new `session.update` (voice and `## Handoff Context`), checks that turns are attributed per agent, and checks that a `grok-4.3` summary is written after the call.
- **Tools in a call:** the GitHub HTTP tool, DeepWiki MCP in both modes, and `web_search` on docs.x.ai.
- **Knowledge:** a document goes through xAI's Files API into a Collection and is answered by xAI's `file_search` (the test then deletes the collection); the same document indexed locally is answered through `search_knowledge`. Both check the stored tool turns, and the Collections test also checks the event log.
- **Transfer, end, and edits:** a simulated `transfer_call`, `end_call` closing the session, and an agent edit applied mid-call as a new `session.update`.
- **Memory and resume:** caller memory recalled on a second call, and "Continue" restoring history by seeding alone.
- **X search:** through the Voice Stack function tool.
- **Optimiser:** a deliberately weak prompt. The lint score must rise, facts must survive, and an unattached tool must be removed.

## API behavior checks

```bash
XAI_API_KEY=... uv run python spikes/phase0.py
```

This checks behaviors the docs leave open and writes `docs/xai-api-notes.md`:

- `client_secrets` with and without `session`; ephemeral-token connects.
- Flat vs nested function-tool shapes; parallel calls.
- Whether voice changes after the first audio (measured by pitch) and speed changes (measured by duration).
- `force_message`, history seeding, system items, per-response instructions, resumption, hosted MCP events, and the transcription model field.

## Browser test with a real call

Start the backend and frontend, then run:

```bash
cd frontend && XAI_API_KEY=... npm run e2e
```

`e2e/global-setup.ts` generates the caller's question with xAI text-to-speech, padded with silence. Chrome plays it as the microphone. The test enters a session-only key through Settings and makes a direct-mode call. It waits for the Front Desk → Voice Specialist handoff and the collected `use_case`, ends the call, and checks the saved conversation and its summary.

## Results on 2026-10-12

These ran against the live xAI API:

| Area | Result |
|---|---|
| Unit tests | 26 passed (SQLite and Postgres) |
| Live backend tests | 9 passed: handoff, tools, knowledge in Collections mode (Files API → Collection → `file_search`, with recorded tool turns and events) and local mode, transfer/end/edit, memory/resume, X search, optimiser, REST. Each test has a 300 s limit because realtime turns can take over two minutes when xAI is slow. |
| Browser calls with real speech | Passed in both direct and relay mode: greeting → spoken question → handoff with `use_case` → specialist speaks → summary saved |
| Phase 0 | See `docs/xai-api-notes.md`. Voice switches mid-session, both tool shapes work, seeding works. Native resumption replays assistant turns only. Native `x_search` does not run its inner tool. |
| Phone numbers | Registered with xAI from the UI (signing secret returned and stored), a signed webhook routed, then deleted from the UI and confirmed gone at xAI |
| Call control | `refer` and `hangup` reach xAI and return 404 for an unknown call. |
| Custom voices | Listing works. Outside the supported region, creating returns 403 ("not available in your region"), and the UI shows the notice. |
| UI with a key | 28 built-in voices with playable samples, the optimiser dialog (3 variants), and workspace key save and remove |

## SIP without a carrier

```bash
uv run voicestack sip simulate --to +18005550199 --url http://localhost:8000
```

See [telephony-sip.md](telephony-sip.md#test-without-a-carrier) for what this covers and what it cannot.

## Static checks

```bash
cd backend && uv run ruff check src tests spikes
cd frontend && npm run typecheck && npm run build
```
