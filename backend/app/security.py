"""Field-level encryption for sensitive accessibility / health notes (kept separate from the profile)."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import get_settings

_DEV_SEED = "equalpath-local-demo-key-not-for-production"


def _fernet() -> tuple[Fernet, bool]:
    key = get_settings().data_encryption_key
    if key:
        return Fernet(key.encode()), True
    derived = base64.urlsafe_b64encode(hashlib.sha256(_DEV_SEED.encode()).digest())
    return Fernet(derived), False


def encrypt(text: str) -> str:
    return _fernet()[0].encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet()[0].decrypt(token.encode()).decode()


def production_key_configured() -> bool:
    return _fernet()[1]
