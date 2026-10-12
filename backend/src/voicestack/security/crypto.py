"""AES-GCM encryption for secrets at rest (API keys, webhook signing secrets, tool credentials)."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from voicestack.config import get_settings

log = logging.getLogger(__name__)
_PREFIX = "v1:"


def _derive(raw: str) -> bytes:
    try:
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    return hashlib.sha256(raw.encode()).digest()


@lru_cache
def _key() -> bytes:
    settings = get_settings()
    if settings.app_encryption_key:
        return _derive(settings.app_encryption_key)
    if settings.app_env == "production":
        raise RuntimeError("APP_ENCRYPTION_KEY is required when APP_ENV=production")
    # Development only: keep a generated key next to the local database.
    path = settings.data_dir / "encryption.key"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        os.chmod(path, 0o600)
        log.warning("Generated a development encryption key at %s. Set APP_ENCRYPTION_KEY in production.", path)
    return _derive(path.read_text().strip())


def encrypt(plaintext: str) -> str:
    nonce = secrets.token_bytes(12)
    ct = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return _PREFIX + base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt(token: str) -> str:
    if not token.startswith(_PREFIX):
        raise ValueError("Unknown ciphertext format")
    blob = base64.urlsafe_b64decode(token[len(_PREFIX) :])
    return AESGCM(_key()).decrypt(blob[:12], blob[12:], None).decode()


def last4(value: str) -> str:
    return value[-4:] if len(value) >= 4 else "****"
