"""Turns an agent's prompt fields into the `instructions` string for session.update.

Section names and order follow the xAI speech-to-speech prompting guide. Lines about transfers,
knowledge search, and ending the call are generated from the tools that are actually attached, so
the prompt only ever names tools that exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from voicestack.runtime.specs import AgentSpec

SECTIONS: list[tuple[str, str]] = [
    ("role", "Role & Persona"),
    ("objective", "Objective"),
    ("flow", "Conversation Flow"),
    ("guardrails", "Guardrails & Escalation"),
    ("style", "Voice & Communication Style"),
]
CRITICAL = ("critical", "CRITICAL INSTRUCTIONS")
SECTION_TITLES = {k: v for k, v in [*SECTIONS, CRITICAL]}


@dataclass
class HandoffContext:
    from_agent: str
    reason: str = ""
    summary: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    greeting: str = ""


def _section(title: str, body: str) -> str:
    return f"## {title}\n{body.strip()}"


def generated_tool_guidance(agent: AgentSpec) -> list[str]:
    lines: list[str] = []
    for edge in agent.edges:
        when = edge.description.strip() or f"the caller needs {edge.target_name}"
        lines.append(f"- Call `{edge.tool_name}` to hand the conversation to {edge.target_name} when {when.rstrip('.')}.")
    if agent.transfers:
        names = "; ".join(f"{t.name}" + (f" ({t.description})" if t.description else "") for t in agent.transfers)
        lines.append(f"- Call `transfer_call` to connect the caller to a person. Destinations: {names}.")
    local_kbs = [k for k in agent.knowledge if k.mode == "local"]
    if local_kbs:
        topics = ", ".join(k.name for k in local_kbs)
        lines.append(
            f"- Call `search_knowledge` to answer questions about {topics}. Answer only from the results; "
            "if they do not cover the question, say you do not know."
        )
    collections = [k for k in agent.knowledge if k.mode == "collections" and k.collection_id]
    if collections:
        topics = ", ".join(k.name for k in collections)
        lines.append(
            f"- Call `file_search` to answer questions from the knowledge base ({topics}). Always search it before saying "
            "you do not know. Answer only from the results; if they do not cover the question, say you do not know."
        )
    searches = [k for k in ("web_search", "x_search") if (agent.builtin_tools.get(k) or {}).get("enabled")]
    if searches:
        names = " or ".join(f"`{k}`" for k in searches)
        lines.append(
            f'- Before using {names}, say only a short line such as "Let me check." Never describe results before you have them.'
        )
    if agent.allow_end_call:
        lines.append(
            "- Call `end_call` only after the caller says goodbye or confirms they need nothing else. "
            "Never end the call right after answering a question; ask if there is anything else and wait for the reply."
        )
    return lines


def compile_instructions(
    agent: AgentSpec,
    *,
    handoff: HandoffContext | None = None,
    caller_context: str | None = None,
) -> str:
    guidance = generated_tool_guidance(agent)
    parts: list[str] = []

    if agent.prompt_mode == "raw":
        if agent.raw_prompt.strip():
            parts.append(agent.raw_prompt.strip())
        if agent.key_facts.strip():
            parts.append(_section("Business Facts", agent.key_facts))
        if guidance:
            parts.append(_section("Tools and Transfers", "\n".join(guidance)))
        critical = ""
    else:
        s = agent.prompt_sections
        for key, title in SECTIONS:
            body = (s.get(key) or "").strip()
            if key == "flow" and guidance:
                body = (body + "\n\n" if body else "") + "Tools and transfers:\n" + "\n".join(guidance)
            if body:
                parts.append(_section(title, body))
            if key == "role" and agent.key_facts.strip():
                parts.append(_section("Business Facts", agent.key_facts))
        critical = (s.get("critical") or "").strip()

    if caller_context:
        parts.append(_section("Caller Context", caller_context))
    if handoff:
        lines = [
            f"You are taking over this conversation from {handoff.from_agent}. The caller has already been "
            "greeted, so do not greet them again or ask for details they already gave.",
        ]
        if handoff.reason:
            lines.append(f"- Reason for the handoff: {handoff.reason}")
        if handoff.summary:
            lines.append(f"- Summary so far: {handoff.summary}")
        for k, v in handoff.fields.items():
            if v not in (None, ""):
                lines.append(f"- {k}: {v}")
        parts.append(_section("Handoff Context", "\n".join(lines)))
    if critical:
        parts.append(_section(CRITICAL[1], critical))
    return "\n\n".join(parts).strip()


def sections_to_text(sections: dict[str, str]) -> str:
    out = []
    for key, title in [*SECTIONS, CRITICAL]:
        body = (sections.get(key) or "").strip()
        if body:
            out.append(_section(title, body))
    return "\n\n".join(out)


_TITLE_LOOKUP = {v.lower(): k for k, v in SECTION_TITLES.items()}
_TITLE_ALIASES = {
    "role": "role",
    "persona": "role",
    "role and persona": "role",
    "role & objective": "role",
    "objective": "objective",
    "goal": "objective",
    "conversation flow": "flow",
    "flow": "flow",
    "instructions": "flow",
    "guardrails": "guardrails",
    "guardrails and escalation": "guardrails",
    "escalation": "guardrails",
    "voice and communication style": "style",
    "style": "style",
    "communication style": "style",
    "tone": "style",
    "critical instructions": "critical",
    "critical": "critical",
}


def section_key_for_title(title: str) -> str | None:
    t = title.strip().lower()
    return _TITLE_LOOKUP.get(t) or _TITLE_ALIASES.get(t)


def text_to_sections(text: str) -> dict[str, str]:
    """Best-effort split of a raw prompt into guide sections by its `## ` headers."""
    sections: dict[str, list[str]] = {}
    current = "role"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            key = section_key_for_title(stripped.lstrip("#"))
            if key:
                current = key
                continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}
