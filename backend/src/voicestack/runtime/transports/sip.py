"""SIP transport: Voice Stack holds the control WebSocket for an inbound phone call.

xAI bridges the caller's audio; we connect to wss://api.x.ai/v1/realtime?call_id=... with the API
key (ephemeral tokens are not accepted for call_id sessions) and drive the session like any other.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from websockets.asyncio.client import ClientConnection

from voicestack.runtime.transports.base import Transport
from voicestack.xai import realtime

log = logging.getLogger(__name__)


class SipTransport(Transport):
    channel = "sip"

    def __init__(self, call_id: str, api_key: str):
        super().__init__()
        self.call_id = call_id
        self.api_key = api_key
        self.ws: ClientConnection | None = None
        self._reader: asyncio.Task | None = None
        self.open = True
        self.events_seen = 0
        self.close_detail = ""

    async def connect(
        self,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        on_close: Callable[[], Awaitable[None]],
        *,
        conversation_id: str | None = None,
    ) -> None:
        self.ws = await realtime.connect(self.api_key, call_id=self.call_id, conversation_id=conversation_id)

        async def reader() -> None:
            try:
                async for raw in self.ws:
                    if isinstance(raw, bytes):
                        continue
                    self.events_seen += 1
                    await on_event(json.loads(raw))
            except Exception:
                log.info("SIP control socket for %s closed", self.call_id, exc_info=True)
            finally:
                self.open = False
                code, reason = getattr(self.ws, "close_code", None), getattr(self.ws, "close_reason", "") or ""
                self.close_detail = f"{code} {reason}".strip()
                log.info("SIP socket for %s closed after %d events: %s", self.call_id, self.events_seen, self.close_detail)
                await on_close()

        self._reader = asyncio.create_task(reader())

    async def send(self, event: dict[str, Any]) -> None:
        if self.ws and self.open:
            await self.ws.send(json.dumps(event))

    async def close(self, reason: str = "") -> None:
        self.open = False
        if self.ws:
            await self.ws.close()
