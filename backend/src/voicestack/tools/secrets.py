"""Named secrets referenced by tools and MCP servers as {{secret:NAME}}."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.db.models import Secret
from voicestack.db.session import session_scope
from voicestack.security.crypto import decrypt, encrypt, last4

SECRET_REF = re.compile(r"\{\{\s*secret:([A-Za-z0-9_.-]+)\s*\}\}")


async def get_secret(name: str, db: AsyncSession | None = None) -> str | None:
    if db is None:
        async with session_scope() as s:
            return await get_secret(name, s)
    row = (await db.execute(select(Secret).where(Secret.name == name))).scalar_one_or_none()
    return decrypt(row.ciphertext) if row else None


async def put_secret(db: AsyncSession, name: str, value: str) -> Secret:
    row = (await db.execute(select(Secret).where(Secret.name == name))).scalar_one_or_none()
    if row is None:
        row = Secret(name=name, ciphertext=encrypt(value), last4=last4(value))
        db.add(row)
    else:
        row.ciphertext = encrypt(value)
        row.last4 = last4(value)
    await db.flush()
    return row


async def render_secrets(value: str) -> str:
    """Replace {{secret:NAME}} references; unknown names raise so misconfigurations surface."""
    names = set(SECRET_REF.findall(value))
    if not names:
        return value
    async with session_scope() as db:
        resolved = {n: await get_secret(n, db) for n in names}
    missing = [n for n, v in resolved.items() if v is None]
    if missing:
        raise KeyError(f"Unknown secret(s): {', '.join(missing)}")
    return SECRET_REF.sub(lambda m: resolved[m.group(1)] or "", value)
