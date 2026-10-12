# Architecture

Voice Stack has one Python backend (FastAPI), one React UI, and a database. The xAI realtime model runs every conversation. Voice Stack is the control plane around it: it stores the agents, compiles their configuration, executes tools, routes handoffs, keeps history, and answers phone calls.

```
Browser ──REST──────────────▶ FastAPI ── Postgres/SQLite (agents, conversations, turns, secrets)
   │  └─control WebSocket───▶ SessionController ── LangGraph runtime (checkpointer + store)
   │                              │        └── Tool registry (HTTP, plugins, managed MCP, knowledge)
   └─ephemeral token──▶ wss://api.x.ai/v1/realtime ◀── Relay / SIP transports (server-side key)
xAI SIP ──signed webhook──▶ /webhooks/xai/call-incoming ──▶ call worker (SipTransport)
```

## The pieces

| Piece | Where | What it does |
|---|---|---|
| Specs | `runtime/specs.py`, `runtime/loader.py` | Immutable views of agents, edges, tools, and knowledge. Published versions are stored as one JSON snapshot, so editing a draft never changes what phone callers hear. |
| Prompt compiler | `prompting/compiler.py` | Builds `instructions` in the prompting guide's section order. It adds a line for each attached transfer, knowledge, and end-call tool, so the prompt names only tools that exist. |
| Session renderer | `runtime/session_config.py` | Agent → the `session` object for `session.update`: voice, speed, tools, transcription hints, pronunciation map, reasoning, idle timeout, resumption. |
| LangGraph runtime | `runtime/graph.py` | One graph per landscape, one checkpointed thread per conversation (see below). |
| SessionController | `runtime/controller.py` | Consumes xAI server events, persists turns, invokes the graph, and turns graph actions into xAI client events. All graph work runs on one ordered worker, so the transport reader never blocks. |
| Transports | `runtime/transports/` | `BrowserDirectTransport` (the browser holds the xAI socket), `RelayTransport` (audio through the server), `SipTransport` (server joins an inbound phone call). |
| Bus | `runtime/bus.py` | In-process pub/sub that feeds the live dock, the Landscape overlay, and the call monitor. |

## The LangGraph runtime

The graph follows LangGraph's swarm pattern. An `active_agent` field decides which node handles each event:

```
START → ingest → <active agent> [→ <handoff target>] → END
        ingest → post_call → END            (when the call ends)
```

- **State** (`VoiceState`): `messages` (LangChain messages, assistant turns named by agent), `active_agent`, `context` (fields collected across handoffs), `handoffs`, `channel`, `contact_id`, `caller_context`, `actions`, `call_summary`.
- **ingest** appends transcripts. Function calls go to the active agent's node, and `end` goes to `post_call`.
- **Agent nodes** execute function tools in parallel as LangChain tools, with a timeout per tool. When the model calls `transfer_to_<agent>`, the node validates the context contract and returns `Command(goto=<target>, update={active_agent, context, messages + ToolMessage, arrival})`. The target node runs in the same step and emits the `session.update` for the new agent and a `response.create` that waits for playback to finish.
- **post_call** asks `grok-4.3` (structured output) for a summary, a disposition, extracted fields, and caller facts. It writes the facts to the LangGraph store under `("contacts", contact_id)`.
- **Persistence:** `AsyncSqliteSaver`/`AsyncSqliteStore` in development, `AsyncPostgresSaver`/`AsyncPostgresStore` with Postgres.

Nodes return `actions` (`session_update`, `function_output`, `respond`, `respond_after_playback`, `force_message`, `seed_history`, `handoff`, `end_after_playback`). The controller performs them in order. This keeps the graph independent of how audio travels, so the same graph serves previews and phone calls.

## A call, step by step

1. **Start.** A preview calls `POST /api/sessions`, which creates the conversation and mints an ephemeral token for direct mode. A phone call arrives as a signed webhook.
2. **Configure.** The controller registers the session, loads caller memory, and runs the graph with `start`. The entry agent's node emits `session.update` and the greeting: a natural greeting through `response.create` with a one-turn directive, or a verbatim `force_message`.
3. **Talk.** Transcripts (`conversation.item.input_audio_transcription.completed`, `response.output_audio_transcript.done`) become turns in the database and messages in the graph.
4. **Function calls.** These are collected until `response.done`. The graph executes them, the controller sends each `function_call_output`, waits until playback finishes, then sends `response.create`, as xAI's docs recommend to avoid overlapping audio.
5. **Handoff.** The graph emits the target agent's `session.update`, with its voice, tools, and a `## Handoff Context` section. The full transcript stays in the realtime conversation and in the graph thread.
6. **End.** `end_call`, a hangup, or the user closes the call. `post_call` writes the summary and contact memory.

## Roles and scaling

`ROLE=all` serves everything. In production, split the work into two services from the same image. `ROLE=app` serves the UI and API, behind an identity proxy. `ROLE=telephony` serves only `/webhooks/*` and holds the call sockets. Calls are pinned to the replica that received the webhook. Conversations, turns, and checkpoints live in the shared database. See [deploy/cloudrun.md](deploy/cloudrun.md).
