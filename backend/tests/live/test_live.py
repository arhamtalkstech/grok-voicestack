"""Live tests against the real xAI API. Skipped unless XAI_API_KEY is set.

    XAI_API_KEY=... uv run pytest tests/live -m live -v

They drive the real SessionController + LangGraph runtime over a server-side realtime WebSocket,
using typed caller turns (the same path the live dock's text box uses).
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest
import yaml
from sqlalchemy import select

from conftest import EXAMPLE
from voicestack.api.landscape import import_landscape
from voicestack.db.models import Conversation, Turn
from voicestack.db.session import init_db, session_scope
from voicestack.prompting.linter import lint
from voicestack.prompting.optimizer import optimize_prompt
from voicestack.runtime.controller import SessionController
from voicestack.runtime.loader import load_landscape
from voicestack.runtime.persistence import open_persistence
from voicestack.runtime.specs import AgentSpec
from voicestack.runtime.transports.base import Transport
from voicestack.xai import realtime
from voicestack.xai.client import XAIClient

KEY = os.environ.get("XAI_API_KEY")
# Live tests make several sequential calls, and some wait up to 150 s for one turn, so they get
# more time than the 120 s default for unit tests.
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not KEY, reason="XAI_API_KEY not set"),
    pytest.mark.timeout(300),
]


class ServerTransport(Transport):
    """Holds the realtime socket server-side, like the SIP transport, but for a model session."""

    channel = "web"

    def __init__(self):
        super().__init__()
        self.ws = None
        self.sent: list[dict[str, Any]] = []
        self.received: list[dict[str, Any]] = []
        self.ui: list[dict[str, Any]] = []

    async def notify(self, message):
        self.ui.append(message.get("event", {}))

    async def connect(self, controller: SessionController) -> None:
        self.ws = await realtime.connect(KEY)

        async def reader():
            async for raw in self.ws:
                if isinstance(raw, bytes):
                    continue
                event = json.loads(raw)
                self.received.append(event)
                await controller.handle_xai_event(event)

        self.task = asyncio.create_task(reader())

    async def send(self, event):
        self.sent.append(event)
        await self.ws.send(json.dumps(event))

    async def close(self, reason=""):
        await self.ws.close()


async def wait_for(predicate, timeout=60.0, step=0.25):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if await predicate():
            return True
        await asyncio.sleep(step)
    return False


@pytest.fixture
async def landscape():
    await init_db()
    await open_persistence()
    async with session_scope() as db:
        await import_landscape(db, yaml.safe_load(EXAMPLE.read_text()), replace=True)
        return await load_landscape(db)


async def test_rest_endpoints():
    async with XAIClient(KEY) as client:
        voices = await client.list_voices()
        secret = await client.create_client_secret(60)
    assert voices and all("voice_id" in v for v in voices)
    assert secret.get("value") and secret.get("expires_at")


async def test_live_handoff_with_context(landscape):
    async with session_scope() as db:
        conv = Conversation(channel="web", entry_agent_id=landscape.agents["front-desk"].id)
        db.add(conv)
        await db.flush()
        conv_id = conv.id
    transport = ServerTransport()
    controller = SessionController(
        conversation_id=conv_id, landscape=landscape, entry_slug="front-desk", transport=transport, api_key=KEY
    )
    await transport.connect(controller)
    await controller.start()

    async def greeted():
        return any(e["type"] == "response.done" for e in transport.received)

    assert await wait_for(greeted, 45), [e["type"] for e in transport.received][-10:]
    await controller.send_text(
        "Hi, I'm building a voice agent that answers the phone for my dental clinic. Which voices can I use?"
    )

    async def handed_off():
        return controller.active_slug == "voice-specialist"

    assert await wait_for(handed_off, 60), [e["type"] for e in transport.received][-15:]
    await controller.idle()

    async def specialist_spoke():
        async with session_scope() as db:
            rows = (await db.execute(select(Turn).where(Turn.conversation_id == conv_id).order_by(Turn.seq))).scalars().all()
        return any(t.kind == "assistant" and t.agent_id == landscape.agents["voice-specialist"].id for t in rows)

    assert await wait_for(specialist_spoke, 60)
    updates = [e for e in transport.sent if e["type"] == "session.update"]
    assert updates[-1]["session"]["voice"] == "eve" and "## Handoff Context" in updates[-1]["session"]["instructions"]
    errors = [e for e in transport.received if e["type"] == "error"]
    assert not errors, errors

    await controller.end("test")
    await controller.wait_closed()
    async with session_scope() as db:
        conv = await db.get(Conversation, conv_id)
    assert conv.status == "ended"
    assert conv.summary, "post-call summary should be written by grok-4.3"


async def test_optimizer_improves_weak_prompt():
    weak = AgentSpec(
        id="agt_live",
        slug="billing",
        name="Billing",
        prompt_mode="raw",
        raw_prompt=(
            "# Billing bot\nThe assistant helps customers of Acme Mobile with bills. Our site is https://acme.example/help. "
            'Plans cost $25 per month. Speak slowly and with a British accent. Start by saying "Hello, Acme billing!". '
            "Look up accounts with lookup_account when needed."
        ),
    )
    before = lint(weak)
    result = await optimize_prompt(KEY, weak)
    variant = result["variants"][0]
    text = "\n".join(variant["sections"].values())
    assert variant["lint_after"]["score"] > before.score
    assert "https://acme.example/help" in text and "$25" in text
    assert "lookup_account" not in text, "the optimiser must not keep tools that are not attached"


async def open_session(landscape, entry: str, *, contact_id: str | None = None, resume_from: str | None = None):
    async with session_scope() as db:
        conv = Conversation(
            channel="web", entry_agent_id=landscape.agents[entry].id, contact_id=contact_id, resumed_from_id=resume_from
        )
        db.add(conv)
        await db.flush()
        conv_id = conv.id
    transport = ServerTransport()
    controller = SessionController(
        conversation_id=conv_id, landscape=landscape, entry_slug=entry, transport=transport, api_key=KEY, contact_id=contact_id
    )
    await transport.connect(controller)
    await controller.start(resume_from=resume_from)
    return controller, transport


async def settled(controller, transport, quiet: float = 3.0, timeout: float = 90.0) -> None:
    """Wait until the agent has finished its turn, including tool calls and their follow-up responses."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    seen, last_change = len(transport.received), loop.time()
    while loop.time() < deadline and not controller.closed:
        await asyncio.sleep(0.25)
        if len(transport.received) != seen:
            seen, last_change = len(transport.received), loop.time()
        responding = (
            any(e["type"] == "response.created" for e in transport.received[-50:])
            and transport.received[-1]["type"] != "response.done"
        )
        if loop.time() - last_change > quiet and not controller._busy and controller._jobs.empty() and not responding:
            return


