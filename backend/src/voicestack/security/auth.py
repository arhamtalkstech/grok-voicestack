"""Access control for the builder UI and API.

AUTH_MODE=none   local development
AUTH_MODE=token  shared admin token (Authorization: Bearer <ADMIN_TOKEN> or ?token= for WebSockets)
AUTH_MODE=proxy  trust an identity-aware proxy (Cloud Run IAP, Cloudflare Access, oauth2-proxy)
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, WebSocket, status

from voicestack.config import get_settings


def _check(token: str | None, user_header: str | None) -> str:
    settings = get_settings()
    if settings.auth_mode == "none":
        return "local"
    if settings.auth_mode == "token":
        if not settings.admin_token:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "AUTH_MODE=token requires ADMIN_TOKEN")
        if token and hmac.compare_digest(token, settings.admin_token):
            return "admin"
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid admin token")
    if user_header:
        return user_header
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Request did not come through the identity proxy")


def _bearer(value: str | None) -> str | None:
    if value and value.lower().startswith("bearer "):
        return value[7:].strip()
    return None


async def require_user(request: Request) -> str:
    settings = get_settings()
    token = _bearer(request.headers.get("authorization")) or request.query_params.get("token")
    return _check(token, request.headers.get(settings.proxy_user_header))


async def require_ws_user(websocket: WebSocket) -> str:
    settings = get_settings()
    token = websocket.query_params.get("token") or _bearer(websocket.headers.get("authorization"))
    return _check(token, websocket.headers.get(settings.proxy_user_header))
