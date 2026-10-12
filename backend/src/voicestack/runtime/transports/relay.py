"""Relay transport: browser <-> Voice Stack <-> xAI.

For networks where browsers cannot reach api.x.ai, and for parity with the server-side SIP path.
Mic audio arrives as binary PCM16 (24 kHz mono) frames and is forwarded as input_audio_buffer.append;
every xAI event is forwarded to the browser as-is.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket
from websockets.asyncio.client import ClientConnection

from voicestack.runtime.transports.base import Transport
from voicestack.xai import realtime

log = logging.getLogger(__name__)


class RelayTransport(Transport):
    channel = "web"

    def __init__(self, ws: WebSocket, api_key: str):
        super().__init__()
        self.ws = ws
        self.api_key = api_key
        self.upstream: ClientConnection | None = None
        self.open = True
        self._audio_seq = 0
        self._reader: asyncio.Task | None = None

    async def connect(
        self, on_event: Callable[[dict[str, Any]], Awaitable[None]], on_close: Callable[[], Awaitable[None]]
    ) -> None:
        self.upstream = await realtime.connect(self.api_key)

        async def reader() -> None:
            try:
                async for raw in self.upstream:
                    if isinstance(raw, bytes):
                        continue
                    event = json.loads(raw)
                    if event.get("type") in ("response.output_audio.delta", "response.audio.delta"):
                        self._audio_seq += 1
                        self.set_playing(True)
                    if self.open:
                        await self.ws.send_json({"kind": "xai_event", "event": event, "seq": self._audio_seq})
                    await on_event(event)
            except Exception:
                log.debug("relay upstream closed", exc_info=True)
            finally:
                await on_close()

        self._reader = asyncio.create_task(reader())

    def playback_report(self, playing: bool, seq: int | None) -> None:
        # Ignore stale "idle" reports that predate audio already sent to the browser.
        if not playing and seq is not None and seq < self._audio_seq:
            return
        self.set_playing(playing)

    async def send_audio(self, pcm16: bytes) -> None:
        if self.upstream:
            await self.send({"type": "input_audio_buffer.append", "audio": base64.b64encode(pcm16).decode()})

    async def send(self, event: dict[str, Any]) -> None:
        if self.upstream and self.open:
            await self.upstream.send(json.dumps(event))

    async def notify(self, message: dict[str, Any]) -> None:
        if self.open:
            await self.ws.send_json(message)

    async def close(self, reason: str = "") -> None:
        self.open = False
        if self.upstream:
            await self.upstream.close()
