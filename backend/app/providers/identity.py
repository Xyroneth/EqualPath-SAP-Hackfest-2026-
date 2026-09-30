"""IdentityProvider: local password sign-in for the demo roles; XSUAA / SAP Cloud Identity Services on SAP BTP.

Local mode: the Candidate is the open, anonymous demo user (Priya). Counsellor, HR Reviewer and Auditor each need
their own password. A successful sign-in returns a signed, expiring token that the browser sends as a Bearer token.
"""
from __future__ import annotations

import hmac
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from app import tokens
from app.config import get_settings

ROLES = ("candidate", "counsellor", "hr_reviewer", "auditor")
STAFF_ROLES = ("counsellor", "hr_reviewer", "auditor")
ROLE_LABELS = {"candidate": "Candidate", "counsellor": "Counsellor", "hr_reviewer": "HR Reviewer", "auditor": "Auditor"}


@dataclass
class Principal:
    user_id: str
    role: str
    source: str

    @property
    def label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)


def role_password(role: str) -> str | None:
    s = get_settings()
    return {"counsellor": s.role_password_counsellor, "hr_reviewer": s.role_password_hr_reviewer, "auditor": s.role_password_auditor}.get(role)


def default_passwords_in_use() -> bool:
    s = get_settings()
    return (s.role_password_counsellor, s.role_password_hr_reviewer, s.role_password_auditor) == ("Counsel@2026", "HRreview@2026", "Audit@2026")


class LoginLimiter:
    """Slows down password guessing: after N failures for a role from one client, sign-in is locked for a while."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state: dict[tuple[str, str], list[float]] = {}

    def check(self, client: str, role: str) -> int:
        with self._lock:
            st = self._state.get((client, role))
            if st and st[1] > time.time():
                return int(st[1] - time.time()) + 1
        return 0

    def failed(self, client: str, role: str) -> None:
        s = get_settings()
        with self._lock:
            st = self._state.setdefault((client, role), [0, 0.0])
            st[0] += 1
            if st[0] >= s.login_max_attempts:
                st[0], st[1] = 0, time.time() + s.login_lock_seconds

    def ok(self, client: str, role: str) -> None:
        with self._lock:
            self._state.pop((client, role), None)


limiter = LoginLimiter()


def authenticate(role: str, password: str | None, client: str) -> dict:
    """Return a session dict or raise HTTPException. Never logs or returns the password."""
    if role not in ROLES:
        raise HTTPException(400, "Unknown role.")
    if role != "candidate":
        wait = limiter.check(client, role)
        if wait:
            raise HTTPException(429, f"Too many wrong attempts. Try again in {wait} seconds.")
        expected = role_password(role)
        if not expected or not hmac.compare_digest((password or "").encode(), expected.encode()):
            limiter.failed(client, role)
            raise HTTPException(401, "Wrong password.")
        limiter.ok(client, role)
    ttl = get_settings().session_ttl_hours * 3600
    return {"token": tokens.sign({"typ": "session", "role": role}, ttl), "role": role, "label": ROLE_LABELS[role], "expires_in": ttl}


class IdentityProvider(ABC):
    kind = "abstract"

    @abstractmethod
    def resolve(self, request: Request) -> Principal: ...


class LocalDemoIdentity(IdentityProvider):
    kind = "local_demo"

    def resolve(self, request: Request) -> Principal:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return Principal(user_id="demo-candidate", role="candidate", source="open demo candidate")
        data = tokens.verify(auth[7:], "session")
        if not data or data.get("role") not in ROLES:
            raise HTTPException(401, "Your session expired. Please sign in again.")
        return Principal(user_id=f"demo-{data['role']}", role=data["role"], source="local password sign-in")


class XSUAAIdentity(IdentityProvider):
    """Validates the JWT forwarded by the SAP approuter using the bound XSUAA instance.

    Role collections (xs-security.json) map to scopes: <xsappname>.Candidate, .Counsellor, .HRReviewer, .Auditor.
    Requires `pip install sap-xssec cfenv` and an XSUAA binding in VCAP_SERVICES.
    """

    kind = "xsuaa"
    _scope_map = {"Candidate": "candidate", "Counsellor": "counsellor", "HRReviewer": "hr_reviewer", "Auditor": "auditor"}

    def resolve(self, request: Request) -> Principal:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(401, "missing bearer token")
        try:
            from cfenv import AppEnv  # type: ignore
            from sap import xssec  # type: ignore
        except ImportError as exc:
            raise HTTPException(500, "XSUAA configured but sap-xssec/cfenv are not installed") from exc
        creds = AppEnv().get_service(label="xsuaa").credentials
        ctx = xssec.create_security_context(auth[7:], creds)
        for scope, role in self._scope_map.items():
            if ctx.check_local_scope(scope):
                return Principal(user_id=ctx.get_logon_name(), role=role, source="XSUAA")
        raise HTTPException(403, "no EQUALPATH role collection assigned")


def get_identity_provider() -> IdentityProvider:
    if get_settings().identity_provider == "xsuaa" and "VCAP_SERVICES" in os.environ:
        return XSUAAIdentity()
    return LocalDemoIdentity()


def current_principal(request: Request) -> Principal:
    return get_identity_provider().resolve(request)


def require_roles(*roles: str):
    def dep(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in roles:
            allowed = ", ".join(ROLE_LABELS[r] for r in roles)
            raise HTTPException(403, f"This needs the {allowed} role. You are signed in as {principal.label}.")
        return principal

    return dep
