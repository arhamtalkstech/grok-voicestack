from __future__ import annotations

import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.api.common import get_or_404, snake_name, to_dict
from voicestack.db.models import McpServer, Secret, Tool, TransferTarget
from voicestack.db.session import get_db
from voicestack.runtime.specs import McpSpec
from voicestack.security.ssrf import BlockedDestination
from voicestack.tools import mcp as mcp_tools
from voicestack.tools.http_tool import run_http_tool
from voicestack.tools.plugins import get_plugin, list_plugins
from voicestack.tools.secrets import put_secret

router = APIRouter(prefix="/api", tags=["integrations"])


# HTTP + plugin tools ------------------------------------------------------------------------------


class ToolIn(BaseModel):
    name: str
    kind: Literal["http", "plugin"] = "http"
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    config: dict[str, Any] = Field(default_factory=dict)
    preamble: str = ""
    requires_confirmation: bool = False
    enabled: bool = True


def _validate_tool(body: ToolIn) -> dict[str, Any]:
    data = body.model_dump()
    data["name"] = body.name if body.kind == "plugin" else snake_name(body.name)
    if body.kind == "http":
        url = body.config.get("url", "")
        if not url.startswith(("http://", "https://")):
            raise HTTPException(422, "HTTP tools need a URL starting with http:// or https://")
        if body.parameters.get("type") != "object":
            raise HTTPException(422, "Parameters must be a JSON Schema object")
    elif not get_plugin(body.name):
        raise HTTPException(422, f"No installed plugin tool named {body.name!r}")
    return data


