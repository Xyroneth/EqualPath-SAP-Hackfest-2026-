"""Runtime configuration. Every secret comes from environment variables (see .env.example)."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"), extra="ignore")

    # --- AI provider selection: auto | sap_ai_core | openai | demo
    llm_provider: str = "auto"
    llm_timeout_seconds: float = 60.0

    # --- SAP AI Core, generative AI hub
    aicore_service_key: str | None = None  # full service-key JSON (alternative to the fields below)
    aicore_auth_url: str | None = None
    aicore_client_id: str | None = None
    aicore_client_secret: str | None = None
    aicore_base_url: str | None = None  # AI_API_URL, e.g. https://api.ai.<region>.aws.ml.hana.ondemand.com
    aicore_resource_group: str = "default"
    aicore_mode: str = "orchestration"  # orchestration | foundation
    aicore_orchestration_deployment_url: str | None = None
    aicore_deployment_id: str | None = None  # foundation-model deployment (OpenAI-compatible chat)
    aicore_model_name: str = "gpt-4o-mini"
    aicore_api_version: str = "2024-10-21"
    aicore_enable_dpi_masking: bool = False

    # --- OpenAI-compatible fallback
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # --- Persistence: sqlite | hana
    repository: str = "sqlite"
    sqlite_path: str = str(BACKEND_DIR / "equalpath.db")
    checkpoint_path: str = str(BACKEND_DIR / "equalpath_checkpoints.db")
    hana_host: str | None = None
    hana_port: int = 443
    hana_user: str | None = None
    hana_password: str | None = None
    hana_schema: str = "EQUALPATH"

    # --- Identity: local | xsuaa
    identity_provider: str = "local"
    # Local demo sign-in for staff roles. CHANGE these before showing the app to anyone outside the team.
    role_password_counsellor: str = "Counsel@2026"
    role_password_hr_reviewer: str = "HRreview@2026"
    role_password_auditor: str = "Audit@2026"
    session_secret: str | None = None
    session_ttl_hours: int = 8
    login_max_attempts: int = 5
    login_lock_seconds: int = 60

    # --- SAP Build Process Automation (final human review workflow)
    sbpa_api_url: str | None = None  # e.g. https://spa-api-gateway-bpi-<region>-prod.cfapps.<region>.hana.ondemand.com
    sbpa_token_url: str | None = None
    sbpa_client_id: str | None = None
    sbpa_client_secret: str | None = None
    sbpa_definition_id: str | None = None  # process definition id of the EQUALPATH review process
    sbpa_callback_secret: str | None = None  # shared secret the SAP Build action sends back to EQUALPATH

    # --- Privacy
    data_encryption_key: str | None = None  # Fernet key for sensitive accommodation notes

    # --- Demo pacing (visual only; reported durations exclude it)
    demo_step_delay_ms: int = 450

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    def aicore_key_fields(self) -> dict:
        """Resolve SAP AI Core credentials from a service key JSON, individual env vars, or a CF binding."""
        fields = {
            "auth_url": self.aicore_auth_url,
            "client_id": self.aicore_client_id,
            "client_secret": self.aicore_client_secret,
            "base_url": self.aicore_base_url,
        }
        raw = self.aicore_service_key or _vcap_credentials("aicore")
        if raw:
            key = json.loads(raw) if isinstance(raw, str) else raw
            fields = {
                "auth_url": fields["auth_url"] or key.get("url"),
                "client_id": fields["client_id"] or key.get("clientid"),
                "client_secret": fields["client_secret"] or key.get("clientsecret"),
                "base_url": fields["base_url"] or (key.get("serviceurls") or {}).get("AI_API_URL"),
            }
        return fields

    def aicore_configured(self) -> bool:
        f = self.aicore_key_fields()
        has_target = bool(self.aicore_orchestration_deployment_url or self.aicore_deployment_id)
        return all(f.values()) and has_target

    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)

    def hana_configured(self) -> bool:
        return bool(self.hana_host and self.hana_user and self.hana_password)

    def sbpa_configured(self) -> bool:
        return bool(self.sbpa_api_url and self.sbpa_token_url and self.sbpa_client_id and self.sbpa_client_secret and self.sbpa_definition_id)


def _vcap_credentials(label: str) -> dict | None:
    """Read service credentials from a Cloud Foundry binding (VCAP_SERVICES) when running on SAP BTP."""
    raw = os.environ.get("VCAP_SERVICES")
    if not raw:
        return None
    try:
        services = json.loads(raw)
    except json.JSONDecodeError:
        return None
    for instances in services.get(label, []) or []:
        return instances.get("credentials")
    return None


def running_on_btp() -> bool:
    return "VCAP_APPLICATION" in os.environ


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_json(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)
