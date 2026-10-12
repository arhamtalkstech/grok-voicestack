from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.config import get_settings
from voicestack.credentials import resolve_request_key, session_key_header
from voicestack.db.models import Agent, Contact, Conversation, now
from voicestack.db.session import get_db, session_scope
from voicestack.runtime.bus import bus
from voicestack.runtime.controller import SessionController
from voicestack.runtime.loader import load_landscape
from voicestack.runtime.transports.browser import BrowserDirectTransport
from voicestack.runtime.transports.relay import RelayTransport
from voicestack.security.auth import require_ws_user
from voicestack.xai.client import XAIClient, XAIError
from voicestack.xai.realtime import realtime_url

log = logging.getLogger(__name__)
router = APIRouter(tags=["sessions"])
ws_router = APIRouter(tags=["sessions"])

# Session-only keys and modes live here between POST /api/sessions and the WebSocket opening.
_pending: dict[str, dict[str, Any]] = {}
PENDING_TTL_S = 120
RELAY_CLIENT_EVENTS = {"conversation.item.truncate", "response.cancel", "input_audio_buffer.clear"}


class SessionIn(BaseModel):
    entry_agent_id: str | None = None
    mode: Literal["direct", "relay"] = "direct"
    caller_identity: str | None = Field(None, max_length=255)
    resume_conversation_id: str | None = None


def _gc_pending() -> None:
    cutoff = time.time() - PENDING_TTL_S
    for cid in [c for c, p in _pending.items() if p["created"] < cutoff]:
        _pending.pop(cid, None)


@router.post("/api/sessions", status_code=201)
async def create_session(
    body: SessionIn, db: AsyncSession = Depends(get_db), session_key: str | None = Depends(session_key_header)
) -> dict[str, Any]:
    _gc_pending()
    settings = get_settings()
    key = await resolve_request_key(db, session_key)
    if body.entry_agent_id:
        entry = await db.get(Agent, body.entry_agent_id)
    else:
        entry = (await db.execute(select(Agent).where(Agent.is_entry))).scalars().first() or (
            await db.execute(select(Agent).order_by(Agent.created_at))
        ).scalars().first()
    if not entry:
        raise HTTPException(404, "Create an agent before starting a preview")

    resumed = None
    if body.resume_conversation_id:
        resumed = await db.get(Conversation, body.resume_conversation_id)
        if not resumed:
            raise HTTPException(404, "Conversation to resume was not found")

    contact_id = resumed.contact_id if resumed else None
    if body.caller_identity:
        ident = body.caller_identity.strip()
        contact = (await db.execute(select(Contact).where(Contact.external_key == ident))).scalar_one_or_none()
        if not contact:
            contact = Contact(external_key=ident)
            db.add(contact)
        contact.last_seen = now()
        await db.flush()
        contact_id = contact.id

    conv = Conversation(
        channel="web",
        entry_agent_id=entry.id,
        last_agent_id=entry.id,
        contact_id=contact_id,
        resumed_from_id=resumed.id if resumed else None,
        agents_visited=[entry.id],
        meta={"mode": body.mode, "key_source": key.source},
    )
    db.add(conv)
    await db.flush()

    realtime = None
    if body.mode == "direct":
        async with XAIClient(key.value) as client:
            try:
                secret = await client.create_client_secret(settings.ephemeral_token_ttl_s)
            except XAIError as exc:
                raise HTTPException(
                    502 if exc.status >= 500 else exc.status, f"Could not create an ephemeral token: {exc.message}"
                ) from exc
        realtime = {
            "url": realtime_url(),
            "token": secret.get("value"),
            "expires_at": secret.get("expires_at"),
            "subprotocol_prefix": "xai-client-secret.",
        }
    _pending[conv.id] = {
        "key": key.value,
        "mode": body.mode,
        "entry_agent_id": entry.id,
        "contact_id": contact_id,
        "resume_from": resumed.id if resumed else None,
        "created": time.time(),
    }
    return {
        "conversation_id": conv.id,
        "mode": body.mode,
        "entry_agent": {"id": entry.id, "slug": entry.slug, "name": entry.name},
        "ws_path": f"/api/sessions/{conv.id}/ws",
        "realtime": realtime,
    }


