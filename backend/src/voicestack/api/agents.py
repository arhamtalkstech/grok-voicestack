from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.api.common import apply_patch, get_or_404, slugify, to_dict
from voicestack.credentials import resolve_request_key, session_key_header
from voicestack.db.models import Agent, AgentVersion, HandoffEdge
from voicestack.db.session import get_db
from voicestack.prompting.compiler import compile_instructions, sections_to_text, text_to_sections
from voicestack.prompting.linter import lint
from voicestack.prompting.optimizer import optimize_prompt
from voicestack.runtime.bus import bus
from voicestack.runtime.loader import build_agent_spec, load_landscape
from voicestack.runtime.session_config import render_session
from voicestack.tools.registry import ToolContext, build_toolset

router = APIRouter(prefix="/api/agents", tags=["agents"])

EDITABLE = {
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
    "tool_ids",
    "mcp_ids",
    "knowledge_ids",
    "transfer_target_ids",
    "allow_end_call",
    "position",
    "is_entry",
}


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = None
    description: str = ""
    prompt_mode: Literal["sections", "raw"] = "sections"
    prompt_sections: dict[str, str] = Field(default_factory=dict)
    raw_prompt: str = ""
    key_facts: str = ""
    greeting: str = ""
    greeting_mode: Literal["model", "verbatim", "none"] = "model"
    greeting_interruptible: bool = True
    voice_id: str = "eve"
    speed: float = Field(1.0, ge=0.7, le=1.5)
    reasoning_effort: Literal["high", "none"] = "high"
    language_hint: str | None = None
    keyterms: list[str] = Field(default_factory=list, max_length=100)
    replace_map: dict[str, str] = Field(default_factory=dict)
    idle_timeout_ms: int | None = Field(None, ge=1000, le=600000)
    builtin_tools: dict[str, Any] = Field(default_factory=dict)
    tool_ids: list[str] = Field(default_factory=list)
    mcp_ids: list[str] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list)
    transfer_target_ids: list[str] = Field(default_factory=list)
    allow_end_call: bool = True
    position: dict[str, float] = Field(default_factory=dict)
    is_entry: bool = False


