from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from voicestack.credentials import resolve_request_key, session_key_header
from voicestack.db.session import get_db
from voicestack.xai.client import XAIClient, XAIError

router = APIRouter(prefix="/api/voices", tags=["voices"])

CUSTOM_VOICE_NOTICE = (
    "Custom voices are available only in the United States, excluding Illinois. Teams in other countries "
    "need to contact the xAI sales team. Creating voices through the API also requires an Enterprise plan; "
    "you can create up to 30 voices for free in the xAI console and paste the voice ID here."
)
_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def _xai_http_error(exc: XAIError) -> HTTPException:
    if exc.status == 403:
        return HTTPException(403, f"{exc.message.rstrip('.')}. {CUSTOM_VOICE_NOTICE}")
    return HTTPException(502 if exc.status >= 500 else exc.status, exc.message)


@router.get("")
async def list_voices(
    db: AsyncSession = Depends(get_db), session_key: str | None = Depends(session_key_header)
) -> dict[str, Any]:
    key = await resolve_request_key(db, session_key)
    cache_key = key.value[-12:]
    builtin: list[dict[str, Any]]
    cached = _cache.get(cache_key)
    async with XAIClient(key.value) as client:
        if cached and time.time() - cached[0] < 600:
            builtin = cached[1]
        else:
            try:
                builtin = await client.list_voices()
            except XAIError as exc:
                raise _xai_http_error(exc) from exc
            _cache[cache_key] = (time.time(), builtin)
        custom: list[dict[str, Any]] = []
        custom_error = None
        try:
            custom = await client.list_custom_voices()
        except XAIError as exc:
            custom_error = exc.message if exc.status != 404 else None
    return {"builtin": builtin, "custom": custom, "custom_error": custom_error, "custom_notice": CUSTOM_VOICE_NOTICE}


class PreviewIn(BaseModel):
    voice_id: str
    text: str = Field("Hi, thanks for calling. How can I help you today?", max_length=400)
    speed: float = Field(1.0, ge=0.7, le=1.5)
    language: str = "en"


@router.post("/preview")
async def preview(
    body: PreviewIn, db: AsyncSession = Depends(get_db), session_key: str | None = Depends(session_key_header)
) -> Response:
    key = await resolve_request_key(db, session_key)
    async with XAIClient(key.value) as client:
        try:
            audio = await client.tts(body.text, body.voice_id, language=body.language, speed=body.speed)
        except XAIError as exc:
            raise _xai_http_error(exc) from exc
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/custom", status_code=201)
async def create_custom_voice(
    file: UploadFile = File(...),
    name: str = Form(...),
    consent: bool = Form(...),
    language: str = Form(""),
    gender: str = Form(""),
    accent: str = Form(""),
    age: str = Form(""),
    tone: str = Form(""),
    use_case: str = Form(""),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
    session_key: str | None = Depends(session_key_header),
) -> dict[str, Any]:
    if not consent:
        raise HTTPException(422, "Confirm that the speaker agreed to have their voice cloned")
    content = await file.read()
    if not content:
        raise HTTPException(422, "The reference clip is empty")
    key = await resolve_request_key(db, session_key)
    fields = {
        "name": name,
        "language": language,
        "gender": gender,
        "accent": accent,
        "age": age,
        "tone": tone,
        "use_case": use_case,
        "description": description,
    }
    async with XAIClient(key.value) as client:
        try:
            return await client.create_custom_voice(
                file.filename or "reference.wav", content, file.content_type or "audio/wav", fields
            )
        except XAIError as exc:
            raise _xai_http_error(exc) from exc


@router.patch("/custom/{voice_id}")
async def update_custom_voice(
    voice_id: str,
    patch: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    session_key: str | None = Depends(session_key_header),
) -> dict[str, Any]:
    if any(v == "" for v in patch.values()):
        raise HTTPException(422, "Use null to clear a field; empty strings are rejected by the API")
    key = await resolve_request_key(db, session_key)
    async with XAIClient(key.value) as client:
        try:
            return await client.update_custom_voice(voice_id, patch)
        except XAIError as exc:
            raise _xai_http_error(exc) from exc


@router.delete("/custom/{voice_id}")
async def delete_custom_voice(
    voice_id: str, db: AsyncSession = Depends(get_db), session_key: str | None = Depends(session_key_header)
) -> dict[str, Any]:
    key = await resolve_request_key(db, session_key)
    async with XAIClient(key.value) as client:
        try:
            return await client.delete_custom_voice(voice_id)
        except XAIError as exc:
            raise _xai_http_error(exc) from exc
