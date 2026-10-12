"""Builds each agent's toolset for a live session.

Output has two halves:
- `realtime_tools`: the `tools` array for session.update (function schemas + server-side tools).
- `executors`: LangChain tools for every function tool Voice Stack runs itself.

Handoff tools (`transfer_to_<agent>`) are schemas only; the LangGraph runtime routes them.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from voicestack.config import get_settings
from voicestack.runtime.specs import AgentSpec, EdgeSpec, ToolSpec
from voicestack.tools import mcp as mcp_tools
from voicestack.tools.http_tool import run_http_tool
from voicestack.tools.plugins import get_plugin

log = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """Per-session dependencies a tool may need. Not checkpointed."""

    conversation_id: str
    channel: str
    call_id: str | None = None
    api_key: str | None = None
    wait_playback: Callable[[], Awaitable[None]] | None = None
    emit: Callable[[dict[str, Any]], Awaitable[None]] | None = None
    flags: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentToolset:
    realtime_tools: list[dict[str, Any]]
    executors: dict[str, BaseTool]
    handoffs: dict[str, EdgeSpec]
    errors: list[str] = field(default_factory=list)
    timeouts: dict[str, float] = field(default_factory=dict)


def _describe(description: str, preamble: str = "", confirm: bool = False) -> str:
    text = description.strip()
    if preamble.strip():
        text += f' Before calling, say a short line such as: "{preamble.strip()}"'
    if confirm:
        text += " This tool changes something: ask the caller to confirm before calling it."
    return text.strip()


def function_schema(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    params = parameters or {"type": "object", "properties": {}}
    params.setdefault("type", "object")
    params.setdefault("properties", {})
    if get_settings().realtime_function_tool_shape == "nested":
        return {"type": "function", "function": {"name": name, "description": description, "parameters": params}}
    return {"type": "function", "name": name, "description": description, "parameters": params}


def handoff_schema(edge: EdgeSpec) -> dict[str, Any]:
    props: dict[str, Any] = {
        "reason": {"type": "string", "description": "Why the caller needs this handoff."},
        "summary": {
            "type": "string",
            "description": "What the caller wants and what has happened so far, in one or two sentences.",
        },
    }
    required = ["reason", "summary"]
    for f in edge.context_fields:
        props[f.name] = {"type": f.type, "description": f.description or f.name}
        if f.required:
            required.append(f.name)
    when = edge.description.strip() or f"the caller needs {edge.target_name}"
    return function_schema(
        edge.tool_name,
        f"Hand the conversation to {edge.target_name}. Use when {when.rstrip('.')}.",
        {"type": "object", "properties": props, "required": required},
    )


def _http_tool(spec: ToolSpec) -> StructuredTool:
    async def run(**kwargs: Any) -> str:
        return json.dumps(await run_http_tool(spec.config, kwargs), ensure_ascii=False)

    return StructuredTool.from_function(
        coroutine=run,
        name=spec.name,
        description=_describe(spec.description, spec.preamble, spec.requires_confirmation),
        args_schema=spec.parameters or {"type": "object", "properties": {}},
    )


def _search_knowledge_tool(agent: AgentSpec) -> StructuredTool:
    from voicestack.knowledge.ingest import search_local

    local = [k for k in agent.knowledge if k.mode == "local"]
    names = ", ".join(k.name for k in local)
    top_k = max((k.top_k for k in local), default=4)

    async def run(query: str) -> str:
        results = await search_local([k.id for k in local], query, k=top_k)
        if not results:
            return json.dumps({"results": [], "note": "No matching passages. Tell the caller you do not know."})
        return json.dumps({"results": results}, ensure_ascii=False)

    return StructuredTool.from_function(
        coroutine=run,
        name="search_knowledge",
        description=f"Search the knowledge base ({names}) for passages that answer the caller's question.",
        args_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "A focused search query in the caller's words."}},
            "required": ["query"],
        },
    )


def _transfer_call_tool(agent: AgentSpec, ctx: ToolContext) -> StructuredTool:
    targets = {t.name: t for t in agent.transfers}

    async def run(destination: str, reason: str = "") -> str:
        target = targets.get(destination)
        if not target:
            return json.dumps({"ok": False, "error": f"Unknown destination. Choose one of: {', '.join(targets)}"})
        if ctx.wait_playback:
            await ctx.wait_playback()
        if ctx.emit:
            await ctx.emit({"type": "transfer.started", "destination": target.name, "uri": target.uri, "reason": reason})
        if ctx.channel != "sip" or not ctx.call_id:
            result = {
                "ok": True,
                "simulated": True,
                "destination": target.name,
                "note": "Preview session: the transfer was simulated. On a phone call this sends a SIP REFER.",
            }
        else:
            from voicestack.xai.client import XAIClient

            async with XAIClient(ctx.api_key or "") as client:
                outcome = await client.refer_call(ctx.call_id, target.uri)
            result = {"destination": target.name, **outcome}
            if outcome["ok"]:
                ctx.flags["transferred"] = True
        if ctx.emit:
            await ctx.emit({"type": "transfer.finished", **result})
        return json.dumps(result)

    return StructuredTool.from_function(
        coroutine=run,
        name="transfer_call",
        description="Transfer the caller to a person or phone line. Say a short line such as "
        '"I\'m connecting you now." at the same time as calling this tool.',
        args_schema={
            "type": "object",
            "properties": {
                "destination": {"type": "string", "enum": list(targets), "description": "Where to transfer the caller."},
                "reason": {"type": "string", "description": "Why the caller is being transferred."},
            },
            "required": ["destination"],
        },
    )


def _end_call_tool(ctx: ToolContext) -> StructuredTool:
    async def run(reason: str = "") -> str:
        ctx.flags["end_requested"] = reason or "completed"
        return json.dumps({"ok": True, "status": "ending"})

    return StructuredTool.from_function(
        coroutine=run,
        name="end_call",
        description="End the conversation after you have said goodbye.",
        args_schema={"type": "object", "properties": {"reason": {"type": "string"}}},
    )


# In realtime sessions the native x_search tool hands its inner tools (x_keyword_search, …) to the
# client as function calls and does not run them, and the model tends to announce failure before
# calling (verified live, see docs/xai-api-notes.md). Voice Stack therefore offers `x_search` as its
# own function tool, backed by the Responses API's x_search, which works reliably.
def _x_search_tool(agent: AgentSpec, ctx: ToolContext) -> StructuredTool:
    config = agent.builtin_tools.get("x_search") or {}

    async def run(query: str) -> str:
        import httpx

        tool: dict[str, Any] = {"type": "x_search"}
        for key in ("allowed_x_handles", "excluded_x_handles", "from_date", "to_date"):
            if config.get(key):
                tool[key] = config[key]
        body = {
            "model": get_settings().text_model,
            "reasoning": {"effort": "low"},
            "tools": [tool],
            "input": [
                {
                    "role": "user",
                    "content": f"Search posts on X for: {query}\nSummarize what the matching posts say in under 80 words, "
                    "naming the author handle and date of each. If nothing matches, say so.",
                }
            ],
        }
        async with httpx.AsyncClient(base_url=get_settings().xai_api_base, timeout=90) as client:
            resp = await client.post("/v1/responses", json=body, headers={"Authorization": f"Bearer {ctx.api_key}"})
        if resp.status_code >= 400:
            return json.dumps({"ok": False, "error": f"X search failed ({resp.status_code})"})
        texts = [
            c.get("text", "") for o in resp.json().get("output", []) if o.get("type") == "message" for c in o.get("content", [])
        ]
        return json.dumps({"ok": True, "results": " ".join(texts).strip() or "No matching posts."}, ensure_ascii=False)

    handles = config.get("allowed_x_handles") or []
    scope = f" Limited to posts from: {', '.join('@' + h.lstrip('@') for h in handles)}." if handles else ""
    return StructuredTool.from_function(
        coroutine=run,
        name="x_search",
        description=f"Search recent posts on X (Twitter) and get a short summary with authors and dates.{scope}",
        args_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to look for, in plain words or X search syntax."}},
            "required": ["query"],
        },
    )


def _builtin_server_tools(agent: AgentSpec) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    web = agent.builtin_tools.get("web_search") or {}
    if web.get("enabled"):
        entry: dict[str, Any] = {"type": "web_search"}
        for key in ("allowed_domains", "excluded_domains"):
            if web.get(key):
                entry[key] = web[key][:5]
        if web.get("enable_image_understanding"):
            entry["enable_image_understanding"] = True
        location = {k: v for k, v in (web.get("location") or {}).items() if v}
        if location:
            entry["location"] = location
        out.append(entry)
    collections = [k for k in agent.knowledge if k.mode == "collections" and k.collection_id]
    if collections:
        out.append(
            {
                "type": "file_search",
                "vector_store_ids": [k.collection_id for k in collections],
                "max_num_results": max(k.top_k for k in collections),
            }
        )
    return out


async def build_toolset(agent: AgentSpec, ctx: ToolContext) -> AgentToolset:
    settings = get_settings()
    executors: dict[str, BaseTool] = {}
    errors: list[str] = []
    timeouts: dict[str, float] = {}

    for spec in agent.tools:
        if spec.kind == "http":
            executors[spec.name] = _http_tool(spec)
            timeouts[spec.name] = float(spec.config.get("timeout_s") or settings.tool_timeout_s) + 2
        elif plugin := get_plugin(spec.name):
            executors[spec.name] = plugin
        else:
            errors.append(f"Plugin tool {spec.name!r} is not installed")
    if any(k.mode == "local" for k in agent.knowledge):
        executors["search_knowledge"] = _search_knowledge_tool(agent)
    if agent.transfers:
        executors["transfer_call"] = _transfer_call_tool(agent, ctx)
        timeouts["transfer_call"] = 120.0  # SIP REFER blocks until the destination answers
    if agent.allow_end_call:
        executors["end_call"] = _end_call_tool(ctx)
    try:
        for t in await mcp_tools.managed_tools(agent.mcps):
            if t.name not in executors:
                executors[t.name] = t
                timeouts[t.name] = settings.mcp_tool_timeout_s
    except Exception as exc:
        errors.append(f"Managed MCP: {exc}")

    if (agent.builtin_tools.get("x_search") or {}).get("enabled"):
        executors["x_search"] = _x_search_tool(agent, ctx)
        timeouts["x_search"] = 90.0

    realtime: list[dict[str, Any]] = []
    for name, t in executors.items():
        oai = convert_to_openai_tool(t)["function"]
        spec_match = next((s for s in agent.tools if s.name == name), None)
        desc = oai.get("description", "")
        if spec_match and spec_match.kind == "plugin":
            desc = _describe(desc, spec_match.preamble, spec_match.requires_confirmation)
        realtime.append(function_schema(name, desc, oai.get("parameters", {})))
    handoffs = {e.tool_name: e for e in agent.edges}
    realtime += [handoff_schema(e) for e in agent.edges]
    realtime += _builtin_server_tools(agent)
    for m in agent.mcps:
        if m.mode == "xai":
            try:
                realtime.append(await mcp_tools.xai_tool_entry(m))
            except Exception as exc:
                errors.append(f"MCP {m.label}: {exc}")
    return AgentToolset(realtime_tools=realtime, executors=executors, handoffs=handoffs, errors=errors, timeouts=timeouts)


async def run_tool(tool: BaseTool, call_id: str, args: dict[str, Any], timeout: float) -> tuple[str, bool]:
    """Run a LangChain tool; returns (output_text, ok). Errors become outputs the model can speak about."""
    try:
        msg = await asyncio.wait_for(
            tool.ainvoke({"type": "tool_call", "id": call_id, "name": tool.name, "args": args}), timeout=timeout
        )
        content = getattr(msg, "content", msg)
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)
        return text, getattr(msg, "status", "success") != "error"
    except TimeoutError:
        return json.dumps({"ok": False, "error": f"The tool timed out after {timeout:.0f}s"}), False
    except Exception as exc:
        log.exception("Tool %s failed", tool.name)
        return json.dumps({"ok": False, "error": str(exc)[:500]}), False