async def ask(controller, transport, text: str, timeout: float = 90.0) -> str:
    """Send a typed caller turn and return everything the agents said until they settle."""
    before = len([e for e in transport.received if e["type"] == "response.output_audio_transcript.done"])
    await controller.send_text(text)
    await settled(controller, transport, timeout=timeout)
    done = [e for e in transport.received if e["type"] == "response.output_audio_transcript.done"][before:]
    return " ".join(e.get("transcript", "") for e in done)


def tool_events(transport, name: str) -> list[dict[str, Any]]:
    return [e for e in transport.ui if e.get("type") == "tool.finished" and e.get("name") == name]


async def landscape_with_mcp_mode(mode: str):
    from voicestack.db.models import McpServer

    async with session_scope() as db:
        server = (await db.execute(select(McpServer).where(McpServer.label == "deepwiki"))).scalar_one()
        original, server.mode = server.mode, mode
        await db.flush()
        result = await load_landscape(db)
        server.mode = original
    return result


async def test_live_tools_in_a_call(landscape):
    # First half: DeepWiki hosted by xAI (the sample ships it in managed mode).
    controller, transport = await open_session(await landscape_with_mcp_mode("xai"), "api-guide")
    await wait_for(lambda: asyncio.sleep(0, any(e["type"] == "session.updated" for e in transport.received)), 20)

    reply = await ask(
        controller,
        transport,
        "Look up the GitHub repository xai-org/xai-sdk-python. What language is it written in and roughly how many stars?",
    )
    calls = tool_events(transport, "look_up_repository")
    assert calls and calls[-1]["ok"], transport.ui[-5:]
    assert "Python" in calls[-1]["output"]
    print("HTTP tool reply:", reply)

    reply = await ask(
        controller, transport, "Using deepwiki, how does the xai-org/xai-sdk-python repository handle streaming?", timeout=120
    )
    mcp = sorted({e["type"] for e in transport.received if "mcp" in e["type"]})
    assert "response.mcp_call.completed" in mcp or "mcp_list_tools.completed" in mcp, mcp
    print("MCP events:", mcp, "reply:", reply[:200])

    await controller.end("test")
    await controller.wait_closed()

    # The same DeepWiki server in managed mode: langchain-mcp-adapters runs it as function tools.
    managed = await landscape_with_mcp_mode("managed")
    controller, transport = await open_session(managed, "api-guide")
    await asyncio.sleep(3)
    tools = [t.get("name") for t in [e for e in transport.sent if e["type"] == "session.update"][0]["session"]["tools"]]
    assert "ask_wiki_question" in tools, tools
    reply = await ask(
        controller,
        transport,
        "Use the ask_wiki_question tool on repo xai-org/xai-sdk-python: which class handles chat streaming?",
        timeout=150,
    )
    calls = tool_events(transport, "ask_wiki_question")
    assert calls and calls[-1]["ok"], [e for e in transport.ui if e.get("type", "").startswith("tool")][-4:]
    print("managed MCP reply:", reply[:300])

    reply = await ask(
        controller, transport, "Search the docs: what is the default reasoning effort for the voice model?", timeout=90
    )
    print("web_search reply:", reply[:200])
    assert reply
    assert not [e for e in transport.received if e["type"] == "error"]
    await controller.end("test")
    await controller.wait_closed()


