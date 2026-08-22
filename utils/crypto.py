"""
API key encryption utilities using Fernet symmetric encryption.

API keys are stored encrypted at rest so admins and assigned users can
retrieve them later (copy button). Authentication is unaffected: it still
matches the separate SHA-256 hash in api_keys.key_hash.

The encryption key is derived deterministically from the existing SECRET_KEY
environment variable (hashed to satisfy Fernet's 32-byte key requirement),
so rotating SECRET_KEY also rotates API-key encryption.
"""
import base64
import hashlib
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from config.settings import get_settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    secret = get_settings().secret_key
    if not secret:
        raise RuntimeError("SECRET_KEY is not set; cannot encrypt/decrypt API keys")
    derived = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_api_key(plain_key: str) -> str:
    """
    Encrypt a plain-text API key for storage in api_keys.key_encrypted.

    Args:
        plain_key: The raw key string (e.g. 'agent-esp-a3f7...')

    Returns:
        str: Fernet token, safe to store as text
    """
    return _fernet().encrypt(plain_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_key: Optional[str]) -> Optional[str]:
    """
    Decrypt a stored API key.

    Returns None when the value is missing or undecryptable (legacy rows,
    rotated/missing API_KEY_ENCRYPTION_KEY) so callers can degrade to
    key=None instead of failing the request.
    """
    if not encrypted_key:
        return None
    try:
        return _fernet().decrypt(encrypted_key.encode("utf-8")).decode("utf-8")
    except (InvalidToken, RuntimeError):
        return None
