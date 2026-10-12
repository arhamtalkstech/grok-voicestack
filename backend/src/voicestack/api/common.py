from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect

SLUG = re.compile(r"[^a-z0-9]+")
RESERVED_SLUGS = {"ingest", "post_call"}
SNAKE = re.compile(r"^[a-z][a-z0-9_]{1,62}$")


def to_dict(row: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    exclude = exclude or set()
    out: dict[str, Any] = {}
    for col in sa_inspect(row).mapper.column_attrs:
        if col.key in exclude:
            continue
        value = getattr(row, col.key)
        if isinstance(value, datetime):
            # SQLite drops tzinfo; values are always written in UTC.
            value = (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
        out[col.key] = value
    return out


def slugify(text: str) -> str:
    slug = SLUG.sub("-", text.lower()).strip("-")[:48] or "agent"
    return f"{slug}-agent" if slug in RESERVED_SLUGS else slug


def snake_name(text: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if not SNAKE.match(name or ""):
        raise HTTPException(422, "Tool names must be snake_case, start with a letter, and be 2–63 characters")
    return name


async def get_or_404(db: AsyncSession, model: type, ident: str) -> Any:
    row = await db.get(model, ident)
    if row is None:
        raise HTTPException(404, f"{model.__name__} {ident} not found")
    return row


def apply_patch(row: Any, patch: dict[str, Any], allowed: set[str]) -> None:
    for key, value in patch.items():
        if key in allowed:
            setattr(row, key, value)
