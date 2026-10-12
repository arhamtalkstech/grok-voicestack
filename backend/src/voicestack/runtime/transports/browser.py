"""Browser-direct transport (default preview).

The browser holds the WebSocket to xAI, authenticated with an ephemeral token minted by our
backend, so audio never passes through the server and the API key never reaches the browser. The
browser forwards decision-relevant xAI events over the control WebSocket; the server replies with
commands the browser relays to xAI.
"""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from voicestack.runtime.transports.base import Transport


class BrowserDirectTransport(Transport):
    channel = "web"

    def __init__(self, ws: WebSocket):
        super().__init__()
        self.ws = ws
        self.open = True

    async def send(self, event: dict[str, Any]) -> None:
        if self.open:
            await self.ws.send_json({"kind": "command", "event": event})

    async def notify(self, message: dict[str, Any]) -> None:
        if self.open:
            await self.ws.send_json(message)

    async def close(self, reason: str = "") -> None:
        self.open = False