POLICY = (
    "# Bright Smiles Dental policies\n\nThe after-hours emergency line is staffed by Dr. Okafor. "
    "New patients must arrive 20 minutes early. Cancellations need 48 hours notice or a 35 dollar fee applies.\n"
)


async def add_policy_document(kb_slug: str, mode: str) -> str:
    from voicestack.db.models import Document, KnowledgeBase
    from voicestack.knowledge.ingest import ingest_document, upload_path

    async with session_scope() as db:
        kb = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.slug == kb_slug))).scalar_one()
        kb.mode = mode
        if mode == "local":
            kb.collection_id = None
        doc = Document(kb_id=kb.id, filename="clinic-policies.md", mime="text/markdown", size=len(POLICY))
        db.add(doc)
        await db.flush()
        doc_id = doc.id
    upload_path(doc_id, "clinic-policies.md").write_text(POLICY)
    await ingest_document(doc_id)
    async with session_scope() as db:
        doc = await db.get(Document, doc_id)
        assert doc.status == "ready", doc.error
        return doc_id


async def stored_turns(conversation_id: str):
    async with session_scope() as db:
        return (await db.execute(select(Turn).where(Turn.conversation_id == conversation_id).order_by(Turn.seq))).scalars().all()


async def test_live_knowledge_collections(landscape):
    """Default mode: xAI Files API -> xAI Collection -> file_search run by xAI during the call."""
    from voicestack.db.models import ConversationEvent, Document, KnowledgeBase

    try:
        doc_id = await add_policy_document("voice-docs", "collections")
        async with session_scope() as db:
            doc = await db.get(Document, doc_id)
            kb = await db.get(KnowledgeBase, doc.kb_id)
            assert kb.collection_id and doc.external_file_id and doc.chunk_count >= 1
            landscape = await load_landscape(db)
        controller, transport = await open_session(landscape, "voice-specialist")
        await asyncio.sleep(3)
        tools = [t["type"] for t in [e for e in transport.sent if e["type"] == "session.update"][0]["session"]["tools"]]
        assert "file_search" in tools, tools
        reply = await ask(
            controller,
            transport,
            "What is the cancellation fee at Bright Smiles Dental, and how much notice is needed?",
            timeout=90,
        )
        assert "35" in reply or "thirty-five" in reply.lower(), reply
        print("collections reply:", reply)
        # xAI's own collections_search call is recorded, not answered.
        assert not [
            e
            for e in transport.sent
            if e["type"] == "conversation.item.create" and e["item"].get("type") == "function_call_output"
        ]
        await controller.end("test")
        await controller.wait_closed()
        turns = await stored_turns(controller.conversation_id)
        server_tools = [t for t in turns if t.kind == "tool" and t.data.get("server_side")]
        assert any("collections_search" in t.text for t in server_tools), [(t.kind, t.text) for t in turns]
        async with session_scope() as db:
            events = (
                (
                    await db.execute(
                        select(ConversationEvent).where(ConversationEvent.conversation_id == controller.conversation_id)
                    )
                )
                .scalars()
                .all()
            )
        types = {e.type for e in events}
        assert {"session.update", "response.done", "response.output_audio_transcript.done"} <= types, types
        print(f"stored {len(events)} events, tool turns: {[t.text for t in turns if t.kind == 'tool']}")

        async with session_scope() as db:
            conv = await db.get(Conversation, controller.conversation_id)
        assert conv.meta.get("time_to_first_audio_ms"), conv.meta
    finally:
        # Leave nothing behind on the xAI team, even when an assertion fails.
        async with session_scope() as db:
            kb = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.slug == "voice-docs"))).scalar_one()
        if kb.collection_id:
            async with XAIClient(KEY) as client:
                await client.delete_collection(kb.collection_id)


