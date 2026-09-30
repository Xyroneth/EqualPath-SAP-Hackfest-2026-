"""Provider tests: SAP AI Core request shape and fallback selection (HTTP is mocked; no credentials needed)."""
import json

import httpx

from app.config import Settings
from app.providers.llm import DemoProvider, OpenAICompatibleProvider, SAPAIProvider, get_llm_provider


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def _aicore_settings(**kw):
    key = {"clientid": "cid", "clientsecret": "sec", "url": "https://auth.example", "serviceurls": {"AI_API_URL": "https://api.ai.example"}}
    return Settings(aicore_service_key=json.dumps(key), aicore_orchestration_deployment_url="https://api.ai.example/v2/inference/deployments/d1",
                    aicore_deployment_id="d2", llm_provider="auto", openai_api_key=None, **kw)


def test_auto_selects_sap_ai_core_when_configured():
    assert isinstance(get_llm_provider(_aicore_settings()), SAPAIProvider)
    assert isinstance(get_llm_provider(Settings(llm_provider="auto", openai_api_key="k", aicore_service_key=None)), OpenAICompatibleProvider)
    assert isinstance(get_llm_provider(Settings(llm_provider="auto", openai_api_key=None, aicore_service_key=None)), DemoProvider)


def test_sap_ai_core_orchestration_request(monkeypatch):
    calls = []
    SAPAIProvider._token = None

    def fake_post(url, **kw):
        calls.append((url, kw))
        if url.endswith("/oauth/token"):
            return FakeResponse({"access_token": "tok", "expires_in": 3600})
        return FakeResponse({"orchestration_result": {"choices": [{"message": {"content": '```json\n{"skills": []}\n```'}}]}})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = SAPAIProvider(_aicore_settings(aicore_enable_dpi_masking=True)).complete_json("system", "user {with braces}")
    assert out == {"skills": []}
    url, kw = calls[1]
    assert url == "https://api.ai.example/v2/inference/deployments/d1/completion"
    assert kw["headers"]["AI-Resource-Group"] == "default" and kw["headers"]["Authorization"] == "Bearer tok"
    modules = kw["json"]["orchestration_config"]["module_configurations"]
    assert modules["templating_module_config"]["template"][1]["content"] == "{{?payload}}"
    assert kw["json"]["input_params"]["payload"] == "user {with braces}"
    assert modules["masking_module_config"]["masking_providers"][0]["type"] == "sap_data_privacy_integration"


def test_sap_ai_core_foundation_mode(monkeypatch):
    SAPAIProvider._token = None
    seen = {}

    def fake_post(url, **kw):
        if url.endswith("/oauth/token"):
            return FakeResponse({"access_token": "tok", "expires_in": 3600})
        seen["url"] = url
        return FakeResponse({"choices": [{"message": {"content": '{"ok": true}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert SAPAIProvider(_aicore_settings(aicore_mode="foundation")).complete_json("s", "u") == {"ok": True}
    assert seen["url"].startswith("https://api.ai.example/v2/inference/deployments/d2/chat/completions?api-version=")
