import time

import pytest

from voicestack.security.crypto import decrypt, encrypt
from voicestack.security.ssrf import BlockedDestination, check_url
from voicestack.security.webhooks import WebhookVerificationError, sign, verify
from voicestack.telephony.calls import extract_number

SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"


def headers(msg_id: str, ts: int, body: bytes, secret: str = SECRET) -> dict[str, str]:
    return {"webhook-id": msg_id, "webhook-timestamp": str(ts), "webhook-signature": sign(secret, msg_id, ts, body)}


def test_standard_webhooks_known_vector():
    # Test vector published by the Standard Webhooks specification.
    body = b'{"test": 2432232314}'
    assert sign(SECRET, "msg_p5jXN8AQM9LWM0D4loKWxJek", 1614265330, body) == "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE="


def test_verify_accepts_valid_and_rejects_tampered():
    body = b'{"type":"realtime.call.incoming"}'
    ts = int(time.time())
    verify(SECRET, headers("m1", ts, body), body)
    with pytest.raises(WebhookVerificationError):
        verify(SECRET, headers("m1", ts, body), body + b" ")
    with pytest.raises(WebhookVerificationError):
        verify(SECRET, headers("m1", ts - 3600, body), body)
    with pytest.raises(WebhookVerificationError):
        verify("whsec_" + "A" * 32, headers("m1", ts, body), body)


def test_encrypt_roundtrip():
    token = encrypt("xai-secret-value")
    assert token.startswith("v1:") and "xai-secret" not in token
    assert decrypt(token) == "xai-secret-value"


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:8000/x", "http://localhost/x", "http://10.0.0.5/", "http://169.254.169.254/latest", "file:///etc/passwd"],
)
async def test_ssrf_blocks_private(url):
    with pytest.raises(BlockedDestination):
        await check_url(url)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("+18005550199", "+18005550199"),
        ("<sip:+14155550100@sip.voice.x.ai>", "+14155550100"),
        ("14155550100", "+14155550100"),
        ("anonymous", None),
    ],
)
def test_extract_number(value, expected):
    assert extract_number(value) == expected
