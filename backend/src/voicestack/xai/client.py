"""Thin async client for the xAI REST endpoints Voice Stack uses.

Endpoint shapes follow docs.x.ai (speech-to-speech, SIP, ephemeral tokens, voice, custom voices).
"""

from __future__ import annotations

from typing import Any

import httpx

from voicestack.config import get_settings


class XAIError(Exception):
    def __init__(self, status: int, message: str, body: Any = None):
        super().__init__(f"xAI API {status}: {message}")
        self.status = status
        self.message = message
        self.body = body


def _error_message(resp: httpx.Response) -> tuple[str, Any]:
    try:
        body = resp.json()
    except Exception:
        return resp.text[:500] or resp.reason_phrase, None
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err), body
        if err:
            return str(err), body
        if body.get("message"):
            return str(body["message"]), body
    return str(body)[:500], body


class XAIClient:
    def __init__(self, api_key: str, *, base_url: str | None = None, timeout: float = 30.0):
        settings = get_settings()
        self.api_key = api_key
        self.base_url = (base_url or settings.xai_api_base).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def __aenter__(self) -> XAIClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        resp = await self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            msg, body = _error_message(resp)
            raise XAIError(resp.status_code, msg, body)
        return resp

    async def _json(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = await self._request(method, path, **kwargs)
        if not resp.content:
            return {}
        return resp.json()

    # Key validation -------------------------------------------------------
    async def validate(self) -> dict[str, Any]:
        """Cheap authenticated call used when a key is saved."""
        return await self._json("GET", "/v1/models")

    # Ephemeral tokens -----------------------------------------------------
    async def create_client_secret(self, seconds: int, session: dict[str, Any] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"expires_after": {"seconds": seconds}}
        if session:
            body["session"] = session
        return await self._json("POST", "/v1/realtime/client_secrets", json=body)

    # Voices ---------------------------------------------------------------
    async def list_voices(self) -> list[dict[str, Any]]:
        data = await self._json("GET", "/v1/tts/voices")
        return data.get("voices", []) if isinstance(data, dict) else data

    async def tts(self, text: str, voice_id: str, *, language: str = "en", speed: float | None = None) -> bytes:
        body: dict[str, Any] = {"text": text, "voice_id": voice_id, "language": language}
        if speed is not None:
            body["speed"] = speed
        resp = await self._request("POST", "/v1/tts", json=body)
        return resp.content

    async def list_custom_voices(self, limit: int = 100) -> list[dict[str, Any]]:
        voices: list[dict[str, Any]] = []
        token: str | None = None
        while True:
            params: dict[str, Any] = {"limit": limit}
            if token:
                params["pagination_token"] = token
            data = await self._json("GET", "/v1/custom-voices", params=params)
            voices.extend(data.get("voices", []))
            token = data.get("pagination_token")
            if not token:
                return voices

    async def create_custom_voice(
        self, file_name: str, content: bytes, content_type: str, fields: dict[str, str]
    ) -> dict[str, Any]:
        files = {"file": (file_name, content, content_type)}
        data = {k: v for k, v in fields.items() if v}
        return await self._json("POST", "/v1/custom-voices", files=files, data=data, timeout=120)

    async def update_custom_voice(self, voice_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        return await self._json("PATCH", f"/v1/custom-voices/{voice_id}", json=patch)

    async def delete_custom_voice(self, voice_id: str) -> dict[str, Any]:
        return await self._json("DELETE", f"/v1/custom-voices/{voice_id}")

    # Phone numbers (SIP) --------------------------------------------------
    async def create_phone_number(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self._json("POST", "/v2/phone-numbers", json=body)

    async def list_phone_numbers(self) -> list[dict[str, Any]]:
        numbers: list[dict[str, Any]] = []
        token: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 100}
            if token:
                params["pagination_token"] = token
            data = await self._json("GET", "/v2/phone-numbers", params=params)
            numbers.extend(data.get("phone_numbers", []))
            token = data.get("pagination_token")
            if not token:
                return numbers

    async def delete_phone_number(self, phone_number_id: str) -> None:
        await self._request("DELETE", f"/v2/phone-numbers/{phone_number_id}")

    # Call control ---------------------------------------------------------
    async def refer_call(self, call_id: str, target_uri: str, timeout: float = 90.0) -> dict[str, Any]:
        """Blocks until the transfer resolves. Returns {"ok": bool, "status": int, "error": str|None}."""
        resp = await self._client.post(f"/v1/realtime/calls/{call_id}/refer", json={"target_uri": target_uri}, timeout=timeout)
        if resp.status_code == 200:
            return {"ok": True, "status": 200, "error": None}
        msg, _ = _error_message(resp)
        return {"ok": False, "status": resp.status_code, "error": msg}

    async def hangup_call(self, call_id: str) -> None:
        await self._request("POST", f"/v1/realtime/calls/{call_id}/hangup")

    # Files + Collections (API key; verified live against api.x.ai on 2026-10-12) ------------------
    async def upload_file(self, file_name: str, content: bytes, content_type: str) -> dict[str, Any]:
        files = {"file": (file_name, content, content_type)}
        return await self._json("POST", "/v1/files", files=files, data={"purpose": "assistants"}, timeout=120)

    async def create_collection(self, name: str, description: str = "") -> dict[str, Any]:
        body: dict[str, Any] = {"collection_name": name, "field_definitions": []}
        if description:
            body["collection_description"] = description
        return await self._json("POST", "/v1/collections", json=body)

    async def delete_collection(self, collection_id: str) -> None:
        await self._request("DELETE", f"/v1/collections/{collection_id}")

    async def add_document(self, collection_id: str, file_id: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
        body = {"collection_id": collection_id, "file_id": file_id, "fields": fields or {}}
        return await self._json("POST", f"/v1/collections/{collection_id}/documents/{file_id}", json=body)

    async def list_documents(self, collection_id: str) -> list[dict[str, Any]]:
        data = await self._json("GET", f"/v1/collections/{collection_id}/documents")
        return data.get("documents", [])

    async def delete_document(self, collection_id: str, file_id: str) -> None:
        await self._request("DELETE", f"/v1/collections/{collection_id}/documents/{file_id}")

    async def search_documents(self, query: str, collection_ids: list[str], limit: int = 5) -> list[dict[str, Any]]:
        body = {"query": query, "source": {"collection_ids": collection_ids}, "limit": limit}
        data = await self._json("POST", "/v1/documents/search", json=body)
        return data.get("matches", [])


def document_state(doc: dict[str, Any]) -> str:
    """Normalize a collection document's status to processing | processed | failed."""
    status = doc.get("status")
    if status in (2, "DOCUMENT_STATUS_PROCESSED"):
        return "processed"
    if status in (3, "DOCUMENT_STATUS_FAILED") or doc.get("error_message"):
        return "failed"
    return "processing"