async def test_live_knowledge_local(landscape):
    """Local mode: LangChain loaders/splitter + FastEmbed, exposed as search_knowledge."""
    await add_policy_document("voice-docs", "local")
    async with session_scope() as db:
        landscape = await load_landscape(db)
    controller, transport = await open_session(landscape, "voice-specialist")
    await asyncio.sleep(3)
    reply = await ask(
        controller, transport, "Check the knowledge base: what is the cancellation fee and how much notice is needed?", timeout=90
    )
    calls = tool_events(transport, "search_knowledge")
    assert calls and calls[-1]["ok"] and "48 hours" in calls[-1]["output"]
    assert "35" in reply or "thirty-five" in reply.lower(), reply
    print("local knowledge reply:", reply)
    await controller.end("test")
    await controller.wait_closed()
    turns = await stored_turns(controller.conversation_id)
    tool = [t for t in turns if t.kind == "tool" and t.text == "search_knowledge"]
    assert tool and tool[0].data["args"].get("query") and "48 hours" in tool[0].data["output"]


async def test_live_transfer_end_and_hot_refresh(landscape):
    controller, transport = await open_session(landscape, "front-desk")
    await asyncio.sleep(4)

    # Hot refresh: change speed mid-call; a new session.update must go out and be accepted.
    async with session_scope() as db:
        from voicestack.db.models import Agent

        agent = (await db.execute(select(Agent).where(Agent.slug == "front-desk"))).scalar_one()
        agent.speed = 1.3
        await db.flush()
        new_landscape = await load_landscape(db)
        agent.speed = 1.0
    await controller.refresh(new_landscape)
    await controller.idle()
    updates = [e for e in transport.sent if e["type"] == "session.update"]
    assert updates[-1]["session"]["audio"]["output"]["speed"] == 1.3

    reply = await ask(controller, transport, "I'd like to speak to a human at developer relations, please.", timeout=90)
    calls = tool_events(transport, "transfer_call")
    assert calls and json.loads(calls[-1]["output"]).get("simulated") is True, transport.ui[-6:]
    print("transfer reply:", reply)

    if not controller.closed:
        await ask(controller, transport, "Actually that's everything, thank you. Goodbye!", timeout=60)
    assert tool_events(transport, "end_call"), "the agent should end the call with end_call"

    async def closed():
        return controller.closed

    assert await wait_for(closed, 30), "end_call should close the session"
    await controller.wait_closed()


