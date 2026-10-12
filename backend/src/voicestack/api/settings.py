from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack import __version__
from voicestack.config import get_settings
from voicestack.credentials import clear, credential_status, store
from voicestack.db.session import get_db
from voicestack.xai.client import XAIClient, XAIError

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/app")
async def app_settings() -> dict[str, Any]:
    s = get_settings()
    return {
        "version": __version__,
        "app_env": s.app_env,
        "role": s.role,
        "auth_mode": s.auth_mode,
        "voice_model": s.voice_model,
        "text_model": s.text_model,
        "optimizer_model": s.optimizer_model,
        "optimizer_reasoning_effort": s.optimizer_reasoning_effort,
        "handoff_voice_mode": s.handoff_voice_mode,
        "public_base_url": s.public_base_url,
        "database": "postgres" if s.is_postgres else "sqlite",
        "embeddings_provider": s.embeddings_provider,
        "embeddings_model": s.embeddings_model,
    }


@router.get("/credentials")
async def get_credentials(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await credential_status(db)


class CredentialIn(BaseModel):
    value: str = Field(min_length=8)
    skip_validation: bool = False


async def _validate_api_key(value: str) -> None:
    async with XAIClient(value) as client:
        try:
            await client.validate()
        except XAIError as exc:
            raise HTTPException(422, f"xAI did not accept this key: {exc.message}") from exc


@router.put("/credentials/{name}")
async def put_credential(name: Literal["xai_api_key"], body: CredentialIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    validated = False
    if name == "xai_api_key" and not body.skip_validation:
        await _validate_api_key(body.value.strip())
        validated = True
    await store(db, name, body.value.strip(), validated)
    return await credential_status(db)


@router.delete("/credentials/{name}")
async def delete_credential(name: Literal["xai_api_key"], db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    await clear(db, name)
    return await credential_status(db)


@router.post("/credentials/test-session-key")
async def test_session_key(body: CredentialIn) -> dict[str, bool]:
    await _validate_api_key(body.value.strip())
    return {"ok": True}
