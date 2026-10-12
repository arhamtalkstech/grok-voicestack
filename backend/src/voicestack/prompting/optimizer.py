"""Prompt optimiser: rewrites an agent prompt so it follows the xAI prompting guide.

LangGraph subgraph: lint -> critique -> rewrite -> validate (-> rewrite, at most twice) -> END.
The critique and rewrite steps use grok-4.3 through langchain-xai with structured output; lint and
validate are deterministic so the result can be checked, not just trusted.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_xai import ChatXAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from voicestack.config import get_settings
from voicestack.prompting.compiler import SECTIONS, text_to_sections
from voicestack.prompting.linter import lint, mentioned_tools
from voicestack.runtime.specs import AgentSpec

GUIDE_PATH = Path(__file__).with_name("guide.md")
Mode = Literal["align", "fix_issue", "simplify"]
MAX_REWRITES = 3


@lru_cache
def load_guide() -> str:
    return GUIDE_PATH.read_text(encoding="utf-8")


class Issue(BaseModel):
    quote: str = Field(description="Short quote from the prompt that shows the problem")
    problem: str
    guide_rule: str = Field(description="The prompting-guide rule or section this relates to")


class Critique(BaseModel):
    issues: list[Issue]


class Change(BaseModel):
    section: Literal["role", "objective", "flow", "guardrails", "style", "critical"]
    change: str
    reason: str = Field(description="Which guide rule or observed issue motivates this change")


class RewrittenPrompt(BaseModel):
    role: str = Field(description="## Role & Persona body, second person")
    objective: str = Field(description="## Objective body, one or two sentences")
    flow: str = Field(description="## Conversation Flow body, starting from the caller's first response")
    guardrails: str = Field(description="## Guardrails & Escalation body")
    style: str = Field(description="## Voice & Communication Style body")
    critical: str = Field(default="", description="## CRITICAL INSTRUCTIONS body, empty if not needed")
    changes: list[Change]

    def sections(self) -> dict[str, str]:
        return {k: getattr(self, k).strip() for k in ("role", "objective", "flow", "guardrails", "style", "critical")}


class Variants(BaseModel):
    variants: list[RewrittenPrompt] = Field(min_length=1, max_length=3)


class OptimizerState(TypedDict, total=False):
    agent: dict[str, Any]
    mode: Mode
    issue: str
    transcripts: list[str]
    managed_mcp_tools: list[str]
    lint_before: dict[str, Any]
    critique: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    validation_errors: list[str]
    attempts: int
    results: list[dict[str, Any]]


FACT_PATTERNS = [
    r"https?://[^\s)>\]]+",
    r"[\w.+-]+@[\w-]+\.[\w.]+",
    r"\+?\d[\d\s().-]{6,}\d",
    r"[$€£]\s?\d[\d,.]*",
    r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm|AM|PM)\b",
]


def extract_facts(text: str) -> set[str]:
    facts: set[str] = set()
    for pattern in FACT_PATTERNS:
        for m in re.finditer(pattern, text):
            facts.add(m.group(0).strip().rstrip(".,;"))
    return facts


def _current_sections(agent: AgentSpec) -> dict[str, str]:
    if agent.prompt_mode == "raw":
        return text_to_sections(agent.raw_prompt)
    return dict(agent.prompt_sections)


def _current_text(agent: AgentSpec) -> str:
    if agent.prompt_mode == "raw":
        return agent.raw_prompt
    return "\n\n".join(
        f"## {t}\n{agent.prompt_sections.get(k, '')}" for k, t in [*SECTIONS, ("critical", "CRITICAL INSTRUCTIONS")]
    )


def _context_block(agent: AgentSpec, managed: list[str]) -> str:
    tools = sorted(agent.function_tool_names(managed_mcp_tools=managed) | agent.server_tool_names())
    lines = [
        f"Agent name: {agent.name}",
        f"Attached tools (the ONLY tools the prompt may mention): {', '.join(tools) or 'none'}",
    ]
    for t in agent.tools:
        lines.append(f"- {t.name}: {t.description}" + (" (must confirm before calling)" if t.requires_confirmation else ""))
    for e in agent.edges:
        lines.append(f"- {e.tool_name}: hands the caller to {e.target_name}. {e.description}")
    if agent.transfers:
        lines.append("- transfer_call destinations: " + ", ".join(t.name for t in agent.transfers))
    if agent.greeting:
        lines.append(f"Greeting (a separate field, spoken first; do NOT repeat it in the flow): {agent.greeting}")
    if agent.key_facts:
        lines.append(f"Business facts (a separate field appended verbatim; do not duplicate):\n{agent.key_facts}")
    if agent.language_hint:
        lines.append(f"Language hint: {agent.language_hint}")
    lines.append(
        "Voice Stack appends one line per attached transfer, knowledge, and end_call tool to the Conversation "
        "Flow automatically. You may reference those tools for escalation triggers, but do not list them all again."
    )
    return "\n".join(lines)


def _model(api_key: str, effort: str = "low") -> ChatXAI:
    settings = get_settings()
    return ChatXAI(model=settings.text_model, api_key=api_key, reasoning_effort=effort, timeout=600, max_retries=2)


def build_optimizer(api_key: str):
    async def lint_node(state: OptimizerState) -> OptimizerState:
        agent = AgentSpec.model_validate(state["agent"])
        return {"lint_before": lint(agent, managed_mcp_tools=state.get("managed_mcp_tools")).dict(), "attempts": 0}

    async def critique_node(state: OptimizerState) -> OptimizerState:
        agent = AgentSpec.model_validate(state["agent"])
        lint_lines = "\n".join(f"- [{f['severity']}] {f['message']}" for f in state["lint_before"]["findings"]) or "- none"
        system = (
            "## Role & Objective\nYou are a Prompt-Critique Expert for realtime voice agents. Examine the supplied "
            "system prompt and surface weaknesses measured against the xAI speech-to-speech prompting guide below.\n\n"
            "## Instructions\nIdentify ambiguity, missing definitions, conflicting, incomplete, or vague instructions, "
            "unstated assumptions, and departures from the guide's structure and rules.\nDo NOT invent new tools or "
            "external information. Do NOT list issues you are unsure about.\n\n"
            f"## Prompting guide\n{load_guide()}"
        )
        human = (
            f"## Agent context\n{_context_block(agent, state.get('managed_mcp_tools', []))}\n\n"
            f"## Automated lint findings\n{lint_lines}\n\n"
            + (f"## Observed issue\n{state['issue']}\n\n" if state.get("issue") else "")
            + (
                "## Example transcripts\n" + "\n---\n".join(state.get("transcripts", [])[:3]) + "\n\n"
                if state.get("transcripts")
                else ""
            )
            + f"## Current prompt\n{_current_text(agent)}"
        )
        result = (
            await _model(api_key)
            .with_structured_output(Critique, method="json_schema")
            .ainvoke([SystemMessage(system), HumanMessage(human)])
        )
        return {"critique": [i.model_dump() for i in result.issues]}

    async def rewrite_node(state: OptimizerState) -> OptimizerState:
        agent = AgentSpec.model_validate(state["agent"])
        mode = state.get("mode", "align")
        rules = [
            "Write in second person, using exactly these sections: Role & Persona, Objective, Conversation Flow, "
            "Guardrails & Escalation, Voice & Communication Style, and CRITICAL INSTRUCTIONS only if truly needed.",
            "Keep every business fact, URL, phone number, price, time, and tool name from the current prompt verbatim.",
            "Mention only attached tools, by their exact names in backticks. Never script steps for capabilities the agent lacks.",
            "Do not write the greeting into the Conversation Flow; it is a separate field.",
            "Rules about how the voice sounds (pace, pitch, accent) do not belong in the prompt; reframe them as rules about wording or drop them.",
            "Prefer short bullets. Be precise. Avoid conflicting instructions.",
            "Return section bodies without the '## ' header lines.",
            "List every change you made with the guide rule or observed issue that motivates it.",
        ]
        if mode == "simplify":
            rules.append("Make the prompt much shorter: strip workaround prompting and redundancy while keeping behavior.")
        if mode == "fix_issue":
            rules.append("Tighten constraints to remove the observed failure mode. Return 2 or 3 distinct variants.")
        feedback = state.get("validation_errors") or []
        system = (
            "You rewrite system prompts for xAI realtime voice agents so they follow the xAI prompting guide.\n\n"
            "## Rules\n" + "\n".join(f"- {r}" for r in rules) + f"\n\n## Prompting guide\n{load_guide()}"
        )
        critique = (
            "\n".join(f"- “{i['quote']}”: {i['problem']} ({i['guide_rule']})" for i in state.get("critique", [])) or "- none"
        )
        human = (
            f"## Agent context\n{_context_block(agent, state.get('managed_mcp_tools', []))}\n\n"
            f"## Critique\n{critique}\n\n"
            + (f"## Observed issue\n{state['issue']}\n\n" if state.get("issue") else "")
            + (
                "## Problems with your previous attempt (fix all of them)\n" + "\n".join(f"- {e}" for e in feedback) + "\n\n"
                if feedback
                else ""
            )
            + f"## Current prompt\n{_current_text(agent)}"
        )
        llm = _model(api_key)
        if mode == "fix_issue":
            out = await llm.with_structured_output(Variants, method="json_schema").ainvoke(
                [SystemMessage(system), HumanMessage(human)]
            )
            candidates = [v.model_dump() for v in out.variants]
        else:
            out = await llm.with_structured_output(RewrittenPrompt, method="json_schema").ainvoke(
                [SystemMessage(system), HumanMessage(human)]
            )
            candidates = [out.model_dump()]
        return {"candidates": candidates, "attempts": state.get("attempts", 0) + 1}

    async def validate_node(state: OptimizerState) -> OptimizerState:
        agent = AgentSpec.model_validate(state["agent"])
        managed = state.get("managed_mcp_tools", [])
        attached = agent.function_tool_names(managed_mcp_tools=managed) | agent.server_tool_names()
        original_facts = extract_facts(_current_text(agent))
        results, errors = [], []
        for idx, cand in enumerate(state["candidates"]):
            rewritten = RewrittenPrompt.model_validate(cand)
            sections = rewritten.sections()
            text = "\n".join(sections.values())
            missing = sorted(f for f in original_facts if f not in text)
            unknown = sorted(mentioned_tools(text) - attached)
            candidate_agent = agent.model_copy(update={"prompt_mode": "sections", "prompt_sections": sections, "raw_prompt": ""})
            after = lint(candidate_agent, managed_mcp_tools=managed).dict()
            cand_errors = []
            if missing:
                cand_errors.append(
                    "These facts from the original prompt are missing; include them verbatim: " + ", ".join(missing)
                )
            if unknown:
                cand_errors.append("These tools are not attached and must not be mentioned: " + ", ".join(unknown))
            blocking = [f for f in after["findings"] if f["severity"] == "error"]
            cand_errors += [f["message"] for f in blocking]
            errors += [f"Variant {idx + 1}: {e}" for e in cand_errors] if len(state["candidates"]) > 1 else cand_errors
            results.append(
                {
                    "sections": sections,
                    "changes": [c.model_dump() for c in rewritten.changes],
                    "lint_after": after,
                    "warnings": cand_errors,
                }
            )
        return {"results": results, "validation_errors": errors}

    def after_validate(state: OptimizerState) -> str:
        if state.get("validation_errors") and state.get("attempts", 0) < MAX_REWRITES:
            return "rewrite"
        return END

    graph = StateGraph(OptimizerState)
    graph.add_node("lint", lint_node)
    graph.add_node("critique", critique_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("validate", validate_node)
    graph.add_edge(START, "lint")
    graph.add_edge("lint", "critique")
    graph.add_edge("critique", "rewrite")
    graph.add_edge("rewrite", "validate")
    graph.add_conditional_edges("validate", after_validate, ["rewrite", END])
    return graph.compile()


async def optimize_prompt(
    api_key: str,
    agent: AgentSpec,
    *,
    mode: Mode = "align",
    issue: str = "",
    transcripts: list[str] | None = None,
    managed_mcp_tools: list[str] | None = None,
) -> dict[str, Any]:
    graph = build_optimizer(api_key)
    final = await graph.ainvoke(
        {
            "agent": agent.model_dump(mode="json"),
            "mode": mode,
            "issue": issue,
            "transcripts": transcripts or [],
            "managed_mcp_tools": managed_mcp_tools or [],
        }
    )
    return {
        "mode": mode,
        "before": {"sections": _current_sections(agent), "lint": final["lint_before"]},
        "critique": final.get("critique", []),
        "variants": final.get("results", []),
        "attempts": final.get("attempts", 0),
        "guide_source": load_guide().splitlines()[0],
    }
