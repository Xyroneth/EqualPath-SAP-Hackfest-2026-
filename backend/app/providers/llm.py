"""LLMProvider interface with SAP AI Core (generative AI hub), OpenAI-compatible and deterministic demo providers."""
from __future__ import annotations

import json
import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings


class LLMError(RuntimeError):
    pass


@dataclass
class ProviderInfo:
    kind: str  # sap_ai_core | openai | demo
    label: str
    model: str
    live: bool
    detail: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class LLMProvider(ABC):
    kind = "abstract"

    @abstractmethod
    def info(self) -> ProviderInfo: ...

    @abstractmethod
    def complete_json(self, system: str, user: str) -> dict:
        """Return a parsed JSON object. Raise LLMError on transport or parse failure."""

    @property
    def is_live(self) -> bool:
        return self.info().live


def _parse_json(content: str) -> dict:
    content = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", content, re.S)
    if fence:
        content = fence.group(1)
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("model response did not contain a JSON object")
    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"model returned invalid JSON: {exc}") from exc


class DemoProvider(LLMProvider):
    """Deterministic mode. Agents use their rule-based engines; no model is called."""

    kind = "demo"

    def info(self) -> ProviderInfo:
        return ProviderInfo("demo", "Deterministic demo mode", "rule-based extractor v1", False,
                            "No LLM credentials configured. Agents run deterministic, auditable rules on the same schemas and validators.")

    def complete_json(self, system: str, user: str) -> dict:  # pragma: no cover - never used for generation
        raise LLMError("demo provider does not generate text")


class OpenAICompatibleProvider(LLMProvider):
    kind = "openai"

    def __init__(self, settings: Settings):
        self.s = settings

    def info(self) -> ProviderInfo:
        return ProviderInfo("openai", "OpenAI-compatible provider", self.s.openai_model, True,
                            f"Fallback provider at {httpx.URL(self.s.openai_base_url).host}. Used because SAP AI Core credentials are absent.")

    def complete_json(self, system: str, user: str) -> dict:
        try:
            r = httpx.post(
                f"{self.s.openai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.s.openai_api_key}"},
                json={
                    "model": self.s.openai_model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
                timeout=self.s.llm_timeout_seconds,
            )
            r.raise_for_status()
            return _parse_json(r.json()["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMError(f"OpenAI-compatible call failed: {exc}") from exc


class SAPAIProvider(LLMProvider):
    """SAP AI Core generative AI hub.

    mode=orchestration: POST {orchestration deployment URL}/completion (model-agnostic, optional SAP
    Data Privacy Integration masking). mode=foundation: POST /v2/inference/deployments/{id}/chat/completions.
    """

    kind = "sap_ai_core"
    _token: tuple[str, float] | None = None
    _lock = threading.Lock()

    def __init__(self, settings: Settings):
        self.s = settings
        self.keys = settings.aicore_key_fields()

    def info(self) -> ProviderInfo:
        target = "orchestration service" if self.s.aicore_mode == "orchestration" else f"deployment {self.s.aicore_deployment_id}"
        return ProviderInfo("sap_ai_core", "SAP AI Core - generative AI hub", self.s.aicore_model_name, True,
                            f"Live via {target}, resource group '{self.s.aicore_resource_group}'. Prompts are PII-redacted before sending.")

    def _access_token(self) -> str:
        with self._lock:
            if self._token and self._token[1] > time.time() + 60:
                return self._token[0]
            url = self.keys["auth_url"].rstrip("/")
            if not url.endswith("/oauth/token"):
                url += "/oauth/token"
            r = httpx.post(url, data={"grant_type": "client_credentials"},
                           auth=(self.keys["client_id"], self.keys["client_secret"]), timeout=30)
            r.raise_for_status()
            body = r.json()
            SAPAIProvider._token = (body["access_token"], time.time() + int(body.get("expires_in", 3600)))
            return body["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token()}", "AI-Resource-Group": self.s.aicore_resource_group,
                "Content-Type": "application/json"}

    def complete_json(self, system: str, user: str) -> dict:
        try:
            if self.s.aicore_mode == "orchestration":
                return self._orchestration(system, user)
            return self._foundation(system, user)
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"SAP AI Core call failed: {exc}") from exc

    def _orchestration(self, system: str, user: str) -> dict:
        base = self.s.aicore_orchestration_deployment_url.rstrip("/")
        modules: dict = {
            # The document text is passed as an input parameter so braces in it are never parsed as template syntax.
            "templating_module_config": {"template": [{"role": "system", "content": system}, {"role": "user", "content": "{{?payload}}"}]},
            "llm_module_config": {"model_name": self.s.aicore_model_name, "model_params": {"temperature": 0, "max_tokens": 4000}},
        }
        if self.s.aicore_enable_dpi_masking:
            modules["masking_module_config"] = {"masking_providers": [{
                "type": "sap_data_privacy_integration", "method": "anonymization",
                "entities": [{"type": "profile-person"}, {"type": "profile-email"}, {"type": "profile-phone"}, {"type": "profile-address"}],
            }]}
        r = httpx.post(f"{base}/completion", headers=self._headers(),
                       json={"orchestration_config": {"module_configurations": modules}, "input_params": {"payload": user}},
                       timeout=self.s.llm_timeout_seconds)
        r.raise_for_status()
        body = r.json()
        result = body.get("orchestration_result") or body.get("final_result")
        return _parse_json(result["choices"][0]["message"]["content"])

    def _foundation(self, system: str, user: str) -> dict:
        base = self.keys["base_url"].rstrip("/")
        url = f"{base}/v2/inference/deployments/{self.s.aicore_deployment_id}/chat/completions?api-version={self.s.aicore_api_version}"
        r = httpx.post(url, headers=self._headers(), timeout=self.s.llm_timeout_seconds, json={
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0, "max_tokens": 4000, "response_format": {"type": "json_object"},
        })
        r.raise_for_status()
        return _parse_json(r.json()["choices"][0]["message"]["content"])


_provider_override: LLMProvider | None = None


def set_provider_override(provider: LLMProvider | None) -> None:
    """Used by tests to inject a fake LLM."""
    global _provider_override
    _provider_override = provider


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    if _provider_override is not None:
        return _provider_override
    s = settings or get_settings()
    choice = s.llm_provider.lower()
    if choice == "sap_ai_core" or (choice == "auto" and s.aicore_configured()):
        if s.aicore_configured():
            return SAPAIProvider(s)
    if choice in ("openai", "auto", "sap_ai_core") and s.openai_configured():
        return OpenAICompatibleProvider(s)
    return DemoProvider()
