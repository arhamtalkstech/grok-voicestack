from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.api.common import get_or_404, to_dict
from voicestack.config import get_settings
from voicestack.credentials import resolve_server_key
from voicestack.db.models import Agent, PhoneNumber, WebhookDelivery
from voicestack.db.session import get_db
from voicestack.security.crypto import encrypt
from voicestack.telephony.calls import WebhookRejected, accept_webhook
from voicestack.xai.client import XAIClient, XAIError

router = APIRouter(prefix="/api/telephony", tags=["telephony"])
webhook_router = APIRouter(tags=["webhooks"])
WEBHOOK_PATH = "/webhooks/xai/call-incoming"


def webhook_url() -> str | None:
    base = get_settings().public_base_url
    return f"{base.rstrip('/')}{WEBHOOK_PATH}" if base else None


def _number_payload(n: PhoneNumber) -> dict[str, Any]:
    data = to_dict(n, exclude={"signing_secret_cipher"})
    data["has_signing_secret"] = bool(n.signing_secret_cipher)
    # xAI's SIP guide routes carriers to sip.voice.x.ai over TLS; the API's sip_host is shown for reference.
    data["sip_uri"] = f"sip:{n.e164}@sip.voice.x.ai;transport=tls"
    return data


@router.get("/info")
async def info(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    key = await resolve_server_key(db)
    recent = (await db.execute(select(WebhookDelivery).order_by(WebhookDelivery.received_at.desc()).limit(10))).scalars().all()
    return {
        "public_base_url": get_settings().public_base_url,
        "webhook_url": webhook_url(),
        "server_key_configured": bool(key),
        "role": get_settings().role,
        "sip_host": "sip.voice.x.ai",
        "recent_webhooks": [to_dict(w) for w in recent],
    }


class SipAuthIn(BaseModel):
    username: str | None = None
    password: str | None = None
    allowed_addresses: list[str] = Field(default_factory=list)


class NumberIn(BaseModel):
    e164: str = Field(pattern=r"^\+\d{7,15}$")
    name: str = Field(min_length=1, max_length=120)
    entry_agent_id: str | None = None
    use_published: bool = True
    greeting_disclosure: str = ""
    sip_auth: SipAuthIn = Field(default_factory=SipAuthIn)
    # Register with xAI (POST /v2/phone-numbers) or attach a number registered elsewhere.
    register_with_xai: bool = True
    signing_secret: str | None = None
    xai_phone_number_id: str | None = None


@router.get("/numbers")
async def list_numbers(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return [_number_payload(n) for n in (await db.execute(select(PhoneNumber).order_by(PhoneNumber.created_at))).scalars()]


@router.post("/numbers", status_code=201)
async def register_number(body: NumberIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if (await db.execute(select(PhoneNumber).where(PhoneNumber.e164 == body.e164))).scalar_one_or_none():
        raise HTTPException(409, "That number is already registered here")
    if body.entry_agent_id:
        await get_or_404(db, Agent, body.entry_agent_id)
    auth = body.sip_auth
    if bool(auth.username) != bool(auth.password):
        raise HTTPException(422, "SIP digest auth needs both a username and a password")
    row = PhoneNumber(
        e164=body.e164,
        name=body.name,
        entry_agent_id=body.entry_agent_id,
        use_published=body.use_published,
        greeting_disclosure=body.greeting_disclosure,
        sip_auth={"username": auth.username, "allowed_addresses": auth.allowed_addresses},
    )
    if body.register_with_xai:
        url = webhook_url()
        if not url:
            raise HTTPException(412, "Set PUBLIC_BASE_URL so xAI can reach the call webhook")
        key = await resolve_server_key(db)
        if not key:
            raise HTTPException(
                412, "Telephony needs a stored workspace key or XAI_API_KEY (session-only keys cannot answer calls)"
            )
        request: dict[str, Any] = {"origin": "byo_trunk", "name": body.name, "phone_number": body.e164, "webhook": {"url": url}}
        sip_auth: dict[str, Any] = {}
        if auth.username:
            sip_auth.update(auth_username=auth.username, auth_password=auth.password)
        if auth.allowed_addresses:
            sip_auth["allowed_addresses"] = auth.allowed_addresses
        if sip_auth:
            request["sip_auth"] = sip_auth
        async with XAIClient(key.value) as client:
            try:
                created = await client.create_phone_number(request)
            except XAIError as exc:
                raise HTTPException(502 if exc.status >= 500 else exc.status, f"xAI rejected the number: {exc.message}") from exc
        number = created.get("phone_number") or {}
        webhook = created.get("webhook") or {}
        row.xai_phone_number_id = number.get("phone_number_id")
        row.xai_webhook_id = webhook.get("webhook_id") or number.get("webhook_id")
        row.sip_host = number.get("sip_host") or "sip.voice.x.ai"
        if webhook.get("dispatch_signing_secret"):
            row.signing_secret_cipher = encrypt(webhook["dispatch_signing_secret"])
    else:
        if not body.signing_secret:
            raise HTTPException(422, "Paste the webhook signing secret for a number registered elsewhere")
        row.signing_secret_cipher = encrypt(body.signing_secret)
        row.xai_phone_number_id = body.xai_phone_number_id
    db.add(row)
    await db.flush()
    return _number_payload(row)


class NumberPatch(BaseModel):
    name: str | None = None
    entry_agent_id: str | None = None
    use_published: bool | None = None
    greeting_disclosure: str | None = None


@router.patch("/numbers/{number_id}")
async def update_number(number_id: str, body: NumberPatch, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await get_or_404(db, PhoneNumber, number_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.flush()
    return _number_payload(row)


@router.delete("/numbers/{number_id}", status_code=204)
async def delete_number(number_id: str, db: AsyncSession = Depends(get_db), remove_from_xai: bool = True) -> None:
    row = await get_or_404(db, PhoneNumber, number_id)
    if remove_from_xai and row.xai_phone_number_id:
        key = await resolve_server_key(db)
        if key:
            async with XAIClient(key.value) as client:
                try:
                    await client.delete_phone_number(row.xai_phone_number_id)
                except XAIError as exc:
                    if exc.status != 404:
                        raise HTTPException(exc.status, f"xAI could not delete the number: {exc.message}") from exc
    await db.delete(row)


@webhook_router.post(WEBHOOK_PATH)
async def call_incoming(request: Request) -> dict[str, Any]:
    body = await request.body()
    try:
        return await accept_webhook(dict(request.headers), body)
    except WebhookRejected as exc:
        raise HTTPException(exc.status, str(exc)) from exc