class AgentPatch(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = None
    description: str | None = None
    prompt_mode: Literal["sections", "raw"] | None = None
    prompt_sections: dict[str, str] | None = None
    raw_prompt: str | None = None
    key_facts: str | None = None
    greeting: str | None = None
    greeting_mode: Literal["model", "verbatim", "none"] | None = None
    greeting_interruptible: bool | None = None
    voice_id: str | None = None
    speed: float | None = Field(None, ge=0.7, le=1.5)
    reasoning_effort: Literal["high", "none"] | None = None
    language_hint: str | None = None
    keyterms: list[str] | None = None
    replace_map: dict[str, str] | None = None
    idle_timeout_ms: int | None = None
    builtin_tools: dict[str, Any] | None = None
    tool_ids: list[str] | None = None
    mcp_ids: list[str] | None = None
    knowledge_ids: list[str] | None = None
    transfer_target_ids: list[str] | None = None
    allow_end_call: bool | None = None
    position: dict[str, float] | None = None
    is_entry: bool | None = None


async def _unique_slug(db: AsyncSession, base: str, exclude_id: str | None = None) -> str:
    slug, n = base, 2
    while True:
        existing = (await db.execute(select(Agent).where(Agent.slug == slug))).scalar_one_or_none()
        if not existing or existing.id == exclude_id:
            return slug
        slug, n = f"{base}-{n}", n + 1


async def _set_single_entry(db: AsyncSession, agent: Agent) -> None:
    if agent.is_entry:
        for other in (await db.execute(select(Agent).where(Agent.is_entry, Agent.id != agent.id))).scalars():
            other.is_entry = False


async def _refresh_live_sessions(db: AsyncSession) -> None:
    web = [s.controller for s in bus.sessions.values() if s.controller.channel == "web"]
    if not web:
        return
    landscape = await load_landscape(db)
    for controller in web:
        await controller.refresh(landscape)


async def agent_payload(db: AsyncSession, agent: Agent) -> dict[str, Any]:
    data = to_dict(agent)
    spec = await build_agent_spec(db, agent)
    data["lint"] = lint(spec).dict()
    data["draft_changed"] = False
    if agent.published_version is not None:
        row = (
            await db.execute(
                select(AgentVersion).where(AgentVersion.agent_id == agent.id, AgentVersion.version == agent.published_version)
            )
        ).scalar_one_or_none()
        data["draft_changed"] = bool(row and row.snapshot != {**spec.model_dump(mode="json"), "version": agent.published_version})
    return data


@router.get("")
async def list_agents(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    agents = (await db.execute(select(Agent).order_by(Agent.created_at))).scalars().all()
    return [await agent_payload(db, a) for a in agents]


@router.post("", status_code=201)
async def create_agent(body: AgentIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    data = body.model_dump()
    data["slug"] = await _unique_slug(db, slugify(body.slug or body.name))
    if not (await db.execute(select(func.count()).select_from(Agent))).scalar():
        data["is_entry"] = True
    agent = Agent(**data)
    db.add(agent)
    await db.flush()
    await _set_single_entry(db, agent)
    return await agent_payload(db, agent)


@router.get("/{agent_id}")
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await agent_payload(db, await get_or_404(db, Agent, agent_id))


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, body: AgentPatch, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    agent = await get_or_404(db, Agent, agent_id)
    patch = body.model_dump(exclude_unset=True)
    if patch.get("prompt_mode") and patch["prompt_mode"] != agent.prompt_mode:
        # Carry content across when switching between structured sections and a raw prompt.
        if patch["prompt_mode"] == "raw" and not patch.get("raw_prompt") and not agent.raw_prompt:
            patch["raw_prompt"] = sections_to_text(agent.prompt_sections or {})
        if patch["prompt_mode"] == "sections" and not patch.get("prompt_sections") and agent.raw_prompt:
            patch["prompt_sections"] = text_to_sections(agent.raw_prompt)
    apply_patch(agent, patch, EDITABLE)
    await db.flush()
    await _set_single_entry(db, agent)
    if set(patch) - {"position"}:
        await _refresh_live_sessions(db)
    return await agent_payload(db, agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)) -> None:
    agent = await get_or_404(db, Agent, agent_id)
    for edge in (
        await db.execute(select(HandoffEdge).where((HandoffEdge.source_id == agent_id) | (HandoffEdge.target_id == agent_id)))
    ).scalars():
        await db.delete(edge)
    await db.delete(agent)


@router.post("/{agent_id}/duplicate", status_code=201)
async def duplicate_agent(agent_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    src = await get_or_404(db, Agent, agent_id)
    data = {k: v for k, v in to_dict(src).items() if k in EDITABLE}
    data.update(name=f"{src.name} copy", is_entry=False, slug=await _unique_slug(db, f"{src.slug}-copy"))
    pos = dict(src.position or {})
    data["position"] = {"x": pos.get("x", 0) + 60, "y": pos.get("y", 0) + 60}
    agent = Agent(**data)
    db.add(agent)
    await db.flush()
    return await agent_payload(db, agent)


@router.post("/{agent_id}/publish")
async def publish_agent(agent_id: str, note: dict[str, str] | None = None, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    agent = await get_or_404(db, Agent, agent_id)
    latest = (await db.execute(select(func.max(AgentVersion.version)).where(AgentVersion.agent_id == agent_id))).scalar() or 0
    spec = await build_agent_spec(db, agent)
    version = latest + 1
    db.add(
        AgentVersion(
            agent_id=agent_id,
            version=version,
            snapshot={**spec.model_dump(mode="json"), "version": version},
            note=(note or {}).get("note", ""),
        )
    )
    agent.published_version = version
    await db.flush()
    return await agent_payload(db, agent)


@router.get("/{agent_id}/versions")
async def list_versions(agent_id: str, db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (
        await db.execute(select(AgentVersion).where(AgentVersion.agent_id == agent_id).order_by(AgentVersion.version.desc()))
    ).scalars()
    return [to_dict(r) for r in rows]


@router.get("/{agent_id}/compiled")
async def compiled(agent_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The exact session.update this agent sends at the start of a preview, for the inspector."""
    agent = await get_or_404(db, Agent, agent_id)
    spec = await build_agent_spec(db, agent)
    toolset = await build_toolset(spec, ToolContext(conversation_id="preview", channel="web"))
    session = render_session(spec, toolset.realtime_tools, channel="web")
    for tool in session["tools"]:
        if tool.get("type") == "mcp":
            tool.pop("authorization", None)
            tool.pop("headers", None)
    return {"instructions": compile_instructions(spec), "session": session, "tool_errors": toolset.errors}


class LintBody(BaseModel):
    prompt_mode: Literal["sections", "raw"] | None = None
    prompt_sections: dict[str, str] | None = None
    raw_prompt: str | None = None
    key_facts: str | None = None
    language_hint: str | None = None


@router.post("/{agent_id}/prompt/lint")
async def lint_prompt(agent_id: str, body: LintBody, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    spec = await build_agent_spec(db, await get_or_404(db, Agent, agent_id))
    spec = spec.model_copy(update=body.model_dump(exclude_none=True))
    return lint(spec).dict()


class OptimizeBody(LintBody):
    mode: Literal["align", "fix_issue", "simplify"] = "align"
    issue: str = ""
    conversation_ids: list[str] = Field(default_factory=list, max_length=3)


@router.post("/{agent_id}/prompt/optimize")
async def optimize(
    agent_id: str, body: OptimizeBody, db: AsyncSession = Depends(get_db), session_key: str | None = Depends(session_key_header)
) -> dict[str, Any]:
    if body.mode == "fix_issue" and not body.issue.strip():
        raise HTTPException(422, "Describe the issue you are seeing")
    key = await resolve_request_key(db, session_key)
    spec = await build_agent_spec(db, await get_or_404(db, Agent, agent_id))
    spec = spec.model_copy(
        update=body.model_dump(
            exclude_none=True, include={"prompt_mode", "prompt_sections", "raw_prompt", "key_facts", "language_hint"}
        )
    )
    transcripts = []
    if body.conversation_ids:
        from voicestack.api.conversations import conversation_transcript

        for cid in body.conversation_ids:
            transcripts.append(await conversation_transcript(db, cid))
    try:
        return await optimize_prompt(key.value, spec, mode=body.mode, issue=body.issue, transcripts=transcripts)
    except Exception as exc:
        raise HTTPException(502, f"The optimiser could not finish: {exc}") from exc
