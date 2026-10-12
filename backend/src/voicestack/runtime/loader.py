"""Builds AgentSpec / LandscapeSpec from database rows (drafts) or published snapshots."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.db.models import Agent, AgentVersion, HandoffEdge, KnowledgeBase, McpServer, Tool, TransferTarget
from voicestack.runtime.specs import (
    AgentSpec,
    ContextField,
    EdgeSpec,
    KnowledgeSpec,
    LandscapeSpec,
    McpSpec,
    ToolSpec,
    TransferSpec,
)


async def build_agent_spec(db: AsyncSession, agent: Agent, *, agents_by_id: dict[str, Agent] | None = None) -> AgentSpec:
    if agents_by_id is None:
        agents_by_id = {a.id: a for a in (await db.execute(select(Agent))).scalars()}
    tools = (await db.execute(select(Tool).where(Tool.id.in_(agent.tool_ids or []), Tool.enabled))).scalars().all()
    mcps = (await db.execute(select(McpServer).where(McpServer.id.in_(agent.mcp_ids or []), McpServer.enabled))).scalars().all()
    kbs = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(agent.knowledge_ids or [])))).scalars().all()
    transfers = (
        (await db.execute(select(TransferTarget).where(TransferTarget.id.in_(agent.transfer_target_ids or [])))).scalars().all()
    )
    edges = (await db.execute(select(HandoffEdge).where(HandoffEdge.source_id == agent.id))).scalars().all()

    edge_specs = []
    for e in edges:
        target = agents_by_id.get(e.target_id)
        if not target:
            continue
        edge_specs.append(
            EdgeSpec(
                id=e.id,
                source_slug=agent.slug,
                target_slug=target.slug,
                target_name=target.name,
                description=e.description,
                context_fields=[ContextField.model_validate(f) for f in e.context_fields or []],
                handoff_greeting=e.handoff_greeting,
                voice_policy=e.voice_policy if e.voice_policy in ("switch", "keep") else "switch",
            )
        )
    return AgentSpec(
        id=agent.id,
        slug=agent.slug,
        name=agent.name,
        description=agent.description,
        prompt_mode=agent.prompt_mode if agent.prompt_mode in ("sections", "raw") else "sections",
        prompt_sections=agent.prompt_sections or {},
        raw_prompt=agent.raw_prompt,
        key_facts=agent.key_facts,
        greeting=agent.greeting,
        greeting_mode=agent.greeting_mode,
        greeting_interruptible=agent.greeting_interruptible,
        voice_id=agent.voice_id,
        speed=agent.speed,
        reasoning_effort=agent.reasoning_effort,
        language_hint=agent.language_hint,
        keyterms=agent.keyterms or [],
        replace_map=agent.replace_map or {},
        idle_timeout_ms=agent.idle_timeout_ms,
        builtin_tools=agent.builtin_tools or {},
        allow_end_call=agent.allow_end_call,
        tools=[
            ToolSpec(
                id=t.id,
                name=t.name,
                kind=t.kind,
                description=t.description,
                parameters=t.parameters or {},
                config=t.config or {},
                preamble=t.preamble,
                requires_confirmation=t.requires_confirmation,
            )
            for t in tools
        ],
        mcps=[
            McpSpec(
                id=m.id,
                label=m.label,
                description=m.description,
                mode=m.mode,
                transport=m.transport,
                url=m.url,
                command=m.command,
                args=m.args or [],
                allowed_tools=m.allowed_tools or [],
                authorization_secret=m.authorization_secret,
                header_secrets=m.header_secrets or {},
            )
            for m in mcps
        ],
        knowledge=[
            KnowledgeSpec(
                id=k.id,
                slug=k.slug,
                name=k.name,
                description=k.description,
                mode=k.mode,
                collection_id=k.collection_id,
                top_k=k.top_k,
            )
            for k in kbs
        ],
        transfers=[TransferSpec(id=t.id, name=t.name, uri=t.uri, description=t.description) for t in transfers],
        edges=edge_specs,
    )


async def load_landscape(db: AsyncSession, *, published: bool = False, entry_agent_id: str | None = None) -> LandscapeSpec:
    """Drafts for preview; published snapshots for phone calls (falls back to the draft if never published)."""
    agents = (await db.execute(select(Agent))).scalars().all()
    by_id = {a.id: a for a in agents}
    specs: dict[str, AgentSpec] = {}
    for agent in agents:
        spec: AgentSpec | None = None
        if published and agent.published_version is not None:
            row = (
                await db.execute(
                    select(AgentVersion).where(AgentVersion.agent_id == agent.id, AgentVersion.version == agent.published_version)
                )
            ).scalar_one_or_none()
            if row:
                spec = AgentSpec.model_validate(row.snapshot)
        if spec is None:
            spec = await build_agent_spec(db, agent, agents_by_id=by_id)
        specs[spec.slug] = spec
    entry = by_id.get(entry_agent_id) if entry_agent_id else next((a for a in agents if a.is_entry), None)
    return LandscapeSpec(agents=specs, entry_slug=entry.slug if entry else (next(iter(specs)) if specs else None))
