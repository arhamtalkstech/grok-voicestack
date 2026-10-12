"""The LangGraph runtime: one graph per landscape, one checkpointed thread per conversation.

Shape (swarm pattern): START -> ingest -> <active agent> [-> <handoff target>] -> END
                       ingest -> post_call -> END (when the call ends)

The realtime model runs the dialog. This graph is the control plane around it: it executes
function tools, routes handoffs with Command(goto=...), keeps the cross-agent message history, and
writes contact memory after the call. Nodes return `actions`, which the SessionController turns
into realtime events (session.update, function_call_output, response.create, force_message).
"""

from __future__ import annotations

import asyncio
import json
import logging
import operator
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_xai import ChatXAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.types import Command
from pydantic import BaseModel, Field

from voicestack.config import get_settings
from voicestack.prompting.compiler import HandoffContext
from voicestack.runtime.session_config import greeting_directive, handoff_directive, render_session
from voicestack.runtime.specs import AgentSpec, LandscapeSpec
from voicestack.tools.registry import AgentToolset, ToolContext, build_toolset, run_tool

log = logging.getLogger(__name__)
RESERVED_NODES = {"ingest", "post_call"}


def merge_dicts(a: dict | None, b: dict | None) -> dict:
    return {**(a or {}), **(b or {})}


def actions_reducer(a: list | None, b: list | None) -> list:
    if b is None:
        return []
    return [*(a or []), *b]


class VoiceState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    active_agent: str
    context: Annotated[dict[str, Any], merge_dicts]
    handoffs: Annotated[list[dict[str, Any]], operator.add]
    event: dict[str, Any]
    actions: Annotated[list[dict[str, Any]], actions_reducer]
    arrival: dict[str, Any] | None
    channel: str
    contact_id: str | None
    caller_context: str | None
    call_summary: dict[str, Any] | None


@dataclass
class RuntimeDeps:
    """Per-session runtime context (LangGraph `context_schema`); never checkpointed."""

    landscape: LandscapeSpec
    tool_ctx: ToolContext
    store: BaseStore
    api_key: str | None = None
    disclosure: str | None = None
    voice_locked: bool = False
    _toolsets: dict[str, AgentToolset] = field(default_factory=dict)

    async def toolset(self, slug: str) -> AgentToolset:
        if slug not in self._toolsets:
            ts = await build_toolset(self.landscape.agents[slug], self.tool_ctx)
            for err in ts.errors:
                await self.emit({"type": "tool.config_error", "agent": slug, "message": err})
            self._toolsets[slug] = ts
        return self._toolsets[slug]

    def invalidate(self) -> None:
        self._toolsets.clear()

    async def emit(self, event: dict[str, Any]) -> None:
        if self.tool_ctx.emit:
            await self.tool_ctx.emit(event)


# Nodes ------------------------------------------------------------------------------------------


async def ingest(state: VoiceState, runtime: Runtime[RuntimeDeps]) -> Command:
    ev = state.get("event") or {}
    kind = ev.get("type")
    reset: dict[str, Any] = {"actions": None}
    active = state.get("active_agent")
    if kind == "user_turn":
        return Command(goto=END, update={**reset, "messages": [HumanMessage(ev["text"])]})
    if kind == "assistant_turn":
        return Command(goto=END, update={**reset, "messages": [AIMessage(ev["text"], name=ev.get("agent") or active)]})
    if kind in ("start", "refresh"):
        return Command(goto=active, update={**reset, "arrival": {"kind": kind, "resume": bool(ev.get("resume"))}})
    if kind == "function_calls":
        return Command(goto=active, update=reset)
    if kind == "end":
        return Command(goto="post_call", update=reset)
    return Command(goto=END, update=reset)


def _include_voice(kind: str, voice_policy: str | None, deps: RuntimeDeps) -> bool:
    if kind == "start":
        return True
    if kind == "handoff" and voice_policy == "keep":
        return False
    if get_settings().handoff_voice_mode == "keep" and deps.voice_locked:
        return False
    return True


