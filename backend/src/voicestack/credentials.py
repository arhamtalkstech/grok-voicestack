"""Bring-your-own-key resolution.

Order: a session-only key sent by the browser (never stored), then the workspace key encrypted in
the database, then the XAI_API_KEY environment variable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.api.common import to_dict
from voicestack.config import get_settings
from voicestack.db.models import Credential, now
from voicestack.db.session import session_scope
from voicestack.security.crypto import decrypt, encrypt, last4

SESSION_KEY_HEADER = "x-xai-api-key"
KeySource = Literal["session", "workspace", "env"]
CredentialName = Literal["xai_api_key"]


@dataclass
class ResolvedKey:
    value: str
    source: KeySource


async def get_stored(db: AsyncSession, name: CredentialName) -> str | None:
    row = await db.get(Credential, name)
    return decrypt(row.ciphertext) if row else None


async def store(db: AsyncSession, name: CredentialName, value: str, validated: bool) -> Credential:
    row = await db.get(Credential, name)
    validated_at: datetime | None = now() if validated else None
    if row is None:
        row = Credential(key=name, ciphertext=encrypt(value), last4=last4(value), validated_at=validated_at)
        db.add(row)
    else:
        row.ciphertext = encrypt(value)
        row.last4 = last4(value)
        row.validated_at = validated_at
    await db.flush()
    return row


async def clear(db: AsyncSession, name: CredentialName) -> None:
    row = await db.get(Credential, name)
    if row:
        await db.delete(row)


async def resolve_server_key(db: AsyncSession | None = None) -> ResolvedKey | None:
    """Key usable without a browser present (telephony, background jobs)."""
    if db is None:
        async with session_scope() as s:
            return await resolve_server_key(s)
    stored = await get_stored(db, "xai_api_key")
    if stored:
        return ResolvedKey(stored, "workspace")
    env = get_settings().xai_api_key
    return ResolvedKey(env, "env") if env else None


async def resolve_request_key(db: AsyncSession, session_key: str | None) -> ResolvedKey:
    if session_key:
        return ResolvedKey(session_key.strip(), "session")
    resolved = await resolve_server_key(db)
    if not resolved:
        raise HTTPException(
            status_code=412,
            detail="No xAI API key configured. Add one in Settings, set XAI_API_KEY, or use a session-only key.",
        )
    return resolved


def session_key_header(x_xai_api_key: str | None = Header(default=None)) -> str | None:
    return x_xai_api_key


async def credential_status(db: AsyncSession) -> dict:
    rows = {r.key: r for r in (await db.execute(select(Credential))).scalars()}
    settings = get_settings()

    def describe(name: str, env_value: str | None) -> dict:
        row = rows.get(name)
        if row:
            return {
                "source": "workspace",
                "last4": row.last4,
                "validated_at": to_dict(row)["validated_at"],
            }
        if env_value:
            return {"source": "env", "last4": last4(env_value), "validated_at": None}
        return {"source": None, "last4": None, "validated_at": None}

    return {
        "xai_api_key": describe("xai_api_key", settings.xai_api_key),
    }
