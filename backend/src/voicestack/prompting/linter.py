"""Deterministic prompt checks derived from the xAI speech-to-speech prompting guide.

Each rule cites the guide statement it enforces, so the UI can explain every finding.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Literal

from voicestack.prompting.compiler import SECTION_TITLES, SECTIONS, section_key_for_title, text_to_sections
from voicestack.runtime.specs import AgentSpec

Severity = Literal["error", "warning", "info"]
PENALTY = {"error": 15, "warning": 7, "info": 2}

KNOWN_TOOL_WORDS = {
    "web_search",
    "x_search",
    "file_search",
    "end_call",
    "transfer_call",
    "api_request",
    "search_knowledge",
}
TOOL_TOKEN = re.compile(r"`([a-z][a-z0-9_]{2,63})`|\b([a-z]+(?:_[a-z0-9]+)+)\b")
AUDIO_PATTERNS = [
    r"\bspeak (?:more )?(?:slowly|quickly|faster|slower)\b",
    r"\b(?:speaking|speech) (?:rate|speed|pace)\b",
    r"\bpitch\b",
    r"\bwhisper",
    r"\bvolume\b",
    r"\bbackground (?:noise|music|sounds?)\b",
    r"\bsound (?:like|more|less)\b",
    r"\b(?:british|american|australian|indian|southern) accent\b",
    r"\bphonetic",
    r"\b(?:laugh|sigh|giggle)s?\b",
]
SCRIPTED_OPENER = re.compile(r"\b(?:open|start|begin|greet)\w*[^.\n]{0,60}[\"“]", re.IGNORECASE)
THIRD_PERSON = re.compile(r"^\s*(?:the (?:assistant|agent|bot|ai)|this (?:assistant|agent|bot))\b", re.IGNORECASE | re.MULTILINE)
COLLECTS_IDS = re.compile(
    r"\b(?:account|order|phone|policy|booking|confirmation|reference|card|member) (?:number|id|code)s?\b", re.IGNORECASE
)
READS_CHARS = re.compile(
    r"(?:each (?:character|digit) separately|digit[- ]by[- ]digit|separated by hyphens|one (?:character|digit) at a time)",
    re.IGNORECASE,
)
SAFETY = re.compile(r"(?:self-harm|suicid|emergency|crisis)", re.IGNORECASE)
SPOKEN_ONLY = re.compile(r"(?:no markdown|spoken word|no bullet|no emojis?|plain speech)", re.IGNORECASE)
MENTIONS_TRANSFER = re.compile(r"\btransfer(?:ring)?\b|\bhand (?:the caller|you|them) (?:off|over)\b", re.IGNORECASE)


@dataclass
class Finding:
    rule: str
    severity: Severity
    message: str
    section: str | None = None
    quote: str | None = None
    guide: str | None = None

    def dict(self) -> dict:
        return asdict(self)


@dataclass
class LintResult:
    findings: list[Finding]
    score: int

    def dict(self) -> dict:
        return {"score": self.score, "findings": [f.dict() for f in self.findings]}


def _sections_for(agent: AgentSpec) -> dict[str, str]:
    if agent.prompt_mode == "raw":
        return text_to_sections(agent.raw_prompt)
    return {k: v for k, v in agent.prompt_sections.items() if v and v.strip()}


def _snippet(text: str, match: re.Match[str]) -> str:
    start, end = max(0, match.start() - 30), min(len(text), match.end() + 30)
    return text[start:end].replace("\n", " ").strip()


def mentioned_tools(text: str) -> set[str]:
    found: set[str] = set()
    for m in TOOL_TOKEN.finditer(text):
        token = m.group(1) or m.group(2)
        if m.group(1) or token in KNOWN_TOOL_WORDS or token.startswith("transfer_to_"):
            found.add(token)
    return found


def lint(agent: AgentSpec, *, managed_mcp_tools: list[str] | None = None) -> LintResult:
    findings: list[Finding] = []
    sections = _sections_for(agent)
    full_text = agent.raw_prompt if agent.prompt_mode == "raw" else "\n".join(sections.values())

    if not full_text.strip():
        findings.append(Finding("empty_prompt", "error", "The prompt is empty.", guide="Recommended prompt structure"))
        return LintResult(findings, 0)

    for key, title in SECTIONS:
        if not sections.get(key):
            findings.append(
                Finding(
                    "missing_section",
                    "warning" if key != "role" else "error",
                    f"Add a “{title}” section. The guide recommends all five sections in a fixed order.",
                    section=key,
                    guide="Recommended prompt structure",
                )
            )

    if agent.prompt_mode == "raw":
        headers = re.findall(r"^(#{1,6})\s+(.+?)\s*$", agent.raw_prompt, re.MULTILINE)
        if any(h[0] == "#" for h in headers):
            findings.append(
                Finding(
                    "h1_headers", "warning", "Use `##` (H2) headers for sections, not `#`.", guide="Second person, H2 headers"
                )
            )
        order = [k for k, _ in SECTIONS]
        keys = [k for k in (section_key_for_title(h[1]) for h in headers) if k in order]
        if keys != sorted(keys, key=order.index):
            findings.append(
                Finding(
                    "section_order",
                    "warning",
                    "Sections are out of order. Use: " + " → ".join(SECTION_TITLES[k] for k in order) + ".",
                    guide="Recommended prompt structure",
                )
            )

    role = sections.get("role", "")
    if role and not re.search(r"\byou\b", role, re.IGNORECASE):
        findings.append(
            Finding(
                "second_person",
                "warning",
                "Write the persona in second person (“You are…”).",
                section="role",
                guide="Second person, H2 headers",
            )
        )
    if m := THIRD_PERSON.search(full_text):
        findings.append(
            Finding(
                "third_person",
                "warning",
                "Describe the agent as “you”, not in third person.",
                quote=_snippet(full_text, m),
                guide="Second person, H2 headers",
            )
        )

    flow = sections.get("flow", "")
    if m := SCRIPTED_OPENER.search(flow):
        findings.append(
            Finding(
                "greeting_in_flow",
                "warning",
                "Move the scripted opening line into the Greeting field. The flow should start from the caller's first response.",
                section="flow",
                quote=_snippet(flow, m),
                guide="The greeting is separate",
            )
        )

    attached = agent.function_tool_names(managed_mcp_tools=managed_mcp_tools) | agent.server_tool_names()
    for tool in sorted(mentioned_tools(full_text) - attached):
        findings.append(
            Finding(
                "unknown_tool",
                "error",
                f"The prompt mentions `{tool}`, but no tool with that name is attached.",
                quote=tool,
                guide="Only mention tools that exist in the tool definition",
            )
        )

    if MENTIONS_TRANSFER.search(full_text) and not (agent.edges or agent.transfers):
        findings.append(
            Finding(
                "transfer_without_tool",
                "error",
                "The prompt talks about transferring, but this agent has no handoff edge or transfer destination.",
                guide="Never script steps for capabilities the agent does not have",
            )
        )

    for pattern in AUDIO_PATTERNS:
        if m := re.search(pattern, full_text, re.IGNORECASE):
            findings.append(
                Finding(
                    "audio_instruction",
                    "warning",
                    "The prompt controls words, not how the voice sounds. Use the speed setting or pronunciation map instead, or reframe this as a rule about wording.",
                    quote=_snippet(full_text, m),
                    guide="The prompt controls what the agent says, not the sound of the voice",
                )
            )
            break

    guardrails = sections.get("guardrails", "")
    if guardrails and not SAFETY.search(guardrails):
        findings.append(
            Finding(
                "safety_path",
                "info",
                "Add the safety path: if the caller mentions self-harm, abuse, or an emergency, respond with empathy, point them to emergency services, and escalate.",
                section="guardrails",
                guide="Guardrails and escalation",
            )
        )

    if COLLECTS_IDS.search(full_text) and not READS_CHARS.search(full_text):
        findings.append(
            Finding(
                "read_codes",
                "info",
                "The agent handles numbers or codes. Add a rule to read them one character at a time, separated by hyphens, and confirm.",
                section="style",
                guide="Reading numbers and codes",
            )
        )

    style = sections.get("style", "")
    if style and not SPOKEN_ONLY.search(style):
        findings.append(
            Finding(
                "spoken_only",
                "info",
                "Say the output is spoken word only: no markdown, lists, or emojis.",
                section="style",
                guide="Voice and communication style",
            )
        )

    if agent.language_hint and not re.search(r"\brespond only in\b|\bonly (?:speak|respond) in\b", full_text, re.IGNORECASE):
        findings.append(
            Finding(
                "language_lock",
                "info",
                f"A language hint ({agent.language_hint}) is set. If the agent must stay in one language, add a language lock to the style section.",
                section="style",
                guide="Language lock",
            )
        )

    critical = sections.get("critical", "")
    if critical and len([ln for ln in critical.splitlines() if ln.strip()]) > 6:
        findings.append(
            Finding(
                "critical_too_long",
                "warning",
                "Keep CRITICAL INSTRUCTIONS short. Every rule added there dilutes the others.",
                section="critical",
                guide="Critical instructions",
            )
        )

    objective = sections.get("objective", "")
    if objective and (len(re.findall(r"[.!?](?:\s|$)", objective)) > 3 or objective.count("\n- ") > 2):
        findings.append(
            Finding(
                "objective_too_long",
                "info",
                "Keep the objective to one or two sentences. Move details into Conversation Flow or Guardrails.",
                section="objective",
                guide="Objective",
            )
        )

    if len(agent.key_facts) > 2000:
        findings.append(
            Finding(
                "facts_too_long",
                "info",
                "Business facts are long. Move document-sized material into a knowledge base.",
                guide="Facts and source of truth",
            )
        )

    score = max(0, 100 - sum(PENALTY[f.severity] for f in findings))
    return LintResult(findings, score)