@router.get("/tools")
async def list_tools(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return [to_dict(t) for t in (await db.execute(select(Tool).order_by(Tool.name))).scalars()]


@router.post("/tools", status_code=201)
async def create_tool(body: ToolIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    data = _validate_tool(body)
    if (await db.execute(select(Tool).where(Tool.name == data["name"]))).scalar_one_or_none():
        raise HTTPException(409, f"A tool named {data['name']} already exists")
    tool = Tool(**data)
    db.add(tool)
    await db.flush()
    return to_dict(tool)


@router.put("/tools/{tool_id}")
async def update_tool(tool_id: str, body: ToolIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    tool = await get_or_404(db, Tool, tool_id)
    for k, v in _validate_tool(body).items():
        setattr(tool, k, v)
    await db.flush()
    return to_dict(tool)


@router.delete("/tools/{tool_id}", status_code=204)
async def delete_tool(tool_id: str, db: AsyncSession = Depends(get_db)) -> None:
    await db.delete(await get_or_404(db, Tool, tool_id))


@router.post("/tools/{tool_id}/test")
async def test_tool(tool_id: str, args: dict[str, Any], db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    tool = await get_or_404(db, Tool, tool_id)
    started = time.monotonic()
    try:
        if tool.kind == "http":
            result = await run_http_tool(tool.config, args)
        else:
            plugin = get_plugin(tool.name)
            if not plugin:
                raise HTTPException(422, "Plugin is not installed")
            result = {"ok": True, "result": await plugin.ainvoke(args)}
    except BlockedDestination as exc:
        result = {"ok": False, "error": str(exc)}
    except KeyError as exc:
        result = {"ok": False, "error": str(exc)}
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {**result, "latency_ms": int((time.monotonic() - started) * 1000)}


@router.get("/plugins")
async def plugins() -> list[dict[str, Any]]:
    return list_plugins()


# MCP servers --------------------------------------------------------------------------------------


class McpIn(BaseModel):
    label: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str = ""
    mode: Literal["xai", "managed"] = "xai"
    transport: Literal["streamable_http", "sse", "stdio"] = "streamable_http"
    url: str = ""
    command: str = ""
    args: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    authorization_secret: str | None = None
    header_secrets: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


def _validate_mcp(body: McpIn) -> None:
    if body.mode == "xai" and body.transport == "stdio":
        raise HTTPException(422, "xAI-hosted MCP needs a public Streamable HTTP or SSE URL. Use managed mode for stdio servers.")
    if body.transport != "stdio" and not body.url.startswith(("http://", "https://")):
        raise HTTPException(422, "Enter the server URL (http:// or https://)")
    if body.transport == "stdio" and not body.command:
        raise HTTPException(422, "stdio servers need a command")


@router.get("/mcp")
async def list_mcp(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return [to_dict(m) for m in (await db.execute(select(McpServer).order_by(McpServer.label))).scalars()]


@router.post("/mcp", status_code=201)
async def create_mcp(body: McpIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    _validate_mcp(body)
    if (await db.execute(select(McpServer).where(McpServer.label == body.label))).scalar_one_or_none():
        raise HTTPException(409, f"An MCP server labelled {body.label} already exists")
    row = McpServer(**body.model_dump())
    db.add(row)
    await db.flush()
    return to_dict(row)


@router.put("/mcp/{mcp_id}")
async def update_mcp(mcp_id: str, body: McpIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    _validate_mcp(body)
    row = await get_or_404(db, McpServer, mcp_id)
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    await db.flush()
    return to_dict(row)


@router.delete("/mcp/{mcp_id}", status_code=204)
async def delete_mcp(mcp_id: str, db: AsyncSession = Depends(get_db)) -> None:
    await db.delete(await get_or_404(db, McpServer, mcp_id))


@router.post("/mcp/{mcp_id}/discover")
async def discover_mcp(mcp_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await get_or_404(db, McpServer, mcp_id)
    spec = McpSpec(**{k: getattr(row, k) for k in McpSpec.model_fields if hasattr(row, k)})
    started = time.monotonic()
    try:
        tools = await mcp_tools.discover(spec)
    except Exception as exc:
        detail = str(exc)
        if hasattr(exc, "exceptions"):
            detail = "; ".join(str(e) for e in exc.exceptions)
        return {"ok": False, "error": detail[:800], "tools": []}
    return {"ok": True, "tools": tools, "latency_ms": int((time.monotonic() - started) * 1000)}


# Secrets ------------------------------------------------------------------------------------------


class SecretIn(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,120}$")
    value: str = Field(min_length=1)


@router.get("/secrets")
async def list_secrets(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.execute(select(Secret).order_by(Secret.name))).scalars()
    return [{"name": r.name, "last4": r.last4, "updated_at": to_dict(r)["updated_at"]} for r in rows]


@router.put("/secrets")
async def set_secret(body: SecretIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await put_secret(db, body.name, body.value)
    return {"name": row.name, "last4": row.last4}


@router.delete("/secrets/{name}", status_code=204)
async def delete_secret(name: str, db: AsyncSession = Depends(get_db)) -> None:
    row = (await db.execute(select(Secret).where(Secret.name == name))).scalar_one_or_none()
    if row:
        await db.delete(row)


# Transfer targets ---------------------------------------------------------------------------------


class TransferIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    uri: str = Field(pattern=r"^(tel:\+\d{6,15}|sip:[^@\s]+@[^\s]+)$")
    description: str = ""


@router.get("/transfer-targets")
async def list_targets(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return [to_dict(t) for t in (await db.execute(select(TransferTarget).order_by(TransferTarget.name))).scalars()]


@router.post("/transfer-targets", status_code=201)
async def create_target(body: TransferIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = TransferTarget(**body.model_dump())
    db.add(row)
    await db.flush()
    return to_dict(row)


@router.put("/transfer-targets/{target_id}")
async def update_target(target_id: str, body: TransferIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await get_or_404(db, TransferTarget, target_id)
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    await db.flush()
    return to_dict(row)


@router.delete("/transfer-targets/{target_id}", status_code=204)
async def delete_target(target_id: str, db: AsyncSession = Depends(get_db)) -> None:
    await db.delete(await get_or_404(db, TransferTarget, target_id))
