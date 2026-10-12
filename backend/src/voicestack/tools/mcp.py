"""MCP connectors in two modes.

- "xai": passthrough. The server is listed in session.tools as {"type": "mcp", ...} and xAI calls it.
  Lowest latency; the server must be publicly reachable over Streamable HTTP or SSE.
- "managed": Voice Stack connects with langchain-mcp-adapters and exposes the server's tools to the
  voice model as function tools. Works with stdio and private-network servers.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from voicestack.runtime.specs import McpSpec
from voicestack.security.ssrf import check_url
from voicestack.tools.secrets import get_secret

log = logging.getLogger(__name__)


async def _headers(spec: McpSpec) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header, secret_name in spec.header_secrets.items():
        value = await get_secret(secret_name)
        if value is None:
            raise KeyError(f"MCP server {spec.label}: secret {secret_name!r} not found")
        headers[header] = value
    return headers


async def _authorization(spec: McpSpec) -> str | None:
    if not spec.authorization_secret:
        return None
    value = await get_secret(spec.authorization_secret)
    if value is None:
        raise KeyError(f"MCP server {spec.label}: secret {spec.authorization_secret!r} not found")
    return value


async def xai_tool_entry(spec: McpSpec) -> dict[str, Any]:
    entry: dict[str, Any] = {"type": "mcp", "server_url": spec.url, "server_label": spec.label}
    if spec.description:
        entry["server_description"] = spec.description
    if spec.allowed_tools:
        entry["allowed_tools"] = spec.allowed_tools
    if auth := await _authorization(spec):
        entry["authorization"] = auth
    if headers := await _headers(spec):
        entry["headers"] = headers
    return entry


async def _connection(spec: McpSpec) -> dict[str, Any]:
    if spec.transport == "stdio":
        return {"transport": "stdio", "command": spec.command, "args": spec.args}
    await check_url(spec.url)
    headers = await _headers(spec)
    if auth := await _authorization(spec):
        headers["Authorization"] = auth if auth.lower().startswith(("bearer ", "basic ")) else f"Bearer {auth}"
    transport = "sse" if spec.transport == "sse" else "streamable_http"
    conn: dict[str, Any] = {"transport": transport, "url": spec.url}
    if headers:
        conn["headers"] = headers
    return conn


async def managed_tools(specs: list[McpSpec]) -> list[BaseTool]:
    managed = [s for s in specs if s.mode == "managed"]
    if not managed:
        return []
    connections = {s.label: await _connection(s) for s in managed}
    client = MultiServerMCPClient(connections)
    tools: list[BaseTool] = []
    for spec in managed:
        try:
            server_tools = await client.get_tools(server_name=spec.label)
        except Exception:
            log.exception("MCP server %s: tool discovery failed", spec.label)
            continue
        for t in server_tools:
            if spec.allowed_tools and t.name not in spec.allowed_tools:
                continue
            tools.append(t)
    return tools


async def discover(spec: McpSpec) -> list[dict[str, Any]]:
    """List a server's tools for the UI, in either mode (used to fill allowed_tools)."""
    if spec.transport != "stdio":
        await check_url(spec.url)
    client = MultiServerMCPClient({spec.label: await _connection(spec)})
    tools = await client.get_tools(server_name=spec.label)
    return [{"name": t.name, "description": t.description or ""} for t in tools]