def _parse_args(raw: str | dict | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def make_agent_node(slug: str):
    async def agent_node(state: VoiceState, runtime: Runtime[RuntimeDeps]) -> Command:
        deps = runtime.context
        agent: AgentSpec = deps.landscape.agents[slug]
        toolset = await deps.toolset(slug)
        channel = state.get("channel", "web")

        arrival = state.get("arrival")
        if arrival:
            kind = arrival.get("kind", "start")
            handoff = HandoffContext(**arrival["handoff"]) if kind == "handoff" else None
            include_voice = _include_voice(kind, arrival.get("voice_policy"), deps)
            session = render_session(
                agent,
                toolset.realtime_tools,
                channel=channel,
                include_voice=include_voice,
                handoff=handoff,
                caller_context=state.get("caller_context"),
            )
            actions: list[dict[str, Any]] = [{"type": "session_update", "session": session, "agent": slug}]
            if kind == "start" and arrival.get("resume"):
                items = history_items(state.get("messages") or [])
                if items:
                    actions.append({"type": "seed_history", "items": items})
                actions.append({"type": "respond", "instructions": session["instructions"] + "\n\n" + RESUME_DIRECTIVE})
            elif kind == "start":
                if deps.disclosure:
                    actions.append({"type": "force_message", "text": deps.disclosure, "interruptible": False})
                if agent.greeting_mode == "verbatim" and agent.greeting.strip():
                    actions.append(
                        {"type": "force_message", "text": agent.greeting.strip(), "interruptible": agent.greeting_interruptible}
                    )
                elif agent.greeting_mode == "model":
                    actions.append(
                        {"type": "respond", "instructions": session["instructions"] + "\n\n" + greeting_directive(agent)}
                    )
            elif kind == "handoff" and handoff:
                actions.append(
                    {
                        "type": "respond_after_playback",
                        "instructions": session["instructions"] + "\n\n" + handoff_directive(agent, handoff),
                    }
                )
            return Command(goto=END, update={"arrival": None, "actions": actions})

        ev = state.get("event") or {}
        if ev.get("type") != "function_calls":
            return Command(goto=END)

        calls = [{**c, "args": _parse_args(c.get("arguments"))} for c in ev.get("calls", [])]
        ai = AIMessage(
            content="",
            name=slug,
            tool_calls=[{"id": c["call_id"], "name": c["name"], "args": c["args"], "type": "tool_call"} for c in calls],
        )
        handoff_calls = [c for c in calls if c["name"] in toolset.handoffs]
        regular = [c for c in calls if c["name"] not in toolset.handoffs]
        timeout = get_settings().tool_timeout_s

        async def run_one(call: dict[str, Any]) -> tuple[dict[str, Any], str, bool]:
            started = time.monotonic()
            await deps.emit(
                {"type": "tool.started", "agent": slug, "call_id": call["call_id"], "name": call["name"], "args": call["args"]}
            )
            tool = toolset.executors.get(call["name"])
            if tool is None:
                output, ok = json.dumps({"ok": False, "error": f"Unknown tool {call['name']}"}), False
            else:
                output, ok = await run_tool(tool, call["call_id"], call["args"], toolset.timeouts.get(call["name"], timeout))
            await deps.emit(
                {
                    "type": "tool.finished",
                    "agent": slug,
                    "call_id": call["call_id"],
                    "name": call["name"],
                    "args": call["args"],
                    "ok": ok,
                    "output": output[:4000],
                    "latency_ms": int((time.monotonic() - started) * 1000),
                }
            )
            return call, output, ok

        results = await asyncio.gather(*(run_one(c) for c in regular))
        messages: list[AnyMessage] = [ai]
        actions = []
        for call, output, ok in results:
            messages.append(
                ToolMessage(output, tool_call_id=call["call_id"], name=call["name"], status="success" if ok else "error")
            )
            actions.append({"type": "function_output", "call_id": call["call_id"], "output": output})

        accepted: dict[str, Any] | None = None
        for call in handoff_calls:
            edge = toolset.handoffs[call["name"]]
            args = call["args"]
            missing = [f.name for f in edge.context_fields if f.required and args.get(f.name) in (None, "")]
            if accepted is not None:
                output = {"ok": False, "error": "Only one handoff can happen at a time."}
            elif edge.target_slug not in deps.landscape.agents:
                output = {"ok": False, "error": f"{edge.target_name} is not available."}
            elif missing:
                output = {"ok": False, "error": f"Ask the caller for these details first: {', '.join(missing)}."}
            else:
                output = {"ok": True, "transferred_to": edge.target_name}
                accepted = {"call": call, "edge": edge}
            text = json.dumps(output)
            messages.append(
                ToolMessage(text, tool_call_id=call["call_id"], name=call["name"], status="success" if output["ok"] else "error")
            )
            actions.append({"type": "function_output", "call_id": call["call_id"], "output": text})

        if accepted:
            edge, args = accepted["edge"], accepted["call"]["args"]
            fields = {f.name: args[f.name] for f in edge.context_fields if args.get(f.name) not in (None, "")}
            merged = {**(state.get("context") or {}), **fields}
            event = {
                "from": slug,
                "to": edge.target_slug,
                "edge_id": edge.id,
                "reason": args.get("reason", ""),
                "summary": args.get("summary", ""),
                "fields": fields,
                "voice_policy": edge.voice_policy,
                "at": datetime.now(UTC).isoformat(),
            }
            actions.append({"type": "handoff", **event})
            arrival = {
                "kind": "handoff",
                "voice_policy": edge.voice_policy,
                "handoff": {
                    "from_agent": agent.name,
                    "reason": event["reason"],
                    "summary": event["summary"],
                    "fields": merged,
                    "greeting": edge.handoff_greeting,
                },
            }
            return Command(
                goto=edge.target_slug,
                update={
                    "messages": messages,
                    "actions": actions,
                    "active_agent": edge.target_slug,
                    "arrival": arrival,
                    "context": fields,
                    "handoffs": [event],
                },
            )

        flags = deps.tool_ctx.flags
        if flags.pop("transferred", False):
            actions.append({"type": "end_after_playback", "reason": "transferred"})
        elif reason := flags.pop("end_requested", None):
            actions.append({"type": "end_after_playback", "reason": reason})
        else:
            actions.append({"type": "respond_after_playback"})
        return Command(goto=END, update={"messages": messages, "actions": actions})

    return agent_node


RESUME_DIRECTIVE = (
    "For this turn only: the caller is returning to an earlier conversation, shown above. Welcome them back "
    "in one short sentence and pick up where it left off."
)


def history_items(messages: list[AnyMessage], limit: int = 40) -> list[dict[str, Any]]:
    """Prior transcript as realtime conversation items (text only) for seeding a new session."""
    items: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m, HumanMessage) and m.content:
            items.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": str(m.content)}]})
        elif isinstance(m, AIMessage) and m.content:
            items.append({"type": "message", "role": "assistant", "content": [{"type": "text", "text": str(m.content)}]})
    return items[-limit:]


