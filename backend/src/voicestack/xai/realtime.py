"""Server-side connection to wss://api.x.ai/v1/realtime (relay previews and SIP calls)."""

from __future__ import annotations

from urllib.parse import urlencode

import websockets
from websockets.asyncio.client import ClientConnection

from voicestack.config import get_settings


def realtime_url(*, call_id: str | None = None, conversation_id: str | None = None, model: str | None = None) -> str:
    settings = get_settings()
    params: dict[str, str] = {}
    if call_id:
        params["call_id"] = call_id  # the model is bound to the inbound call
    else:
        params["model"] = model or settings.voice_model
    if conversation_id:
        params["conversation_id"] = conversation_id
    return f"{settings.xai_realtime_url}?{urlencode(params)}"


async def connect(api_key: str, **kwargs: str | None) -> ClientConnection:
    return await websockets.connect(
        realtime_url(**kwargs),
        additional_headers={"Authorization": f"Bearer {api_key}"},
        max_size=16 * 1024 * 1024,
        ping_interval=20,
        ping_timeout=20,
        open_timeout=15,
    )
