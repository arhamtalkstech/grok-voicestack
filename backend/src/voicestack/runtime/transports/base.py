from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

from voicestack.config import get_settings


class Transport(ABC):
    """Moves events between a SessionController and xAI; tracks whether assistant audio is playing."""

    channel: str = "web"

    def __init__(self) -> None:
        self._idle = asyncio.Event()
        self._idle.set()
        self._estimated_until = 0.0

    @abstractmethod
    async def send(self, event: dict[str, Any]) -> None:
        """Send a client event to the xAI realtime session."""

    async def notify(self, message: dict[str, Any]) -> None:  # noqa: B027 - optional hook
        """Send a UI event to the client that owns this session (if any)."""

    async def close(self, reason: str = "") -> None:  # noqa: B027 - optional hook
        """Release the connection."""

    def set_playing(self, playing: bool) -> None:
        if playing:
            self._idle.clear()
        else:
            self._idle.set()

    def estimate_playback(self, seconds: float) -> None:
        """Fallback when the transport cannot observe playback (e.g. no output_audio_buffer events)."""
        self._estimated_until = max(self._estimated_until, time.monotonic() + seconds)

    async def wait_playback_idle(self) -> None:
        timeout = get_settings().playback_wait_timeout_s
        await asyncio.sleep(0.05)  # let in-flight playback state reports land
        try:
            await asyncio.wait_for(self._idle.wait(), timeout=timeout)
        except TimeoutError:
            pass
        remaining = self._estimated_until - time.monotonic()
        if remaining > 0:
            await asyncio.sleep(min(remaining, timeout))
