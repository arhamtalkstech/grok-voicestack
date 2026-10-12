"""Drives the real SessionController + LangGraph runtime with scripted xAI server events.

The transport records what Voice Stack would send to xAI. No network calls: this checks routing,
handoff context, persistence, and action ordering. Live behavior is covered by tests/live.
"""

import asyncio
import json

import pytest
import yaml
from sqlalchemy import select

from conftest import EXAMPLE
from voicestack.api.landscape import import_landscape
from voicestack.db.models import Conversation, Turn
from voicestack.db.session import init_db, session_scope
from voicestack.runtime.controller import SessionController
from voicestack.runtime.loader import load_landscape
from voicestack.runtime.persistence import open_persistence
from voicestack.runtime.transports.base import Transport


class RecordingTransport(Transport):
    channel = "web"

    def __init__(self):
        super().__init__()
        self.sent: list[dict] = []
        self.ui: list[dict] = []

    async def send(self, event):
        self.sent.append(event)

    async def notify(self, message):
        self.ui.append(message)


async def settle(controller: SessionController) -> None:
    await asyncio.sleep(0.01)
    await controller.idle()


@pytest.fixture
async def landscape():
    await init_db()
    await open_persistence()
    async with session_scope() as db:
        await import_landscape(db, yaml.safe_load(EXAMPLE.read_text()), replace=True)
        return await load_landscape(db)


async def new_controller(landscape) -> tuple[SessionController, RecordingTransport]:
    async with session_scope() as db:
        conv = Conversation(channel="web", entry_agent_id=landscape.agents["front-desk"].id)
        db.add(conv)
        await db.flush()
        conv_id = conv.id
    transport = RecordingTransport()
    controller = SessionController(
        conversation_id=conv_id, landscape=landscape, entry_slug="front-desk", transport=transport, api_key=None
    )
    return controller, transport


async def test_start_sends_session_then_greeting(landscape):
    controller, transport = await new_controller(landscape)
    await controller.start()
    await settle(controller)
    types = [e["type"] for e in transport.sent]
    assert types[:2] == ["session.update", "response.create"]
    session = transport.sent[0]["session"]
    assert session["voice"] == "ara" and session["audio"]["input"]["format"]["rate"] == 24000
    names = {t.get("name") for t in session["tools"] if t["type"] == "function"}
    assert {"transfer_to_api_guide", "transfer_to_voice_specialist", "transfer_call", "end_call"} <= names
    assert "Thanks for calling the Grok developer help line" in transport.sent[1]["response"]["instructions"]
    await controller.end("test")


async def test_handoff_carries_context_and_switches_agent(landscape):
    controller, transport = await new_controller(landscape)
    await controller.start()
    await settle(controller)
    transport.sent.clear()

    await controller.handle_xai_event(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "I'm building a phone agent for my clinic",
        }
    )
    await controller.handle_xai_event({"type": "response.created", "response": {"id": "resp_1"}})
    await controller.handle_xai_event(
        {
            "type": "response.output_audio_transcript.done",
            "response_id": "resp_1",
            "transcript": "Let me connect you with our voice specialist.",
        }
    )
    args = {
        "reason": "voice agent",
        "summary": "Building a phone agent for a clinic",
        "use_case": "clinic phone line",
        "channel": "phone",
    }
    await controller.handle_xai_event(
        {
            "type": "response.function_call_arguments.done",
            "response_id": "resp_1",
            "call_id": "call_1",
            "name": "transfer_to_voice_specialist",
            "arguments": json.dumps(args),
        }
    )
    await controller.handle_xai_event({"type": "response.done", "response": {"id": "resp_1", "output": []}})
    await settle(controller)

    types = [e["type"] for e in transport.sent]
    assert types == ["conversation.item.create", "session.update", "response.create"], types
    output = json.loads(transport.sent[0]["item"]["output"])
    assert transport.sent[0]["item"]["call_id"] == "call_1" and output == {"ok": True, "transferred_to": "Voice Specialist"}
    session = transport.sent[1]["session"]
    assert session["voice"] == "eve"
    assert "## Handoff Context" in session["instructions"] and "use_case: clinic phone line" in session["instructions"]
    # The sample knowledge base is an xAI Collection created on first upload, so no knowledge tool yet.
    assert "transfer_to_api_guide" in {t.get("name") for t in session["tools"] if t["type"] == "function"}
    assert controller.active_slug == "voice-specialist"

    async with session_scope() as db:
        turns = (
            (await db.execute(select(Turn).where(Turn.conversation_id == controller.conversation_id).order_by(Turn.seq)))
            .scalars()
            .all()
        )
        conv = await db.get(Conversation, controller.conversation_id)
    kinds = [t.kind for t in turns]
    assert kinds[-3:] == ["user", "assistant", "handoff"]
    assert turns[-1].data["fields"] == {"use_case": "clinic phone line", "channel": "phone"}
    assert landscape.agents["voice-specialist"].id in conv.agents_visited

    from voicestack.api.conversations import conversation_state

    state = await conversation_state(controller.conversation_id)
    assert state["active_agent"] == "voice-specialist" and state["context"]["use_case"] == "clinic phone line"
    assert state["handoffs"][0]["from"] == "front-desk"
    await controller.end("test")


async def test_handoff_missing_required_field_is_rejected(landscape):
    controller, transport = await new_controller(landscape)
    await controller.start()
    await settle(controller)
    transport.sent.clear()
    await controller.handle_xai_event(
        {
            "type": "response.function_call_arguments.done",
            "call_id": "c2",
            "name": "transfer_to_api_guide",
            "arguments": json.dumps({"reason": "api", "summary": "x"}),
        }
    )
    await controller.handle_xai_event({"type": "response.done", "response": {"id": "r2"}})
    await settle(controller)
    output = json.loads(transport.sent[0]["item"]["output"])
    assert output["ok"] is False and "topic" in output["error"]
    assert transport.sent[-1] == {"type": "response.create"}
    assert controller.active_slug == "front-desk"
    await controller.end("test")


async def test_end_call_tool_ends_session(landscape):
    controller, transport = await new_controller(landscape)
    await controller.start()
    await settle(controller)
    await controller.handle_xai_event(
        {"type": "response.function_call_arguments.done", "call_id": "c3", "name": "end_call", "arguments": "{}"}
    )
    await controller.handle_xai_event({"type": "response.done", "response": {"id": "r3"}})
    await settle(controller)
    assert controller.closed
    assert any(m.get("event", {}).get("type") == "session.end" for m in transport.ui)
