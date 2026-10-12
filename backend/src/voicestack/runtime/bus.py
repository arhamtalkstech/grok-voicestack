"""In-process pub/sub for live sessions.

Every SessionController publishes UI events here. The live dock, the Landscape live overlay, and
the Telephony call monitor subscribe. Single-process by design; a multi-replica deployment pins a
session to the replica that owns its WebSocket, and the monitor shows that replica's sessions.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from voicestack.runtime.controller import SessionController


@dataclass
class LiveSession:
    controller: SessionController
    started_at: float = field(default_factory=time.time)


class Bus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self.sessions: dict[str, LiveSession] = {}

    def register(self, controller: SessionController) -> None:
        self.sessions[controller.conversation_id] = LiveSession(controller)
        self.publish_global({"type": "session.started", "conversation_id": controller.conversation_id})

    def unregister(self, conversation_id: str) -> None:
        self.sessions.pop(conversation_id, None)
        self.publish_global({"type": "session.ended", "conversation_id": conversation_id})

    def subscribe(self, key: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs[key].add(q)
        return q

    def unsubscribe(self, key: str, q: asyncio.Queue) -> None:
        self._subs[key].discard(q)

    def publish(self, conversation_id: str, event: dict[str, Any]) -> None:
        event = {**event, "conversation_id": conversation_id, "ts": time.time()}
        for key in (conversation_id, "*"):
            for q in list(self._subs.get(key, ())):
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(event)

    def publish_global(self, event: dict[str, Any]) -> None:
        event = {**event, "ts": time.time()}
        for q in list(self._subs.get("*", ())):
            if not q.full():
                q.put_nowait(event)


bus = Bus()
