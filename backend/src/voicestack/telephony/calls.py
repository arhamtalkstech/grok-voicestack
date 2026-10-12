"""Inbound SIP calls: signed webhook -> route -> SessionController over a SipTransport."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from sqlalchemy import select

from voicestack.credentials import resolve_server_key
from voicestack.db.models import Agent, Contact, Conversation, PhoneNumber, WebhookDelivery, now
from voicestack.db.session import session_scope
from voicestack.runtime.controller import SessionController
from voicestack.runtime.loader import load_landscape
from voicestack.runtime.transports.sip import SipTransport
from voicestack.security.crypto import decrypt
from voicestack.security.webhooks import WebhookVerificationError, verify

log = logging.getLogger(__name__)
_tasks: set[asyncio.Task] = set()
E164 = re.compile(r"\+?\d{7,15}")


class WebhookRejected(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def header_value(sip_headers: list[dict[str, str]], name: str) -> str | None:
    for h in sip_headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def extract_number(value: str | None) -> str | None:
    if not value:
        return None
    m = E164.search(value)
    if not m:
        return None
    digits = m.group(0)
    return digits if digits.startswith("+") else f"+{digits}"


async def accept_webhook(headers: dict[str, str], body: bytes) -> dict[str, Any]:
    """Verify, dedupe, and route. Returns the routing decision; the call starts in the background."""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise WebhookRejected(400, "Body is not JSON") from exc
    data = payload.get("data") or {}
    to_number = extract_number(header_value(data.get("sip_headers"), "To"))
    from_number = extract_number(header_value(data.get("sip_headers"), "From"))
    msg_id = {k.lower(): v for k, v in headers.items()}.get("webhook-id", "")

    async with session_scope() as db:
        numbers = (await db.execute(select(PhoneNumber).where(PhoneNumber.signing_secret_cipher.is_not(None)))).scalars().all()
        ordered = sorted(numbers, key=lambda n: n.e164 != to_number)  # try the dialed number's secret first
        matched: PhoneNumber | None = None
        for number in ordered:
            try:
                verify(decrypt(number.signing_secret_cipher), headers, body)
                matched = number
                break
            except WebhookVerificationError:
                continue
        if matched is None:
            raise WebhookRejected(401, "Signature did not match any registered phone number")
        if msg_id and await db.get(WebhookDelivery, msg_id):
            return {"duplicate": True}
        db.add(WebhookDelivery(id=msg_id or f"anon-{now().timestamp()}", event_type=payload.get("type", ""), status="accepted"))
        if payload.get("type") != "realtime.call.incoming":
            return {"ignored": payload.get("type")}
        call_id = data.get("call_id")
        if not call_id:
            raise WebhookRejected(400, "Missing data.call_id")
        entry_agent_id = matched.entry_agent_id
        if not entry_agent_id:
            entry = (await db.execute(select(Agent).where(Agent.is_entry))).scalars().first()
            entry_agent_id = entry.id if entry else None
        decision = {
            "call_id": call_id,
            "number_id": matched.id,
            "to": to_number or matched.e164,
            "from": from_number,
            "entry_agent_id": entry_agent_id,
            "use_published": matched.use_published,
            "disclosure": matched.greeting_disclosure or None,
            "metadata": data.get("metadata") or {},
        }
    task = asyncio.create_task(run_call(decision))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"accepted": True, "call_id": decision["call_id"], "entry_agent_id": decision["entry_agent_id"]}


async def run_call(decision: dict[str, Any]) -> None:
    call_id = decision["call_id"]
    async with session_scope() as db:
        key = await resolve_server_key(db)
        landscape = await load_landscape(db, published=decision["use_published"], entry_agent_id=decision["entry_agent_id"])
        contact_id = None
        if decision.get("from"):
            contact = (await db.execute(select(Contact).where(Contact.external_key == decision["from"]))).scalar_one_or_none()
            if contact is None:
                contact = Contact(external_key=decision["from"])
                db.add(contact)
            contact.last_seen = now()
            await db.flush()
            contact_id = contact.id
        entry_spec = landscape.agents.get(landscape.entry_slug or "")
        conv = Conversation(
            channel="sip",
            call_id=call_id,
            from_number=decision.get("from"),
            to_number=decision.get("to"),
            entry_agent_id=entry_spec.id if entry_spec else None,
            last_agent_id=entry_spec.id if entry_spec else None,
            contact_id=contact_id,
            agents_visited=[entry_spec.id] if entry_spec else [],
            meta={"number_id": decision["number_id"], "metadata": decision.get("metadata", {})},
        )
        db.add(conv)
        await db.flush()
        conversation_id = conv.id
    if not key or not entry_spec:
        log.error("Cannot answer call %s: %s", call_id, "no API key" if not key else "no entry agent")
        async with session_scope() as db:
            row = await db.get(Conversation, conversation_id)
            row.status = "error"
            row.meta = {**row.meta, "error": "No xAI API key configured" if not key else "No entry agent"}
        return

    transport = SipTransport(call_id, key.value)
    controller = SessionController(
        conversation_id=conversation_id,
        landscape=landscape,
        entry_slug=entry_spec.slug,
        transport=transport,
        api_key=key.value,
        contact_id=contact_id,
        call_id=call_id,
        disclosure=decision.get("disclosure"),
    )

    async def on_close() -> None:
        # No session events at all means xAI never attached us to a live call.
        reason = (
            "caller_hung_up"
            if transport.events_seen > 2
            else f"call_unavailable: xAI closed the socket ({transport.close_detail})"
        )
        await controller.end(reason, hangup=False)

    try:
        await transport.connect(controller.handle_xai_event, on_close)
    except Exception as exc:
        log.exception("Could not join call %s", call_id)
        async with session_scope() as db:
            row = await db.get(Conversation, conversation_id)
            row.status = "error"
            row.ended_at = now()
            row.meta = {**row.meta, "error": f"Could not join the call: {exc}"}
        return
    await controller.start()
    await controller.wait_closed()
