"""SessionController: one per live conversation, independent of how audio travels.

It consumes xAI realtime server events, persists the transcript, invokes the LangGraph runtime when a
decision is needed (function calls, handoffs, start, end), and turns the graph's actions into xAI
client events through a Transport (browser-direct, relay, or SIP).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from sqlalchemy import func, select

from voicestack.config import get_settings
from voicestack.db.models import Conversation, ConversationEvent, Turn, now
from voicestack.db.session import session_scope
from voicestack.runtime.bus import bus
from voicestack.runtime.graph import RuntimeDeps, get_graph, recall
from voicestack.runtime.persistence import get_persistence
from voicestack.runtime.specs import LandscapeSpec
from voicestack.runtime.transports.base import Transport
from voicestack.tools.registry import ToolContext

log = logging.getLogger(__name__)
# Tools xAI runs itself but still reports as function calls (verified live). Voice Stack records
# them as server-side tool turns and must not answer them with a function_call_output.
SERVER_SIDE_CALLS = {
    "web_search",
    "browse_page",
    "collections_search",
    "file_search",
    "x_keyword_search",
    "x_semantic_search",
    "x_user_search",
    "x_thread_fetch",
    "code_execution",
}
UNLOGGED_EVENTS = {
    "response.output_audio.delta",
    "response.audio.delta",
    "response.output_audio_transcript.delta",
    "response.audio_transcript.delta",
    "response.function_call_arguments.delta",
    "response.mcp_call_arguments.delta",
    "conversation.item.input_audio_transcription.updated",
    "input_audio_buffer.append",
    "ping",
}
FORWARDED_UI_EVENTS = {
    "input_audio_buffer.speech_started",
    "input_audio_buffer.speech_stopped",
    "input_audio_buffer.timeout_triggered",
    "response.created",
    "response.done",
    "session.updated",
    "mcp_list_tools.completed",
    "mcp_list_tools.failed",
    "response.mcp_call.in_progress",
    "response.mcp_call.completed",
    "response.mcp_call.failed",
}


class SessionController:
    def __init__(
        self,
        *,
        conversation_id: str,
        landscape: LandscapeSpec,
        entry_slug: str,
        transport: Transport,
        api_key: str | None,
        contact_id: str | None = None,
        call_id: str | None = None,
        disclosure: str | None = None,
    ):
        self.conversation_id = conversation_id
        self.landscape = landscape
        self.active_slug = entry_slug
        self.transport = transport
        self.channel = transport.channel
        self.contact_id = contact_id
        self.call_id = call_id
        self._lock = asyncio.Lock()
        self._pending_calls: dict[str, dict[str, Any]] = {}
        self._response_agent: dict[str, str] = {}
        self._response_audio_seen: set[str] = set()
        self._turn_started_at: float | None = None
        self._ttfa: list[int] = []
        self._event_buf: list[ConversationEvent] = []
        self._record = get_settings().record_events
        self._seq: int | None = None
        # Graph work runs on one ordered worker so the transport reader never blocks (it must keep
        # reading playback events while an action waits for playback to finish).
        self._jobs: asyncio.Queue[tuple[dict[str, Any], dict[str, Any] | None] | None] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._busy = False
        self.closed = False
        self.started = False
        self.tool_ctx = ToolContext(
            conversation_id=conversation_id,
            channel=self.channel,
            call_id=call_id,
            api_key=api_key,
            wait_playback=transport.wait_playback_idle,
            emit=self.emit,
        )
        persistence = get_persistence()
        self.deps = RuntimeDeps(
            landscape=landscape,
            tool_ctx=self.tool_ctx,
            store=persistence.store,
            api_key=api_key,
            disclosure=disclosure,
        )

    # Lifecycle ----------------------------------------------------------------------------------

    async def start(self, resume_from: str | None = None) -> None:
        """Begin the session. `resume_from` continues an earlier conversation's history and context."""
        if self.started:
            return
        self.started = True
        bus.register(self)
        self._worker = asyncio.create_task(self._run_worker())
        caller_context = await recall(self.deps.store, self.contact_id) if self.contact_id else None
        if caller_context:
            await self.emit({"type": "memory.loaded", "text": caller_context})
        initial: dict[str, Any] = {
            "active_agent": self.active_slug,
            "channel": self.channel,
            "contact_id": self.contact_id,
            "caller_context": caller_context,
        }
        if resume_from:
            persistence = get_persistence()
            graph = get_graph(self.landscape, persistence.checkpointer, persistence.store)
            prior = (await graph.aget_state({"configurable": {"thread_id": resume_from}})).values or {}
            initial["messages"] = prior.get("messages", [])
            initial["context"] = prior.get("context", {})
            if prior.get("active_agent") in self.landscape.agents:
                self.active_slug = initial["active_agent"] = prior["active_agent"]
        await self.emit({"type": "agent.active", "agent": self.active_slug, "reason": "resume" if resume_from else "start"})
        self._enqueue({"type": "start", "resume": bool(resume_from)}, initial=initial)

    def _enqueue(self, event: dict[str, Any], initial: dict[str, Any] | None = None) -> None:
        self._jobs.put_nowait((event, initial))

    async def _run_worker(self) -> None:
        while True:
            job = await self._jobs.get()
            if job is None:
                return
            event, initial = job
            if self.closed and event["type"] not in ("user_turn", "assistant_turn", "end"):
                continue
            self._busy = True
            try:
                if event["type"] == "end":
                    await self._finalize()
                else:
                    await self._invoke(event, initial)
            except Exception as exc:
                log.exception("Runtime step %s failed", event.get("type"))
                await self.emit({"type": "error", "source": "voicestack", "message": f"{event.get('type')}: {exc}"})
            finally:
                self._busy = False

    async def idle(self, timeout: float = 30.0) -> None:
        """Wait until every queued runtime step and its actions have finished."""
        deadline = asyncio.get_running_loop().time() + timeout
        while (self._busy or not self._jobs.empty()) and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.02)

    async def wait_closed(self) -> None:
        if self._worker:
            await self._worker

    async def end(self, reason: str = "ended", *, hangup: bool = True) -> None:
        if self.closed:
            return
        self.closed = True
        await self.emit({"type": "session.ending", "reason": reason})
        if hangup and self.channel == "sip" and self.call_id and self.tool_ctx.api_key and reason != "transferred":
            from voicestack.xai.client import XAIClient

            try:
                async with XAIClient(self.tool_ctx.api_key) as client:
                    await client.hangup_call(self.call_id)
            except Exception:
                log.exception("Hangup failed for call %s", self.call_id)
        bus.unregister(self.conversation_id)
        await self.transport.notify({"kind": "ui", "event": {"type": "session.end", "reason": reason}})
        await self.transport.close(reason)
        async with session_scope() as db:
            conv = await db.get(Conversation, self.conversation_id)
            if conv:
                conv.status, conv.ended_at = "ended", now()
                conv.meta = {**(conv.meta or {}), "end_reason": reason, "time_to_first_audio_ms": self._ttfa}
        await self._flush_events()
        self._enqueue({"type": "end"})
        self._jobs.put_nowait(None)

    async def _finalize(self) -> None:
        try:
            graph = get_graph(self.landscape, get_persistence().checkpointer, get_persistence().store)
            async with self._lock:
                result = await graph.ainvoke({"event": {"type": "end"}}, config=self._config(), context=self.deps)
            summary = result.get("call_summary")
            if summary:
                async with session_scope() as db:
                    conv = await db.get(Conversation, self.conversation_id)
                    conv.summary = summary["summary"]
                    conv.disposition = summary["disposition"]
                    conv.extracted = {f["key"]: f["value"] for f in summary.get("extracted", [])}
                bus.publish(self.conversation_id, {"type": "summary.ready", "summary": summary})
        except Exception:
            log.exception("Finalizing conversation %s failed", self.conversation_id)

    async def refresh(self, landscape: LandscapeSpec) -> None:
        """Hot-apply edited agent config to the running session."""
        self.landscape = landscape
        self.deps.landscape = landscape
        self.deps.invalidate()
        if self.active_slug not in landscape.agents:
            return
        self._enqueue({"type": "refresh"})
        await self.emit({"type": "session.refreshed", "agent": self.active_slug})

    # Inbound from the client (typed text) -------------------------------------------------------

    async def send_text(self, text: str) -> None:
        text = text.strip()
        if not text or self.closed:
            return
        self._turn_started_at = time.monotonic()
        await self._add_turn("user", text, data={"input": "text"})
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]},
            }
        )
        await self._send({"type": "response.create"})
        self._enqueue({"type": "user_turn", "text": text})

    # Inbound from xAI ---------------------------------------------------------------------------

    async def handle_xai_event(self, event: dict[str, Any]) -> None:
        etype = event.get("type", "")
        self._log_event("in", event)
        try:
            if etype in FORWARDED_UI_EVENTS:
                await self.emit({"type": "xai", "event": _slim(event)})
            if etype == "conversation.created":
                await self._set_conversation(xai_conversation_id=(event.get("conversation") or {}).get("id"))
            elif etype == "input_audio_buffer.speech_stopped":
                self._turn_started_at = time.monotonic()
            elif etype == "conversation.item.input_audio_transcription.completed":
                text = (event.get("transcript") or "").strip()
                if text:
                    await self._add_turn("user", text)
                    self._enqueue({"type": "user_turn", "text": text})
            elif etype == "response.created":
                rid = (event.get("response") or {}).get("id")
                if rid:
                    self._response_agent[rid] = self.active_slug
            elif etype in ("response.output_audio.delta", "response.audio.delta"):
                rid = event.get("response_id", "")
                if rid not in self._response_audio_seen:
                    self._response_audio_seen.add(rid)
                    self.deps.voice_locked = True
                    if self._turn_started_at is not None:
                        ms = int((time.monotonic() - self._turn_started_at) * 1000)
                        self._turn_started_at = None
                        self._ttfa.append(ms)
                        await self.emit({"type": "metric", "name": "time_to_first_audio_ms", "value": ms})
            elif etype == "response.output_audio_transcript.done":
                text = (event.get("transcript") or "").strip()
                slug = self._response_agent.get(event.get("response_id", ""), self.active_slug)
                if text:
                    await self._add_turn("assistant", text, slug=slug)
                    self._enqueue({"type": "assistant_turn", "text": text, "agent": slug})
                    if self.channel == "sip":
                        self.transport.estimate_playback(min(len(text) / 14.0, 30.0))
            elif etype == "response.function_call_arguments.done":
                if self._is_server_side(event.get("name", "")):
                    return
                self._pending_calls[event["call_id"]] = {
                    "call_id": event["call_id"],
                    "name": event.get("name", ""),
                    "arguments": event.get("arguments", "{}"),
                }
            elif etype == "response.done":
                for item in (event.get("response") or {}).get("output") or []:
                    if item.get("type") == "mcp_call" or (
                        item.get("type") == "function_call" and self._is_server_side(item.get("name", ""))
                    ):
                        await self._record_server_tool(item)
                        continue
                    if item.get("type") == "function_call" and item.get("call_id") not in self._pending_calls:
                        self._pending_calls[item["call_id"]] = {
                            "call_id": item["call_id"],
                            "name": item.get("name", ""),
                            "arguments": item.get("arguments", "{}"),
                        }
                if self._pending_calls:
                    calls = list(self._pending_calls.values())
                    self._pending_calls.clear()
                    self._enqueue({"type": "function_calls", "calls": calls})
            elif etype == "input_audio_buffer.dtmf_event_received":
                digit = str(event.get("event", ""))
                await self._add_turn("dtmf", digit)
                await self.emit({"type": "dtmf", "digit": digit})
            elif etype == "output_audio_buffer.started":
                self.transport.set_playing(True)
            elif etype in ("output_audio_buffer.stopped", "output_audio_buffer.cleared"):
                self.transport.set_playing(False)
            elif etype == "error":
                err = event.get("error") or {}
                log.warning("xAI realtime error in %s: %s", self.conversation_id, err)
                await self.emit(
                    {"type": "error", "source": "xai", "message": err.get("message", str(err)), "code": err.get("code")}
                )
        except Exception as exc:
            log.exception("Handling %s failed", etype)
            await self.emit({"type": "error", "source": "voicestack", "message": f"{etype}: {exc}"})

    # Graph invocation and actions ---------------------------------------------------------------

    # Recording ----------------------------------------------------------------------------------

    def _is_server_side(self, name: str) -> bool:
        toolset = self.deps._toolsets.get(self.active_slug)
        owned = set(toolset.executors) | set(toolset.handoffs) if toolset else set()
        return name in SERVER_SIDE_CALLS and name not in owned

    async def _record_server_tool(self, item: dict[str, Any]) -> None:
        name = item.get("name", "")
        label = item.get("server_label")
        data = {
            "server_side": True,
            "name": f"{label}.{name}" if label else name,
            "args": _parse_json(item.get("arguments")),
            "output": str(item.get("output") or "")[:4000],
            "ok": not item.get("error") and item.get("status") != "failed",
            "error": item.get("error"),
        }
        await self._add_turn("tool", data["name"], slug=self.active_slug, data=data)

    async def _send(self, event: dict[str, Any]) -> None:
        self._log_event("out", event)
        await self.transport.send(event)

    def _log_event(self, direction: str, event: dict[str, Any]) -> None:
        etype = event.get("type", "")
        if not self._record or etype in UNLOGGED_EVENTS:
            return
        payload = event
        if etype == "session.update":
            payload = {**event, "session": _redact_session(event.get("session") or {})}
        self._event_buf.append(
            ConversationEvent(conversation_id=self.conversation_id, direction=direction, type=etype[:80], payload=payload)
        )
        if len(self._event_buf) >= 25:
            asyncio.create_task(self._flush_events())

    async def _flush_events(self) -> None:
        if not self._event_buf:
            return
        batch, self._event_buf = self._event_buf, []
        try:
            async with session_scope() as db:
                db.add_all(batch)
        except Exception:
            log.exception("Could not store %d realtime events for %s", len(batch), self.conversation_id)

    def _config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.conversation_id}, "recursion_limit": 25}

    async def _invoke(self, event: dict[str, Any], initial: dict[str, Any] | None = None) -> None:
        async with self._lock:
            persistence = get_persistence()
            graph = get_graph(self.landscape, persistence.checkpointer, persistence.store)
            result = await graph.ainvoke({"event": event, **(initial or {})}, config=self._config(), context=self.deps)
            self.active_slug = result.get("active_agent") or self.active_slug
            actions = list(result.get("actions") or [])
        await self._perform(actions)

    async def _perform(self, actions: list[dict[str, Any]]) -> None:
        for action in actions:
            if self.closed:
                return
            kind = action["type"]
            if kind == "function_output":
                await self._send(
                    {
                        "type": "conversation.item.create",
                        "item": {"type": "function_call_output", "call_id": action["call_id"], "output": action["output"]},
                    }
                )
            elif kind == "session_update":
                await self._send({"type": "session.update", "session": action["session"]})
                await self.emit(
                    {"type": "session.config", "agent": action["agent"], "session": _redact_session(action["session"])}
                )
            elif kind == "seed_history":
                for item in action["items"]:
                    await self._send({"type": "conversation.item.create", "item": item})
            elif kind == "force_message":
                await self._send(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "force_message",
                            "role": "assistant",
                            "interruptible": action.get("interruptible", True),
                            "content": [{"type": "output_text", "text": action["text"]}],
                        },
                    }
                )
                await self._add_turn("assistant", action["text"], slug=self.active_slug, data={"force_message": True})
            elif kind in ("respond", "respond_after_playback"):
                if kind == "respond_after_playback":
                    await self.emit({"type": "thinking", "on": True})
                    await self.transport.wait_playback_idle()
                    await self.emit({"type": "thinking", "on": False})
                payload: dict[str, Any] = {"type": "response.create"}
                if action.get("instructions"):
                    payload["response"] = {"instructions": action["instructions"]}
                await self._send(payload)
            elif kind == "handoff":
                await self._record_handoff(action)
            elif kind == "end_after_playback":
                await self.transport.wait_playback_idle()
                await self.end(action.get("reason", "completed"))

    async def _record_handoff(self, action: dict[str, Any]) -> None:
        from_spec = self.landscape.agents.get(action["from"])
        to_spec = self.landscape.agents.get(action["to"])
        await self._add_turn(
            "handoff",
            f"{from_spec.name if from_spec else action['from']} → {to_spec.name if to_spec else action['to']}",
            slug=action["to"],
            data={k: action.get(k) for k in ("from", "to", "reason", "summary", "fields", "edge_id", "voice_policy")},
        )
        await self.emit({"type": "handoff", **{k: v for k, v in action.items() if k != "type"}})
        await self.emit({"type": "agent.active", "agent": action["to"], "reason": "handoff"})
        async with session_scope() as db:
            conv = await db.get(Conversation, self.conversation_id)
            if conv and to_spec:
                visited = list(conv.agents_visited or [])
                if to_spec.id not in visited:
                    visited.append(to_spec.id)
                conv.agents_visited = visited
                conv.last_agent_id = to_spec.id

    # Persistence and UI -------------------------------------------------------------------------

    async def _add_turn(self, kind: str, text: str, *, slug: str | None = None, data: dict[str, Any] | None = None) -> None:
        spec = self.landscape.agents.get(slug or self.active_slug)
        agent_id = spec.id if spec and kind != "user" else None
        async with session_scope() as db:
            if self._seq is None:
                self._seq = (
                    await db.execute(select(func.max(Turn.seq)).where(Turn.conversation_id == self.conversation_id))
                ).scalar() or 0
            self._seq += 1
            turn = Turn(
                conversation_id=self.conversation_id, seq=self._seq, kind=kind, agent_id=agent_id, text=text, data=data or {}
            )
            db.add(turn)
        await self.emit(
            {
                "type": "turn",
                "turn": {
                    "id": turn.id,
                    "seq": turn.seq,
                    "kind": kind,
                    "agent": slug if kind != "user" else None,
                    "agent_id": agent_id,
                    "text": text,
                    "data": data or {},
                },
            }
        )

    async def _set_conversation(self, **fields: Any) -> None:
        async with session_scope() as db:
            conv = await db.get(Conversation, self.conversation_id)
            if conv:
                for k, v in fields.items():
                    setattr(conv, k, v)

    async def emit(self, event: dict[str, Any]) -> None:
        if event.get("type") == "tool.finished":
            data = {k: event.get(k) for k in ("name", "args", "output", "ok", "latency_ms", "call_id")}
            await self._add_turn("tool", event.get("name", ""), slug=event.get("agent"), data={**data, "server_side": False})
        bus.publish(self.conversation_id, event)
        try:
            await self.transport.notify({"kind": "ui", "event": event})
        except Exception:
            log.debug("notify failed", exc_info=True)


def _parse_json(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


def _slim(event: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in event.items() if k not in ("delta", "audio")}


def _redact_session(session: dict[str, Any]) -> dict[str, Any]:
    """Session config for the UI inspector, without MCP credentials."""
    safe = json.loads(json.dumps(session))
    for tool in safe.get("tools", []):
        if tool.get("type") == "mcp":
            if "authorization" in tool:
                tool["authorization"] = "••••"
            if "headers" in tool:
                tool["headers"] = {k: "••••" for k in tool["headers"]}
    return safe