async def test_live_memory_and_resume(landscape):
    from voicestack.db.models import Contact

    async with session_scope() as db:
        contact = Contact(external_key=f"+1415555{int(asyncio.get_running_loop().time()) % 10000:04d}")
        db.add(contact)
        await db.flush()
        contact_id = contact.id

    controller, transport = await open_session(landscape, "voice-specialist", contact_id=contact_id)
    await asyncio.sleep(3)
    await ask(
        controller, transport, "Hi, my name is Priya and I run Bright Smiles Dental. I want a phone agent for after-hours calls."
    )
    first_id = controller.conversation_id
    await controller.end("test")
    await controller.wait_closed()
    async with session_scope() as db:
        assert (await db.get(Conversation, first_id)).summary

    # A new call from the same caller gets the memory.
    controller, transport = await open_session(landscape, "voice-specialist", contact_id=contact_id)
    await asyncio.sleep(3)
    memory = [e for e in transport.ui if e.get("type") == "memory.loaded"]
    assert memory and "Priya" in memory[0]["text"], memory
    assert "## Caller Context" in [e for e in transport.sent if e["type"] == "session.update"][0]["session"]["instructions"]
    reply = await ask(controller, transport, "Do you remember my name and my clinic?")
    assert "Priya" in reply, reply
    print("memory reply:", reply)
    await controller.end("test")
    await controller.wait_closed()

    # Continue the first conversation: history is seeded into a fresh realtime session.
    # Without a contact, so only the seeded history (not caller memory) can supply the answer.
    controller, transport = await open_session(landscape, "voice-specialist", resume_from=first_id)
    await asyncio.sleep(4)
    seeded = [e for e in transport.sent if e["type"] == "conversation.item.create" and e["item"].get("type") == "message"]
    assert seeded, "resume should seed prior turns"
    assert any(e["item"]["role"] == "user" and "Priya" in e["item"]["content"][0]["text"] for e in seeded), seeded
    reply = await ask(controller, transport, "Remind me: what's my name, and what kind of calls did I want the agent to handle?")
    assert "Priya" in reply and "after" in reply.lower(), reply
    print("resume reply:", reply)
    await controller.end("test")
    await controller.wait_closed()


async def test_live_x_search(landscape):
    spec = landscape.agents["api-guide"]
    spec.builtin_tools = {**spec.builtin_tools, "x_search": {"enabled": True}}
    controller, transport = await open_session(landscape, "api-guide")
    await asyncio.sleep(3)
    tools = [t.get("name") for t in [e for e in transport.sent if e["type"] == "session.update"][0]["session"]["tools"]]
    assert "x_search" in tools, tools
    reply = await ask(
        controller, transport, "Search X: what are people posting about Grok voice today? One sentence.", timeout=120
    )
    calls = tool_events(transport, "x_search")
    assert calls and calls[-1]["ok"] and '"ok": true' in calls[-1]["output"], transport.ui[-4:]
    assert "token" not in reply.lower() and "can't access" not in reply.lower(), reply
    print("x_search reply:", reply[:300])
    await controller.end("test")
    await controller.wait_closed()
