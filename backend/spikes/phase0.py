"""Phase 0: check undocumented or conflicting xAI realtime behaviors against the live API.

    XAI_API_KEY=... uv run python spikes/phase0.py            # writes ../docs/xai-api-notes.md

Each check prints PASS/FAIL/INFO with evidence. Voice and speed changes are measured from the audio
itself: pitch (autocorrelation) tells a female from a male voice, and audio duration for the same
force_message text tells whether speed changed.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import websockets

API = "https://api.x.ai"
WSS = "wss://api.x.ai/v1/realtime"
MODEL = os.environ.get("VOICE_MODEL", "grok-voice-latest")
KEY = os.environ.get("XAI_API_KEY", "")
OUT = Path(__file__).resolve().parents[2] / "docs" / "xai-api-notes.md"
RATE = 24000


@dataclass
class Result:
    name: str
    status: str
    detail: str
    evidence: list[str] = field(default_factory=list)


results: list[Result] = []


def record(name: str, status: str, detail: str, evidence: list[str] | None = None) -> None:
    results.append(Result(name, status, detail, evidence or []))
    print(f"[{status}] {name}: {detail}")


class Session:
    def __init__(self, ws):
        self.ws = ws
        self.events: list[dict[str, Any]] = []

    @classmethod
    async def open(cls, *, token: str | None = None, query: str = "") -> Session:
        url = f"{WSS}?model={MODEL}{query}"
        if token:
            ws = await websockets.connect(url, subprotocols=[f"xai-client-secret.{token}"], max_size=None)
        else:
            ws = await websockets.connect(url, additional_headers={"Authorization": f"Bearer {KEY}"}, max_size=None)
        return cls(ws)

    async def send(self, event: dict[str, Any]) -> None:
        await self.ws.send(json.dumps(event))

    async def until(self, types: set[str], timeout: float = 30) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"none of {types} within {timeout}s; last: {[e['type'] for e in self.events[-8:]]}")
            raw = await asyncio.wait_for(self.ws.recv(), timeout=remaining)
            if isinstance(raw, bytes):
                continue
            event = json.loads(raw)
            self.events.append(event)
            if event["type"] in types:
                return event

    async def respond(self, timeout: float = 45) -> tuple[bytes, str, list[dict[str, Any]]]:
        """Collect one response: audio bytes, transcript, function calls."""
        audio, transcript, calls = bytearray(), "", []
        while True:
            event = await self.until(
                {
                    "response.output_audio.delta",
                    "response.audio.delta",
                    "response.output_audio_transcript.done",
                    "response.function_call_arguments.done",
                    "response.done",
                    "error",
                },
                timeout,
            )
            t = event["type"]
            if t in ("response.output_audio.delta", "response.audio.delta"):
                audio.extend(base64.b64decode(event["delta"]))
            elif t == "response.output_audio_transcript.done":
                transcript = event.get("transcript", "")
            elif t == "response.function_call_arguments.done":
                calls.append(event)
            elif t == "error":
                raise RuntimeError(event.get("error"))
            elif t == "response.done":
                return bytes(audio), transcript, calls

    async def say(self, text: str, **response: Any) -> tuple[bytes, str, list[dict[str, Any]]]:
        await self.send(
            {
                "type": "conversation.item.create",
                "item": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]},
            }
        )
        await self.send({"type": "response.create", **({"response": response} if response else {})})
        return await self.respond()

    async def configure(self, session: dict[str, Any]) -> dict[str, Any]:
        await self.send({"type": "session.update", "session": session})
        return await self.until({"session.updated", "error"})

    async def close(self) -> None:
        await self.ws.close()


def pitch_hz(pcm: bytes) -> float:
    """Median fundamental frequency of voiced 40 ms frames (autocorrelation)."""
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    frame, hop, estimates = int(0.04 * RATE), int(0.02 * RATE), []
    lo, hi = int(RATE / 400), int(RATE / 70)
    for start in range(0, len(x) - frame, hop):
        seg = x[start : start + frame]
        if np.sqrt(np.mean(seg**2)) < 0.02:
            continue
        seg = seg - seg.mean()
        corr = np.correlate(seg, seg, mode="full")[frame - 1 :]
        if corr[0] <= 0:
            continue
        lag = lo + int(np.argmax(corr[lo:hi]))
        if corr[lag] / corr[0] > 0.3:
            estimates.append(RATE / lag)
    return float(np.median(estimates)) if estimates else 0.0


def seconds(pcm: bytes) -> float:
    return len(pcm) / 2 / RATE


BASE = {
    "turn_detection": {"type": None},
    "audio": {"output": {"format": {"type": "audio/pcm", "rate": RATE}}},
    "reasoning": {"effort": "none"},
}


async def check_rest(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/tts/voices")
    voices = r.json().get("voices", []) if r.status_code == 200 else []
    record(
        "GET /v1/tts/voices",
        "PASS" if voices else "FAIL",
        f"{r.status_code}; {len(voices)} voices",
        [", ".join(f"{v.get('voice_id')} ({v.get('name', '')})" for v in voices)],
    )
    r = await client.post("/v1/realtime/client_secrets", json={"expires_after": {"seconds": 60}})
    record(
        "client_secrets without session",
        "PASS" if r.status_code == 200 else "FAIL",
        f"{r.status_code}",
        [r.text[:200].replace(r.json().get("value", "~"), "<token>") if r.status_code == 200 else r.text[:300]],
    )
    r = await client.post(
        "/v1/realtime/client_secrets",
        json={"expires_after": {"seconds": 60}, "session": {"model": MODEL, "reasoning": {"effort": "none"}}},
    )
    record(
        "client_secrets with session field",
        "INFO",
        f"{r.status_code} (REST reference lists it; the guide page says unsupported)",
        [r.text[:300] if r.status_code != 200 else "accepted"],
    )
    # These lists hold the team's own resources (numbers, voice names, IDs), so the
    # notes record only counts and field names, never values.
    r = await client.get("/v1/custom-voices", params={"limit": 5})
    record("GET /v1/custom-voices", "INFO", f"{r.status_code}", [_shape(r, "voices")])
    r = await client.get("/v2/phone-numbers")
    record("GET /v2/phone-numbers", "INFO", f"{r.status_code}", [_shape(r, "phone_numbers")])


def _shape(r: httpx.Response, key: str) -> str:
    if r.status_code != 200:
        return f"HTTP {r.status_code}"
    items = r.json().get(key) or []
    fields = sorted({k for item in items for k in item})
    return f"{len(items)} item(s); fields: {', '.join(fields) or 'n/a'}"


async def check_ephemeral() -> None:
    async with httpx.AsyncClient(base_url=API, headers={"Authorization": f"Bearer {KEY}"}) as c:
        token = (await c.post("/v1/realtime/client_secrets", json={"expires_after": {"seconds": 120}})).json()["value"]
    s = await Session.open(token=token)
    created = await s.until({"conversation.created", "session.created"})
    await s.configure({**BASE, "voice": "eve", "instructions": "You are terse."})
    _, transcript, _ = await s.say("Say the word ready.")
    record("Ephemeral token via subprotocol", "PASS", f"connected; first event {created['type']}; reply: {transcript!r}")
    await s.close()


async def check_tool_shapes() -> None:
    for shape in ("flat", "nested"):
        fn = {"name": "get_code", "description": "Returns today's code word.", "parameters": {"type": "object", "properties": {}}}
        tool = {"type": "function", **fn} if shape == "flat" else {"type": "function", "function": fn}
        s = await Session.open()
        ack = await s.configure(
            {**BASE, "voice": "eve", "instructions": "Always call get_code when asked for the code word.", "tools": [tool]}
        )
        try:
            _, transcript, calls = await s.say("What is the code word?")
            status = "PASS" if calls and calls[0].get("name") == "get_code" else "FAIL"
            record(
                f"Function tool shape: {shape}",
                status,
                f"session.update -> {ack['type']}; function calls: {[c.get('name') for c in calls]}",
                [transcript],
            )
        except Exception as exc:
            record(f"Function tool shape: {shape}", "FAIL", str(exc))
        await s.close()


async def check_parallel_and_output() -> None:
    tools = [
        {
            "type": "function",
            "name": "get_weather",
            "description": "Weather for a city",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
        },
        {
            "type": "function",
            "name": "get_time",
            "description": "Local time for a city",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
        },
    ]
    s = await Session.open()
    await s.configure(
        {
            **BASE,
            "voice": "eve",
            "instructions": "Use tools for weather and time. Call both tools at once when asked for both.",
            "tools": tools,
        }
    )
    _, _, calls = await s.say("What's the weather and the local time in Paris?")
    for call in calls:
        out = {
            "get_weather": {"city": "Paris", "temp_c": 18, "sky": "cloudy"},
            "get_time": {"city": "Paris", "time": "14:05"},
        }.get(call["name"], {})
        await s.send(
            {
                "type": "conversation.item.create",
                "item": {"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(out)},
            }
        )
    await s.send({"type": "response.create"})
    _, transcript, _ = await s.respond()
    record(
        "Parallel function calls",
        "PASS" if len(calls) >= 2 else "INFO",
        f"{len(calls)} calls in one response: {[c['name'] for c in calls]}",
        [transcript],
    )
    await s.close()


async def check_voice_switch() -> None:
    s = await Session.open()
    await s.configure({**BASE, "voice": "eve", "instructions": "Repeat exactly what the user asks you to say."})
    a1, _, _ = await s.say("Say: the quick brown fox jumps over the lazy dog, twice.")
    ack = await s.configure({"voice": "rex"})
    a2, _, _ = await s.say("Say: the quick brown fox jumps over the lazy dog, twice.")
    p1, p2 = pitch_hz(a1), pitch_hz(a2)
    echoed = (ack.get("session") or {}).get("voice")
    changed = p1 > 0 and p2 > 0 and abs(p1 - p2) > 25
    record(
        "Voice change after first audio (session.update)",
        "PASS" if changed else "FAIL",
        f"eve median pitch {p1:.0f} Hz -> after update to rex {p2:.0f} Hz; session.updated voice={echoed!r}",
        ["PASS means handoffs can switch voice in-session (HANDOFF_VOICE_MODE=in_session)."],
    )
    await s.close()


async def check_speed_and_force_message() -> None:
    s = await Session.open()
    await s.configure({**BASE, "voice": "ara", "instructions": "You are helpful."})
    text = "This call may be recorded for quality and training purposes. Thank you for your patience."
    durations = {}
    for speed in (1.0, 1.4):
        await s.configure({"audio": {"output": {"speed": speed, "format": {"type": "audio/pcm", "rate": RATE}}}})
        await s.send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "force_message",
                    "role": "assistant",
                    "interruptible": False,
                    "content": [{"type": "output_text", "text": text}],
                },
            }
        )
        audio, transcript, _ = await s.respond()
        durations[speed] = seconds(audio)
    ratio = durations[1.0] / durations[1.4] if durations[1.4] else 0
    record(
        "force_message", "PASS" if durations[1.0] > 1 else "FAIL", f"{durations[1.0]:.2f}s of audio for a {len(text)}-char line"
    )
    record(
        "Speed change mid-session",
        "PASS" if ratio > 1.15 else "FAIL",
        f"1.0x {durations[1.0]:.2f}s vs 1.4x {durations[1.4]:.2f}s (ratio {ratio:.2f})",
    )
    await s.close()


async def check_seeding_and_overrides() -> None:
    s = await Session.open()
    await s.configure({**BASE, "voice": "eve", "instructions": "Answer in one short sentence."})
    for item in (
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Remember: my project is called Bluefin."}],
        },
        {"type": "message", "role": "assistant", "content": [{"type": "text", "text": "Got it, your project is Bluefin."}]},
    ):
        await s.send({"type": "conversation.item.create", "item": item})
    _, transcript, _ = await s.say("What is my project called?")
    record(
        "History seeding (assistant content type 'text')", "PASS" if "bluefin" in transcript.lower() else "FAIL", repr(transcript)
    )
    await s.send(
        {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "system",
                "content": [{"type": "input_text", "text": "The caller's account tier is Gold."}],
            },
        }
    )
    _, transcript, _ = await s.say("What tier am I?")
    record("System-role context item", "PASS" if "gold" in transcript.lower() else "FAIL", repr(transcript))
    _, transcript, _ = await s.say("Say hello.", instructions="Respond only in Spanish, one short sentence.")
    record("Per-response instructions override", "INFO", repr(transcript))
    await s.close()


async def check_resumption() -> None:
    s = await Session.open()
    created = await s.until({"conversation.created"})
    conv_id = created["conversation"]["id"]
    await s.configure({**BASE, "voice": "eve", "instructions": "Answer in one short sentence.", "resumption": {"enabled": True}})
    await s.say("My favourite colour is teal. Just say okay.")
    await s.close()
    await asyncio.sleep(2)
    s2 = await Session.open(query=f"&conversation_id={conv_id}")
    again = await s2.until({"conversation.created"})
    await s2.configure({**BASE, "voice": "eve", "instructions": "Answer in one short sentence.", "resumption": {"enabled": True}})
    await asyncio.sleep(1)
    _, transcript, _ = await s2.say("What is my favourite colour?")
    replayed = [
        e["item"].get("role")
        for e in s2.events
        if e["type"] in ("conversation.item.added", "conversation.item.created") and (e.get("item") or {}).get("replayed")
    ]
    same = (again.get("conversation") or {}).get("id") == conv_id
    record(
        "Session resumption (conversation_id)",
        "PASS" if "teal" in transcript.lower() else "INFO",
        f"same conversation id: {same}; replayed roles: {replayed}; answer: {transcript!r}",
        [
            "Typed (input_text) user turns were not replayed in this test; only assistant turns were. Voice Stack resumes by seeding history with conversation.item.create instead."
        ],
    )
    await s2.close()


async def check_mcp() -> None:
    s = await Session.open()
    ack = await s.configure(
        {
            **BASE,
            "voice": "eve",
            "instructions": "Use deepwiki to answer repository questions. One sentence.",
            "tools": [
                {
                    "type": "mcp",
                    "server_url": "https://mcp.deepwiki.com/mcp",
                    "server_label": "deepwiki",
                    "allowed_tools": ["ask_wiki_question"],
                }
            ],
        }
    )
    try:
        _, transcript, _ = await s.say("Using deepwiki, what language is the xai-org/xai-sdk-python repository written in?")
        mcp_events = sorted({e["type"] for e in s.events if "mcp" in e["type"]})
        record(
            "xAI-hosted MCP (deepwiki)", "PASS" if mcp_events else "INFO", f"{ack['type']}; events: {mcp_events}", [transcript]
        )
    except Exception as exc:
        record("xAI-hosted MCP (deepwiki)", "FAIL", str(exc))
    await s.close()


async def check_native_x_search() -> None:
    s = await Session.open()
    await s.configure(
        {**BASE, "voice": "eve", "instructions": "Use x_search for questions about posts on X.", "tools": [{"type": "x_search"}]}
    )
    _, transcript, calls = await s.say("What did the spacexai account post most recently on X?")
    await asyncio.sleep(8)
    followups = [e for e in s.events if e["type"] == "response.created"]
    names = [c.get("name") for c in calls]
    record(
        "Native x_search in realtime",
        "INFO",
        f"client-visible function calls: {names}; responses after the call: {len(followups) - 1}; spoken: {transcript[:120]!r}",
        ["Voice Stack offers x_search as its own function tool backed by the Responses API instead of the native tool."],
    )
    await s.close()


async def check_transcription_model() -> None:
    s = await Session.open()
    ack = await s.configure({**BASE, "audio": {**BASE["audio"], "input": {"transcription": {"model": "grok-transcribe"}}}})
    record(
        "audio.input.transcription.model=grok-transcribe accepted",
        "PASS" if ack["type"] == "session.updated" else "FAIL",
        json.dumps(ack.get("error") or (ack.get("session") or {}).get("audio", {}))[:300],
    )
    await s.close()


def write_notes() -> None:
    lines = [
        "# xAI realtime API notes (verified)",
        "",
        f"Generated by `backend/spikes/phase0.py` on {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} against `{MODEL}`.",
        "Each row is a live call; rerun the script to refresh. Voice Stack's defaults follow these results.",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r.name} | {r.status} | {r.detail.replace('|', '/')} |")
    lines.append("")
    for r in results:
        if r.evidence:
            lines += [f"### {r.name}", "", *[f"    {e}" for e in r.evidence if e], ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    print(f"\nWrote {OUT}")


async def main() -> None:
    if not KEY:
        sys.exit("Set XAI_API_KEY")
    async with httpx.AsyncClient(base_url=API, headers={"Authorization": f"Bearer {KEY}"}, timeout=60) as client:
        await check_rest(client)
    for check in (
        check_ephemeral,
        check_tool_shapes,
        check_parallel_and_output,
        check_voice_switch,
        check_speed_and_force_message,
        check_seeding_and_overrides,
        check_resumption,
        check_mcp,
        check_native_x_search,
        check_transcription_model,
    ):
        try:
            await check()
        except Exception as exc:
            record(check.__name__, "FAIL", f"{type(exc).__name__}: {exc}")
    write_notes()


if __name__ == "__main__":
    asyncio.run(main())