class Fact(BaseModel):
    key: str
    value: str


class CallSummary(BaseModel):
    summary: str = Field(description="Two or three sentences: what the caller wanted and how it ended")
    disposition: Literal["resolved", "transferred", "escalated", "abandoned", "follow_up", "other"]
    caller_facts: list[Fact] = Field(
        description="Stable facts about the caller worth remembering next time (name, account id, preferences). Empty if none."
    )
    extracted: list[Fact] = Field(description="Structured details collected during the call (order ids, dates, amounts).")


def transcript_text(messages: list[AnyMessage]) -> str:
    lines = []
    for m in messages:
        if isinstance(m, HumanMessage):
            lines.append(f"Caller: {m.content}")
        elif isinstance(m, AIMessage) and m.content:
            lines.append(f"Agent ({m.name or 'agent'}): {m.content}")
        elif isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                lines.append(f"[tool call {tc['name']} {json.dumps(tc['args'])[:300]}]")
        elif isinstance(m, ToolMessage):
            lines.append(f"[tool result {m.name}: {str(m.content)[:300]}]")
    return "\n".join(lines)


async def post_call(state: VoiceState, runtime: Runtime[RuntimeDeps]) -> dict[str, Any]:
    deps = runtime.context
    messages = state.get("messages") or []
    if not deps.api_key or not any(isinstance(m, HumanMessage) for m in messages):
        return {"call_summary": None}
    settings = get_settings()
    llm = ChatXAI(model=settings.text_model, api_key=deps.api_key, reasoning_effort="low", timeout=120, max_retries=2)
    try:
        result: CallSummary = await llm.with_structured_output(CallSummary, method="json_schema").ainvoke(
            "Summarize this voice conversation for a support team. Handoffs between agents are part of one "
            f"conversation.\n\nContext collected: {json.dumps(state.get('context') or {})}\n\n"
            f"{transcript_text(messages)}"
        )
    except Exception:
        log.exception("Post-call summary failed")
        return {"call_summary": None}
    summary = result.model_dump()
    contact_id = state.get("contact_id")
    if contact_id:
        await remember(deps.store, contact_id, summary, deps.tool_ctx.conversation_id)
    return {"call_summary": summary}


