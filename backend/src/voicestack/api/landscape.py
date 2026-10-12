from __future__ import annotations

from typing import Any, Literal

import yaml
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.api.common import get_or_404, slugify, to_dict
from voicestack.db.models import Agent, HandoffEdge, KnowledgeBase, McpServer, PhoneNumber, Tool, TransferTarget
from voicestack.db.session import get_db
from voicestack.runtime.specs import ContextField

router = APIRouter(prefix="/api", tags=["landscape"])


@router.get("/landscape")
async def get_landscape(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    agents = (await db.execute(select(Agent).order_by(Agent.created_at))).scalars().all()
    edges = (await db.execute(select(HandoffEdge))).scalars().all()
    tools = {t.id: t for t in (await db.execute(select(Tool))).scalars()}
    mcps = {m.id: m for m in (await db.execute(select(McpServer))).scalars()}
    kbs = {k.id: k for k in (await db.execute(select(KnowledgeBase))).scalars()}
    numbers = (await db.execute(select(PhoneNumber))).scalars().all()
    return {
        "agents": [
            {
                "id": a.id,
                "slug": a.slug,
                "name": a.name,
                "description": a.description,
                "voice_id": a.voice_id,
                "speed": a.speed,
                "is_entry": a.is_entry,
                "position": a.position or {},
                "published_version": a.published_version,
                "tools": [tools[t].name for t in a.tool_ids or [] if t in tools],
                "mcps": [mcps[m].label for m in a.mcp_ids or [] if m in mcps],
                "knowledge": [kbs[k].name for k in a.knowledge_ids or [] if k in kbs],
                "builtin": [k for k, v in (a.builtin_tools or {}).items() if (v or {}).get("enabled")],
                "transfers": len(a.transfer_target_ids or []),
            }
            for a in agents
        ],
        "edges": [to_dict(e) for e in edges],
        "entry_points": [
            {"kind": "phone", "id": n.id, "label": n.e164, "name": n.name, "agent_id": n.entry_agent_id} for n in numbers
        ],
    }


class PositionsIn(BaseModel):
    positions: dict[str, dict[str, float]]


@router.put("/landscape/positions")
async def save_positions(body: PositionsIn, db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    count = 0
    for agent_id, pos in body.positions.items():
        agent = await db.get(Agent, agent_id)
        if agent:
            agent.position = {"x": float(pos.get("x", 0)), "y": float(pos.get("y", 0))}
            count += 1
    return {"updated": count}


class EdgeIn(BaseModel):
    source_id: str
    target_id: str
    description: str = ""
    context_fields: list[ContextField] = Field(default_factory=list)
    handoff_greeting: str = ""
    voice_policy: Literal["switch", "keep"] = "switch"


class EdgePatch(BaseModel):
    description: str | None = None
    context_fields: list[ContextField] | None = None
    handoff_greeting: str | None = None
    voice_policy: Literal["switch", "keep"] | None = None


@router.post("/edges", status_code=201)
async def create_edge(body: EdgeIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if body.source_id == body.target_id:
        raise HTTPException(422, "An agent cannot hand off to itself")
    await get_or_404(db, Agent, body.source_id)
    await get_or_404(db, Agent, body.target_id)
    existing = (
        await db.execute(
            select(HandoffEdge).where(HandoffEdge.source_id == body.source_id, HandoffEdge.target_id == body.target_id)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "This handoff already exists")
    names = [f.name for f in body.context_fields]
    if len(names) != len(set(names)) or {"reason", "summary"} & set(names):
        raise HTTPException(422, "Context field names must be unique and cannot be 'reason' or 'summary'")
    edge = HandoffEdge(**{**body.model_dump(), "context_fields": [f.model_dump() for f in body.context_fields]})
    db.add(edge)
    await db.flush()
    return to_dict(edge)


@router.patch("/edges/{edge_id}")
async def update_edge(edge_id: str, body: EdgePatch, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    edge = await get_or_404(db, HandoffEdge, edge_id)
    patch = body.model_dump(exclude_unset=True)
    if "context_fields" in patch:
        names = [f["name"] for f in patch["context_fields"]]
        if len(names) != len(set(names)) or {"reason", "summary"} & set(names):
            raise HTTPException(422, "Context field names must be unique and cannot be 'reason' or 'summary'")
    for k, v in patch.items():
        setattr(edge, k, v)
    await db.flush()
    return to_dict(edge)


@router.delete("/edges/{edge_id}", status_code=204)
async def delete_edge(edge_id: str, db: AsyncSession = Depends(get_db)) -> None:
    await db.delete(await get_or_404(db, HandoffEdge, edge_id))


# Agents-as-code ---------------------------------------------------------------------------------

AGENT_FIELDS = [
    "name",
    "description",
    "prompt_mode",
    "prompt_sections",
    "raw_prompt",
    "key_facts",
    "greeting",
    "greeting_mode",
    "greeting_interruptible",
    "voice_id",
    "speed",
    "reasoning_effort",
    "language_hint",
    "keyterms",
    "replace_map",
    "idle_timeout_ms",
    "builtin_tools",
    "allow_end_call",
    "position",
    "is_entry",
]
TOOL_FIELDS = ["name", "kind", "description", "parameters", "config", "preamble", "requires_confirmation", "enabled"]
MCP_FIELDS = [
    "label",
    "description",
    "mode",
    "transport",
    "url",
    "command",
    "args",
    "allowed_tools",
    "authorization_secret",
    "header_secrets",
    "enabled",
]
KB_FIELDS = ["name", "slug", "description", "mode", "collection_id", "top_k"]
XFER_FIELDS = ["name", "uri", "description"]


async def export_landscape(db: AsyncSession) -> dict[str, Any]:
    agents = (await db.execute(select(Agent).order_by(Agent.created_at))).scalars().all()
    by_id = {a.id: a for a in agents}
    tools = {t.id: t for t in (await db.execute(select(Tool))).scalars()}
    mcps = {m.id: m for m in (await db.execute(select(McpServer))).scalars()}
    kbs = {k.id: k for k in (await db.execute(select(KnowledgeBase))).scalars()}
    xfers = {x.id: x for x in (await db.execute(select(TransferTarget))).scalars()}
    edges = (await db.execute(select(HandoffEdge))).scalars().all()
    return {
        "version": 1,
        "tools": [{f: getattr(t, f) for f in TOOL_FIELDS} for t in tools.values()],
        "mcp_servers": [{f: getattr(m, f) for f in MCP_FIELDS} for m in mcps.values()],
        "knowledge_bases": [{f: getattr(k, f) for f in KB_FIELDS} for k in kbs.values()],
        "transfer_targets": [{f: getattr(x, f) for f in XFER_FIELDS} for x in xfers.values()],
        "agents": [
            {
                "slug": a.slug,
                **{f: getattr(a, f) for f in AGENT_FIELDS},
                "tools": [tools[i].name for i in a.tool_ids or [] if i in tools],
                "mcp_servers": [mcps[i].label for i in a.mcp_ids or [] if i in mcps],
                "knowledge_bases": [kbs[i].slug for i in a.knowledge_ids or [] if i in kbs],
                "transfer_targets": [xfers[i].name for i in a.transfer_target_ids or [] if i in xfers],
            }
            for a in agents
        ],
        "handoffs": [
            {
                "from": by_id[e.source_id].slug,
                "to": by_id[e.target_id].slug,
                "description": e.description,
                "context_fields": e.context_fields,
                "handoff_greeting": e.handoff_greeting,
                "voice_policy": e.voice_policy,
            }
            for e in edges
            if e.source_id in by_id and e.target_id in by_id
        ],
    }


async def import_landscape(db: AsyncSession, doc: dict[str, Any], *, replace: bool = False) -> dict[str, int]:
    if doc.get("version") != 1:
        raise HTTPException(422, "Unsupported landscape file version (expected version: 1)")
    if replace:
        for model in (HandoffEdge, Agent, Tool, McpServer, TransferTarget):
            for row in (await db.execute(select(model))).scalars():
                await db.delete(row)
        await db.flush()

    async def upsert(model: type, key: str, item: dict[str, Any], fields: list[str]) -> Any:
        row = (await db.execute(select(model).where(getattr(model, key) == item[key]))).scalar_one_or_none()
        values = {f: item[f] for f in fields if f in item}
        if row is None:
            row = model(**values)
            db.add(row)
        else:
            for f, v in values.items():
                setattr(row, f, v)
        await db.flush()
        return row

    tools = {t["name"]: await upsert(Tool, "name", t, TOOL_FIELDS) for t in doc.get("tools", [])}
    mcps = {m["label"]: await upsert(McpServer, "label", m, MCP_FIELDS) for m in doc.get("mcp_servers", [])}
    kbs = {}
    for k in doc.get("knowledge_bases", []):
        k = {**k, "slug": k.get("slug") or slugify(k["name"])}
        kbs[k["slug"]] = await upsert(KnowledgeBase, "slug", k, KB_FIELDS)
    xfers = {x["name"]: await upsert(TransferTarget, "name", x, XFER_FIELDS) for x in doc.get("transfer_targets", [])}
    agents = {}
    for a in doc.get("agents", []):
        a = {**a, "slug": a.get("slug") or slugify(a["name"])}
        row = await upsert(Agent, "slug", a, ["slug", *AGENT_FIELDS])
        row.tool_ids = [tools[n].id for n in a.get("tools", []) if n in tools]
        row.mcp_ids = [mcps[n].id for n in a.get("mcp_servers", []) if n in mcps]
        row.knowledge_ids = [kbs[n].id for n in a.get("knowledge_bases", []) if n in kbs]
        row.transfer_target_ids = [xfers[n].id for n in a.get("transfer_targets", []) if n in xfers]
        agents[row.slug] = row
    await db.flush()
    edge_count = 0
    for h in doc.get("handoffs", []):
        src, dst = agents.get(h["from"]), agents.get(h["to"])
        if not src or not dst:
            continue
        edge = (
            await db.execute(select(HandoffEdge).where(HandoffEdge.source_id == src.id, HandoffEdge.target_id == dst.id))
        ).scalar_one_or_none()
        if edge is None:
            edge = HandoffEdge(source_id=src.id, target_id=dst.id)
            db.add(edge)
        edge.description = h.get("description", "")
        edge.context_fields = h.get("context_fields", [])
        edge.handoff_greeting = h.get("handoff_greeting", "")
        edge.voice_policy = h.get("voice_policy", "switch")
        edge_count += 1
    entries = [a for a in agents.values() if a.is_entry]
    for extra in entries[1:]:
        extra.is_entry = False
    return {
        "agents": len(agents),
        "handoffs": edge_count,
        "tools": len(tools),
        "mcp_servers": len(mcps),
        "knowledge_bases": len(kbs),
    }


@router.get("/landscape/export", response_class=PlainTextResponse)
async def export_yaml(db: AsyncSession = Depends(get_db)) -> str:
    return yaml.safe_dump(await export_landscape(db), sort_keys=False, allow_unicode=True)


@router.post("/landscape/import")
async def import_yaml(
    body: str = Body(..., media_type="text/plain"), replace: bool = False, db: AsyncSession = Depends(get_db)
) -> dict[str, int]:
    try:
        doc = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise HTTPException(422, f"Invalid YAML: {exc}") from exc
    if not isinstance(doc, dict):
        raise HTTPException(422, "Expected a YAML mapping")
    return await import_landscape(db, doc, replace=replace)