@ws_router.websocket("/api/sessions/{conversation_id}/ws")
async def session_ws(websocket: WebSocket, conversation_id: str) -> None:
    try:
        await require_ws_user(websocket)
    except HTTPException:
        await websocket.close(code=4401)
        return
    pending = _pending.pop(conversation_id, None)
    if not pending:
        await websocket.close(code=4404, reason="Unknown or expired session")
        return
    await websocket.accept()

    async with session_scope() as db:
        landscape = await load_landscape(db, entry_agent_id=pending["entry_agent_id"])
    entry_slug = landscape.entry_slug
    if not entry_slug:
        await websocket.close(code=4400, reason="No entry agent")
        return

    relay: RelayTransport | None = None
    if pending["mode"] == "relay":
        relay = RelayTransport(websocket, pending["key"])
        transport = relay
    else:
        transport = BrowserDirectTransport(websocket)
    controller = SessionController(
        conversation_id=conversation_id,
        landscape=landscape,
        entry_slug=entry_slug,
        transport=transport,
        api_key=pending["key"],
        contact_id=pending["contact_id"],
    )
    await websocket.send_json(
        {
            "kind": "ready",
            "entry_agent": entry_slug,
            "agents": {
                s: {"id": a.id, "name": a.name, "voice_id": a.voice_id, "speed": a.speed} for s, a in landscape.agents.items()
            },
        }
    )

    if relay:

        async def upstream_closed() -> None:
            await controller.end("upstream_closed", hangup=False)

        try:
            await relay.connect(controller.handle_xai_event, upstream_closed)
        except Exception as exc:
            await websocket.send_json(
                {"kind": "ui", "event": {"type": "error", "source": "xai", "message": f"Could not connect to xAI: {exc}"}}
            )
            await websocket.close(code=4502)
            return
        await controller.start(resume_from=pending["resume_from"])

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                if relay:
                    await relay.send_audio(message["bytes"])
                continue
            data = json.loads(message.get("text") or "{}")
            kind = data.get("kind")
            if kind == "xai_open" and not relay:
                await controller.start(resume_from=pending["resume_from"])
            elif kind == "xai_event" and not relay:
                if "playing" in data:
                    transport.set_playing(bool(data["playing"]))
                await controller.handle_xai_event(data.get("event") or {})
            elif kind == "xai_closed" and not relay:
                await controller.end(data.get("reason") or "xai_closed", hangup=False)
            elif kind == "playback":
                if relay:
                    relay.playback_report(bool(data.get("playing")), data.get("seq"))
                else:
                    transport.set_playing(bool(data.get("playing")))
            elif kind == "text":
                await controller.send_text(str(data.get("text", "")))
            elif kind == "client_event" and relay:
                event = data.get("event") or {}
                if event.get("type") in RELAY_CLIENT_EVENTS:
                    await relay.send(event)
            elif kind == "hangup":
                await controller.end("user_ended", hangup=False)
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("Session socket error for %s", conversation_id)
    finally:
        if not controller.closed:
            await controller.end("client_disconnected", hangup=False)


@router.post("/api/sessions/{conversation_id}/refresh")
async def refresh_session(conversation_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    live = bus.sessions.get(conversation_id)
    if not live:
        raise HTTPException(404, "That session is not live")
    await live.controller.refresh(await load_landscape(db))
    return {"refreshed": True}


@router.get("/api/live")
async def live_sessions() -> list[dict[str, Any]]:
    return [
        {
            "conversation_id": cid,
            "channel": s.controller.channel,
            "agent": s.controller.active_slug,
            "call_id": s.controller.call_id,
            "started_at": s.started_at,
        }
        for cid, s in bus.sessions.items()
    ]


@router.post("/api/live/{conversation_id}/hangup")
async def hangup_live(conversation_id: str) -> dict[str, Any]:
    live = bus.sessions.get(conversation_id)
    if not live:
        raise HTTPException(404, "That session is not live")
    await live.controller.end("operator_hangup")
    return {"ended": True}


@ws_router.websocket("/api/live/ws")
async def live_ws(websocket: WebSocket) -> None:
    """Live monitor: all sessions (conversation_id=*) or one conversation."""
    try:
        await require_ws_user(websocket)
    except HTTPException:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    key = websocket.query_params.get("conversation_id") or "*"
    queue = bus.subscribe(key)
    try:
        await websocket.send_json({"type": "snapshot", "sessions": await live_sessions()})
        while True:
            getter = asyncio.create_task(queue.get())
            receiver = asyncio.create_task(websocket.receive())
            done, pending_tasks = await asyncio.wait({getter, receiver}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending_tasks:
                t.cancel()
            if receiver in done:
                msg = receiver.result()
                if msg.get("type") == "websocket.disconnect":
                    break
                continue
            await websocket.send_json(getter.result())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        bus.unsubscribe(key, queue)
