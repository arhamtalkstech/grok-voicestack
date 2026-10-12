from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from langchain_core.messages import messages_to_dict
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.api.common import get_or_404, to_dict
from voicestack.db.models import Agent, Contact, Conversation, ConversationEvent, Turn
from voicestack.db.session import get_db
from voicestack.runtime.graph import build_graph
from voicestack.runtime.persistence import get_persistence
from voicestack.runtime.specs import LandscapeSpec

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    channel: str | None = None,
    agent_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
) -> dict[str, Any]:
    stmt = select(Conversation)
    if channel:
        stmt = stmt.where(Conversation.channel == channel)
    if status:
        stmt = stmt.where(Conversation.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Conversation.summary.ilike(like),
                Conversation.from_number.ilike(like),
                Conversation.id.in_(select(Turn.conversation_id).where(Turn.text.ilike(like))),
            )
        )
    rows = (await db.execute(stmt.order_by(Conversation.started_at.desc()))).scalars().all()
    if agent_id:
        rows = [r for r in rows if agent_id in (r.agents_visited or []) or r.entry_agent_id == agent_id]
    total = len(rows)
    rows = rows[offset : offset + limit]
    ids = [r.id for r in rows]
    counts = (
        dict(
            (
                await db.execute(
                    select(Turn.conversation_id, func.count()).where(Turn.conversation_id.in_(ids)).group_by(Turn.conversation_id)
                )
            ).all()
        )
        if ids
        else {}
    )
    contacts = {
        c.id: c
        for c in (await db.execute(select(Contact).where(Contact.id.in_([r.contact_id for r in rows if r.contact_id])))).scalars()
    }
    return {
        "total": total,
        "items": [
            {
                **to_dict(r),
                "turn_count": counts.get(r.id, 0),
                "contact": contacts[r.contact_id].external_key if r.contact_id in contacts else None,
            }
            for r in rows
        ],
    }


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    conv = await get_or_404(db, Conversation, conversation_id)
    turns = (await db.execute(select(Turn).where(Turn.conversation_id == conversation_id).order_by(Turn.seq))).scalars().all()
    agent_ids = {t.agent_id for t in turns if t.agent_id} | set(conv.agents_visited or [])
    agents = {
        a.id: {"id": a.id, "slug": a.slug, "name": a.name}
        for a in (await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))).scalars()
    }
    contact = await db.get(Contact, conv.contact_id) if conv.contact_id else None
    chain: list[str] = []
    cursor = conv
    while cursor and cursor.resumed_from_id and len(chain) < 10:
        chain.append(cursor.resumed_from_id)
        cursor = await db.get(Conversation, cursor.resumed_from_id)
    return {
        **to_dict(conv),
        "turns": [to_dict(t) for t in turns],
        "agents": agents,
        "contact": contact.external_key if contact else None,
        "resume_chain": chain,
    }


@router.get("/{conversation_id}/state")
async def conversation_state(conversation_id: str) -> dict[str, Any]:
    """The LangGraph checkpoint for this conversation: active agent, collected context, handoffs."""
    persistence = get_persistence()
    graph = build_graph(LandscapeSpec(agents={}), persistence.checkpointer, persistence.store)
    snapshot = await graph.aget_state({"configurable": {"thread_id": conversation_id}})
    values = snapshot.values or {}
    return {
        "active_agent": values.get("active_agent"),
        "context": values.get("context") or {},
        "handoffs": values.get("handoffs") or [],
        "call_summary": values.get("call_summary"),
        "message_count": len(values.get("messages") or []),
        "messages": messages_to_dict(values.get("messages") or [])[-60:],
        "checkpoint_id": (snapshot.config or {}).get("configurable", {}).get("checkpoint_id"),
    }


@router.get("/{conversation_id}/events")
async def conversation_events(
    conversation_id: str, db: AsyncSession = Depends(get_db), limit: int = Query(500, le=5000), offset: int = 0
) -> dict[str, Any]:
    """The stored realtime event log: what xAI sent (in) and what Voice Stack sent (out), in order."""
    await get_or_404(db, Conversation, conversation_id)
    base = select(ConversationEvent).where(ConversationEvent.conversation_id == conversation_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    rows = (await db.execute(base.order_by(ConversationEvent.id).offset(offset).limit(limit))).scalars().all()
    return {"total": total, "items": [to_dict(r) for r in rows]}


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)) -> None:
    await db.delete(await get_or_404(db, Conversation, conversation_id))
    await get_persistence().checkpointer.adelete_thread(conversation_id)


async def conversation_transcript(db: AsyncSession, conversation_id: str) -> str:
    turns = (await db.execute(select(Turn).where(Turn.conversation_id == conversation_id).order_by(Turn.seq))).scalars().all()
    agents = {a.id: a.name for a in (await db.execute(select(Agent))).scalars()}
    lines = []
    for t in turns:
        if t.kind == "user":
            lines.append(f"Caller: {t.text}")
        elif t.kind == "assistant":
            lines.append(f"Agent ({agents.get(t.agent_id, 'agent')}): {t.text}")
        elif t.kind == "handoff":
            lines.append(f"[handoff {t.text}]")
    return "\n".join(lines)
