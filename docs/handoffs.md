# Handoffs

A handoff moves the caller from one agent to another inside the same call. Create one by dragging between agent cards on the Landscape, or from an agent's **Handoffs** tab.

## What the model sees

Each handoff edge A → B gives agent A a function tool named `transfer_to_<b_slug>`:

```json
{
  "type": "function",
  "name": "transfer_to_voice_specialist",
  "description": "Hand the conversation to Voice Specialist. Use when the caller is building a voice agent…",
  "parameters": {
    "type": "object",
    "properties": {
      "reason":   {"type": "string"},
      "summary":  {"type": "string"},
      "use_case": {"type": "string", "description": "What the voice agent should do"},
      "channel":  {"type": "string", "description": "web or phone, if known"}
    },
    "required": ["reason", "summary", "use_case"]
  }
}
```

`reason` and `summary` are always present. The rest is the edge's **context contract**: the typed fields you define, each optional or required. The edge description also becomes a line in A's Conversation Flow, so the prompt and the tool agree.

## What happens on a handoff

1. The LangGraph node for A validates the call. If a required field is missing, the tool returns an error that asks the agent to collect it first, and the call stays with A. Only one handoff per turn is accepted.
2. A `function_call_output` closes the call: `{"ok": true, "transferred_to": "Voice Specialist"}`.
3. The node returns `Command(goto="voice-specialist")`. B's node emits a `session.update` with B's instructions, tools, speed, transcription hints, pronunciation map, and voice (depending on the voice policy). B's instructions gain a section:

   ```
   ## Handoff Context
   You are taking over this conversation from Front Desk. The caller has already been greeted…
   - Reason for the handoff: voice agent
   - Summary so far: Building a phone agent for a dental clinic
   - use_case: clinic phone line
   ```

4. After A's handoff line finishes playing, B responds: either the edge's "first line after handoff" or a short self-introduction.

The full transcript stays in the realtime conversation, so B hears everything A heard. Collected fields merge into the conversation's `context` and stay available to every later agent. They appear in the live dock's **State** tab and on the conversation page.

## Voice policy

Each edge either **switches** to B's voice or **keeps** the current one. The global `HANDOFF_VOICE_MODE=keep` keeps the first voice for every handoff once audio has played.

xAI's docs do not say whether `voice` can change mid-session; OpenAI's realtime API locks it after the first audio. `backend/spikes/phase0.py` measures it from the audio itself. On 2026-10-12, median pitch went from about 170 Hz (`eve`) to about 107 Hz (`rex`) after a mid-session `session.update`, so the voice does switch. That is why `HANDOFF_VOICE_MODE=in_session` is the default.

## Transfers to people

Transfer lines (Integrations → Transfer lines) are `tel:+E.164` or `sip:user@host` destinations. Attaching any to an agent adds a `transfer_call` tool:

- **On phone calls:** it waits for the agent's line to finish, then calls `POST /v1/realtime/calls/{call_id}/refer`. The call blocks until the destination answers. On success (`200`) the session ends with reason `transferred`. On failure (`502`/`504`) the error is returned to the model, so the agent can tell the caller.
- **In previews:** the transfer is simulated and labelled in the transcript.
