"""Small HMAC-signed tokens for demo sessions and short-lived document view links (no external JWT dependency)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.config import get_settings


def _secret() -> bytes:
    s = get_settings()
    if s.session_secret:
        return s.session_secret.encode()
    # Stable across restarts, but changes when any role password changes (which invalidates old sessions).
    seed = "|".join(["equalpath-session", s.role_password_counsellor, s.role_password_hr_reviewer, s.role_password_auditor])
    return hashlib.sha256(seed.encode()).digest()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def sign(payload: dict, ttl_seconds: int) -> str:
    body = _b64(json.dumps({**payload, "exp": int(time.time()) + ttl_seconds}, separators=(",", ":")).encode())
    return f"{body}.{_b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())}"


def verify(token: str, typ: str) -> dict | None:
    try:
        body, sig = token.split(".", 1)
        good = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if data.get("typ") != typ or data.get("exp", 0) < time.time():
        return None
    return data
