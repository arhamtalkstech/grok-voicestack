"""Compiles an agent into the `session` object for xAI's session.update event."""

from __future__ import annotations

from typing import Any

from voicestack.prompting.compiler import HandoffContext, compile_instructions
from voicestack.runtime.specs import AgentSpec

BROWSER_AUDIO = {"format": {"type": "audio/pcm", "rate": 24000}}


def render_session(
    agent: AgentSpec,
    realtime_tools: list[dict[str, Any]],
    *,
    channel: str,
    include_voice: bool = True,
    handoff: HandoffContext | None = None,
    caller_context: str | None = None,
    resumption: bool = True,
) -> dict[str, Any]:
    session: dict[str, Any] = {
        "instructions": compile_instructions(agent, handoff=handoff, caller_context=caller_context),
        "turn_detection": {"type": "server_vad"},
        "tools": realtime_tools,
        "reasoning": {"effort": agent.reasoning_effort},
    }
    if include_voice:
        session["voice"] = agent.voice_id
    if agent.idle_timeout_ms:
        session["turn_detection"]["idle_timeout_ms"] = agent.idle_timeout_ms

    audio_in: dict[str, Any] = {}
    audio_out: dict[str, Any] = {"speed": round(max(0.7, min(1.5, agent.speed)), 2)}
    if channel == "web":
        audio_in.update(BROWSER_AUDIO)
        audio_out.update(BROWSER_AUDIO)
    transcription: dict[str, Any] = {}
    if agent.language_hint:
        transcription["language_hint"] = agent.language_hint
    if agent.keyterms:
        transcription["keyterms"] = [k[:50] for k in agent.keyterms if k.strip()][:100]
    if transcription:
        audio_in["transcription"] = transcription
    session["audio"] = {"output": audio_out, **({"input": audio_in} if audio_in else {})}

    if agent.replace_map:
        session["replace"] = {k: v for k, v in agent.replace_map.items() if k.strip() and v.strip()}
    if resumption:
        session["resumption"] = {"enabled": True}
    return session


def greeting_directive(agent: AgentSpec) -> str:
    if agent.greeting.strip():
        return (
            "For this turn only: open the conversation by greeting the caller with this line, "
            f"in natural spoken words: {agent.greeting.strip()}"
        )
    return "For this turn only: greet the caller in one short sentence and ask how you can help."


def handoff_directive(agent: AgentSpec, handoff: HandoffContext) -> str:
    if handoff.greeting.strip():
        return f"For this turn only: you have just taken over the conversation. Say: {handoff.greeting.strip()}"
    return (
        f"For this turn only: you are {agent.name} and have just taken over from {handoff.from_agent}. "
        "Introduce yourself in one short sentence and continue helping with what the caller needs. "
        "Do not ask for details they already gave."
    )
