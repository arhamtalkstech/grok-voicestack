# Building agents

An agent is a prompt plus a voice, a speed, tools, knowledge, and handoffs. Open **Agents** to edit one. Changes save automatically and apply to any live preview immediately.

## Prompt

Prompts use the section structure from xAI's speech-to-speech prompting guide, in this order:

| Section | What goes in it |
|---|---|
| Role & Persona | Who the agent is, in second person ("You are…"). |
| Objective | What done looks like, in one or two sentences. |
| Conversation Flow | How the call goes, starting from the caller's first response. Name only tools the agent has. |
| Guardrails & Escalation | Scope, refusals, escalation triggers, and the safety path. |
| Voice & Communication Style | How replies are worded for speech: length, tone, language, reading numbers. |
| CRITICAL INSTRUCTIONS | Optional. Absolute rules only. Keep it short. |

**Single prompt** mode accepts a free-form prompt. Use `##` headers so the checks can read the sections.

**Business facts** (hours, prices, URLs) are inserted verbatim after the persona. Put long documents in a knowledge base instead.

**Greeting** is separate from the prompt:

- *Agent words it:* the agent opens with this meaning in its own words.
- *Say exactly:* spoken verbatim through `force_message`. Good for disclosures. It can be made non-interruptible.
- *Wait for caller:* no greeting.

The **prompt check** on the right lints the prompt against the guide: missing or out-of-order sections, tools named in the prompt but not attached, instructions about how the voice sounds, a missing safety path, and more. See [prompting.md](prompting.md) for the optimiser.

## Voice

- **Built-in voices** load live from `GET /v1/tts/voices`. Play a sample at the current speed before choosing.
- **Speed** ranges from 0.7× to 1.5× and is sent as `audio.output.speed`.
- **Custom voices** are listed from `GET /v1/custom-voices`. Paste a voice ID created in the xAI console, or upload a reference clip. Uploading requires an Enterprise plan and a consent confirmation.

> Custom voices are available only in the United States, excluding Illinois. Teams in other countries need to contact the xAI sales team.

## Behavior

| Setting | Session field |
|---|---|
| Reasoning (high / none) | `reasoning.effort` |
| Language hint | `audio.input.transcription.language_hint` |
| Key terms (up to 100) | `audio.input.transcription.keyterms` |
| Pronunciation map | `replace` (changes the audio, not the transcript) |
| Check in after silence | `turn_detection.idle_timeout_ms` |
| Can end the call | adds the `end_call` tool |

## Tools, knowledge, handoffs

- **Tools tab:** web and X search (run at xAI), your HTTP and plugin tools, MCP servers, and transfer lines. See [tools-and-mcp.md](tools-and-mcp.md).
- **Knowledge tab:** attach knowledge bases. See [knowledge.md](knowledge.md).
- **Handoffs tab:** connect to other agents and define the context each handoff carries. See [handoffs.md](handoffs.md).

## Drafts and publishing

Previews always use your latest edits. Phone numbers answer with the **published** version: press **Publish** to snapshot the agent, including its resolved tools and handoffs. The badge shows when a draft has unpublished edits. A number can be set to use drafts instead.

## Seeing exactly what the model gets

**What the model receives** in the right rail shows the compiled instructions and the full `session.update`. The live dock's **State** tab shows the `session.update` actually sent during a call.
