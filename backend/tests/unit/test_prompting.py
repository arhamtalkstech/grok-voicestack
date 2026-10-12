from voicestack.prompting.compiler import HandoffContext, compile_instructions, text_to_sections
from voicestack.prompting.linter import lint
from voicestack.runtime.specs import AgentSpec, EdgeSpec, TransferSpec

GOOD = {
    "role": "You are a calm support agent for Acme Internet.",
    "objective": "Resolve billing questions accurately.",
    "flow": "Ask for the account email, then answer from the facts.",
    "guardrails": "Stay in scope. If the caller mentions self-harm or an emergency, respond with empathy and point them to emergency services.",
    "style": "Spoken word only: no markdown. One or two short sentences.",
}


def agent(**kw) -> AgentSpec:
    base = {"id": "agt_1", "slug": "billing", "name": "Billing", "prompt_sections": dict(GOOD)}
    base.update(kw)
    return AgentSpec(**base)


def rules(spec: AgentSpec) -> set[str]:
    return {f.rule for f in lint(spec).findings}


def test_clean_prompt_scores_100():
    result = lint(agent())
    assert result.score == 100, result.findings


def test_unknown_tool_is_an_error():
    spec = agent(prompt_sections={**GOOD, "flow": "Call `lookup_account` with the email."})
    found = [f for f in lint(spec).findings if f.rule == "unknown_tool"]
    assert found and found[0].severity == "error" and "lookup_account" in found[0].message


def test_attached_tool_mention_is_fine():
    edge = EdgeSpec(id="e", source_slug="billing", target_slug="tech", target_name="Tech")
    spec = agent(edges=[edge], prompt_sections={**GOOD, "flow": "If it is technical, call `transfer_to_tech`."})
    assert "unknown_tool" not in rules(spec)


def test_transfer_without_destination():
    spec = agent(prompt_sections={**GOOD, "flow": "If they are angry, transfer them to a manager."})
    assert "transfer_without_tool" in rules(spec)
    spec = agent(
        transfers=[TransferSpec(id="x", name="Manager", uri="tel:+15550100")],
        prompt_sections={**GOOD, "flow": "If they are angry, transfer them to a manager."},
    )
    assert "transfer_without_tool" not in rules(spec)


def test_audio_instructions_flagged():
    spec = agent(prompt_sections={**GOOD, "style": "Speak slowly with a British accent. No markdown."})
    assert "audio_instruction" in rules(spec)


def test_scripted_greeting_in_flow():
    spec = agent(prompt_sections={**GOOD, "flow": 'Start by saying "Hello, thanks for calling Acme!"'})
    assert "greeting_in_flow" in rules(spec)


def test_missing_sections_and_safety():
    spec = agent(prompt_sections={"role": "You are helpful.", "guardrails": "Stay on topic."})
    found = rules(spec)
    assert "missing_section" in found and "safety_path" in found


def test_raw_prompt_order_and_headers():
    raw = "# Role & Persona\nYou are X.\n## Objective\nDo Y.\n## Voice & Communication Style\nShort.\n## Conversation Flow\nZ."
    found = rules(agent(prompt_mode="raw", raw_prompt=raw, prompt_sections={}))
    assert {"h1_headers", "section_order"} <= found


def test_compile_order_and_generated_lines():
    edge = EdgeSpec(
        id="e", source_slug="billing", target_slug="tech", target_name="Tech Support", description="the issue is technical"
    )
    spec = agent(edges=[edge], key_facts="Hours: 9am-5pm", prompt_sections={**GOOD, "critical": "NEVER share passwords."})
    text = compile_instructions(
        spec,
        handoff=HandoffContext(
            from_agent="Front Desk", reason="billing", summary="Asked about a charge", fields={"account_email": "a@b.c"}
        ),
    )
    order = [
        "## Role & Persona",
        "## Business Facts",
        "## Objective",
        "## Conversation Flow",
        "## Guardrails & Escalation",
        "## Voice & Communication Style",
        "## Handoff Context",
        "## CRITICAL INSTRUCTIONS",
    ]
    positions = [text.index(h) for h in order]
    assert positions == sorted(positions)
    assert "`transfer_to_tech`" in text and "`end_call`" in text and "account_email: a@b.c" in text


def test_text_to_sections_roundtrip():
    sections = text_to_sections("## Role & Persona\nYou are X.\n## Objective\nDo Y.\n## Unknown header\nStill objective.")
    assert sections["role"] == "You are X."
    assert sections["objective"].startswith("Do Y.") and "Unknown header" in sections["objective"]