# Contact memory ---------------------------------------------------------------------------------

MEMORY_NS = "contacts"


async def remember(store: BaseStore, contact_id: str, summary: dict[str, Any], conversation_id: str) -> None:
    from voicestack.runtime.persistence import get_persistence

    async with get_persistence().store_lock:
        await _remember(store, contact_id, summary, conversation_id)


async def _remember(store: BaseStore, contact_id: str, summary: dict[str, Any], conversation_id: str) -> None:
    item = await store.aget((MEMORY_NS, contact_id), "profile")
    profile = dict(item.value) if item else {"facts": {}, "conversations": []}
    for fact in summary.get("caller_facts", []):
        profile["facts"][fact["key"]] = fact["value"]
    profile["conversations"] = [
        {"conversation_id": conversation_id, "date": datetime.now(UTC).date().isoformat(), "summary": summary["summary"]},
        *profile.get("conversations", []),
    ][:5]
    await store.aput((MEMORY_NS, contact_id), "profile", profile)


async def recall(store: BaseStore, contact_id: str) -> str | None:
    from voicestack.runtime.persistence import get_persistence

    async with get_persistence().store_lock:
        item = await store.aget((MEMORY_NS, contact_id), "profile")
    if not item:
        return None
    profile = item.value
    lines = ["This caller has spoken with us before. Use this only if relevant; do not read it out."]
    facts = profile.get("facts") or {}
    if facts:
        lines.append("Known details: " + "; ".join(f"{k}: {v}" for k, v in facts.items()))
    for conv in profile.get("conversations", [])[:3]:
        lines.append(f"- {conv['date']}: {conv['summary']}")
    return "\n".join(lines)


# Graph assembly ---------------------------------------------------------------------------------

_compiled: dict[str, Any] = {}


def build_graph(landscape: LandscapeSpec, checkpointer=None, store=None):
    graph = StateGraph(VoiceState, context_schema=RuntimeDeps)
    slugs = list(landscape.agents)
    graph.add_node("ingest", ingest, destinations=(*slugs, "post_call", END))
    for slug in slugs:
        targets = tuple(e.target_slug for e in landscape.agents[slug].edges if e.target_slug in landscape.agents)
        graph.add_node(slug, make_agent_node(slug), destinations=(*targets, END))
    graph.add_node("post_call", post_call)
    graph.add_edge(START, "ingest")
    graph.add_edge("post_call", END)
    return graph.compile(checkpointer=checkpointer, store=store)


def get_graph(landscape: LandscapeSpec, checkpointer, store):
    key = landscape.fingerprint()
    if key not in _compiled:
        _compiled[key] = build_graph(landscape, checkpointer, store)
        if len(_compiled) > 64:
            _compiled.pop(next(iter(_compiled)))
    return _compiled[key]
