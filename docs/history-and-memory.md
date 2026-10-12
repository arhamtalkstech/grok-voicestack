# History and memory

## One thread per conversation, across agents

Every preview and phone call is one conversation, however many agents it passes through. Four things are recorded:

| Record | Table / store | What is in it |
|---|---|---|
| **Conversation** | `conversations` | Channel (web or SIP), caller and dialed numbers, contact, agents visited in order, xAI conversation id or SIP `call_id`, start and end time, end reason, time to first audio per turn, and the post-call summary, disposition, and extracted fields from `grok-4.3`. |
| **Turns** | `turns` | In order, each tagged with the agent that handled it: caller transcripts (typed or spoken), agent transcripts, verbatim lines (`force_message`), keypad digits, handoffs (from, to, reason, summary, collected fields), and **tool calls**. Voice Stack's own tools store name, arguments, output, success, and latency. Tools xAI ran itself (web search, collections search, hosted MCP) are marked "ran at xAI". |
| **Realtime event log** | `conversation_events` | Every event from xAI and every event Voice Stack sent back, with direction and timestamp. Audio and transcript deltas are excluded; the final transcripts are in `turns`. Secrets inside `session.update` are redacted. In direct-mode previews, the log has the events the browser forwards (see [known-gaps.md](known-gaps.md)). Turn it off with `RECORD_EVENTS=false`. |
| **Graph state** | LangGraph checkpoint (thread = conversation id) | LangChain messages (including tool calls and results), `active_agent`, collected `context`, and `handoffs`. Returned by `GET /api/conversations/{id}/state`. |

**Audio is not recorded.** The Conversations page shows the swimlanes, tool cards, and summary; the right rail shows the graph state, and an expandable **Realtime event log** shows the stored events. APIs: `GET /api/conversations/{id}`, `/state`, and `/events`.

## Memory across conversations

When a caller is identified, they get a contact record. On phone calls the identity is the `From` number; in previews it is the **Caller identity** field. Memory works like this:

1. After the call, `post_call` asks `grok-4.3` for a summary and stable caller facts (name, account, preferences).
2. The facts and the last five summaries are written to the LangGraph store under `("contacts", <contact_id>)` with key `profile`.
3. The next time the same identity calls, the entry agent's instructions gain a `## Caller Context` section. It holds the known details and recent summaries, with an instruction to use them only when relevant.

To try it, start a preview with caller identity `+14155550100` and tell the agent your name. End the call, wait for the summary, then start another call with the same identity.

## Continuing a conversation

**Continue in preview** on a conversation page starts a new conversation linked to the old one (`resumed_from_id`):

- The graph thread starts from the old thread's messages, context, and active agent.
- The realtime session is seeded with the prior transcript through `conversation.item.create` (user and assistant text items), and the agent welcomes the caller back.

xAI also offers native session resumption (`resumption.enabled` plus `?conversation_id=`), which replays cached turns for up to 30 minutes of inactivity. In our live check (`docs/xai-api-notes.md`), reconnecting reattached to the same conversation but replayed only the assistant's turns, not a typed user message. That is why Voice Stack resumes by seeding the full transcript itself, which the same check confirmed works.
