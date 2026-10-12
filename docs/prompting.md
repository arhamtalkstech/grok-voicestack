# Prompting and the optimiser

Voice Stack bundles xAI's speech-to-speech prompting guide at `backend/src/voicestack/prompting/guide.md`, with its source URL and fetch date. Refresh it with:

```bash
uv run voicestack guide refresh
```

## The prompt check (linter)

`prompting/linter.py` runs on every save. Each rule cites the guide statement it enforces:

| Rule | Severity | Guide basis |
|---|---|---|
| Empty prompt / missing Role & Persona | error | Recommended prompt structure |
| Tool named in the prompt but not attached | error | Only mention tools that exist in the tool definition |
| Talks about transferring without a handoff or transfer line | error | Never script steps for capabilities the agent does not have |
| Missing section, `#` headers, sections out of order | warning | Recommended prompt structure |
| Not second person / third-person description | warning | Second person, H2 headers |
| Scripted opening line inside Conversation Flow | warning | The greeting is separate |
| Instructions about pace, pitch, accent, sounds | warning | The prompt controls what the agent says, not the sound of the voice |
| CRITICAL INSTRUCTIONS longer than six lines | warning | Critical instructions |
| No safety path in Guardrails | info | Guardrails and escalation |
| Handles IDs or numbers without a character-by-character rule | info | Reading numbers and codes |
| Style does not say spoken word only | info | Voice and communication style |
| Language hint set but no language lock | info | Language lock |
| Objective longer than two sentences; facts longer than 2,000 characters | info | Objective; Facts and source of truth |

The score starts at 100. Each error subtracts 15, each warning 7, each info 2.

## The optimiser

**Optimise with guide** on the Prompt tab (or `voicestack prompt optimize <slug>`) runs a LangGraph subgraph in `prompting/optimizer.py`:

1. **lint:** the deterministic checks above.
2. **critique:** `grok-4.3` with the guide's "Instruction quality check" meta-prompt and the full guide in context. It returns issues with quoted snippets.
3. **rewrite:** `grok-4.3` with structured output. It returns the six sections and a changelog that ties every change to a guide rule or an observed issue. It is told the agent's real tools, handoffs, greeting, and facts.
4. **validate:** re-lints the result. It checks that every URL, email, phone number, price, and time from the original survives verbatim, and that no unattached tool is mentioned. On failure it loops back to rewrite with the problems listed, at most twice.

Modes:

- **Align with guide:** restructure and tighten.
- **Fix an issue:** describe a failure you see in calls ("reads order numbers too fast"). Returns 2–3 variants. You can attach up to three transcripts through the API (`conversation_ids`).
- **Simplify:** shorten a long or migrated prompt, as the guide recommends for `grok-voice-think-fast-2.0`.

The result shows a word-level diff per section, the reason for each change, and the lint score before and after. Accept sections one at a time or all at once. Accepted sections become your draft, so a running preview picks them up immediately.

API: `POST /api/agents/{id}/prompt/optimize` with `{"mode": "align" | "fix_issue" | "simplify", "issue": "", "conversation_ids": []}`. It uses the request's key (session-only key, workspace key, or `XAI_API_KEY`).
