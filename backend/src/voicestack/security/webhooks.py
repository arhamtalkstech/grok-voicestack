"""Standard Webhooks v1 (HMAC-SHA256) signing and verification.

xAI signs `realtime.call.incoming` with the `dispatch_signing_secret` returned once when a phone
number is registered. Signed content is `{webhook-id}.{webhook-timestamp}.{body}`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time


class WebhookVerificationError(Exception):
    pass


def _secret_bytes(secret: str) -> bytes:
    raw = secret[len("whsec_") :] if secret.startswith("whsec_") else secret
    try:
        return base64.b64decode(raw + "=" * (-len(raw) % 4), validate=True)
    except Exception:
        return raw.encode()


def sign(secret: str, msg_id: str, timestamp: int, body: bytes) -> str:
    content = f"{msg_id}.{timestamp}.".encode() + body
    digest = hmac.new(_secret_bytes(secret), content, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def verify(secret: str, headers: dict[str, str], body: bytes, tolerance_s: int = 300) -> None:
    lower = {k.lower(): v for k, v in headers.items()}
    msg_id = lower.get("webhook-id")
    ts = lower.get("webhook-timestamp")
    sig_header = lower.get("webhook-signature")
    if not (msg_id and ts and sig_header):
        raise WebhookVerificationError("Missing webhook-id, webhook-timestamp, or webhook-signature header")
    try:
        timestamp = int(ts)
    except ValueError as exc:
        raise WebhookVerificationError("Invalid webhook-timestamp") from exc
    if abs(time.time() - timestamp) > tolerance_s:
        raise WebhookVerificationError("Webhook timestamp is outside the tolerance window")
    expected = sign(secret, msg_id, timestamp, body).split(",", 1)[1]
    for candidate in sig_header.split():
        version, _, value = candidate.partition(",")
        if version == "v1" and hmac.compare_digest(value, expected):
            return
    raise WebhookVerificationError("No matching v1 signature")
