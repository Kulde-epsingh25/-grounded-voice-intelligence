"""Tests for the browser voice-agent API and conversation lifecycle."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.agent import _agent_sessions
from app.api import kb, leads, vapi
from app.core.config import AppConfig, VapiConfig
from app.core.providers import registry as provider_registry
from app.main import app


def test_preview_root_redirects_to_voice_demo():
    response = TestClient(app).get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/voice/"


def test_agent_turns_share_state_and_end_session():
    client = TestClient(app)
    call_id = "browser-agent-api-test"
    _agent_sessions.pop(call_id, None)

    first = client.post(
        "/api/v1/agent/turn",
        json={"call_id": call_id, "transcript": "We run a retail business."},
    )
    second = client.post(
        "/api/v1/agent/turn",
        json={"call_id": call_id, "transcript": "Our monthly revenue is around fifty."},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["turn_index"] == 2
    assert second.json()["state"]["business_type"] == "retail"
    assert "fifty thousand" in second.json()["response"].lower()
    assert "monthly_revenue" not in second.json()["state"]

    ended = client.delete(f"/api/v1/agent/sessions/{call_id}")
    assert ended.status_code == 204
    assert call_id not in _agent_sessions


def test_agent_turn_rejects_blank_transcript():
    response = TestClient(app).post(
        "/api/v1/agent/turn",
        json={"call_id": "blank-agent-api-test", "transcript": "   "},
    )
    assert response.status_code == 422


def test_vapi_web_sdk_does_not_require_private_management_key(monkeypatch):
    config = AppConfig(
        vapi=VapiConfig(
            api_key="",
            public_key="public-key",
            assistant_id="assistant-id",
            public_base_url="",
        )
    )
    monkeypatch.setattr(vapi, "get_config", lambda: config)
    monkeypatch.setattr(
        vapi,
        "build_assistant_config",
        lambda: SimpleNamespace(model_dump=lambda **kwargs: {"name": "test assistant"}),
    )

    response = TestClient(app).get("/api/v1/vapi/config")

    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert response.json()["management_api_configured"] is False
    assert response.json()["webhook_ready"] is False


def test_vapi_provider_status_uses_public_key_and_assistant_id(monkeypatch):
    config = AppConfig(
        vapi=VapiConfig(
            api_key="",
            public_key="public-key",
            assistant_id="assistant-id",
        )
    )
    monkeypatch.setattr(provider_registry, "get_config", lambda: config)

    assert provider_registry.ProviderRegistry.is_provider_configured("vapi") is True


def test_unprotected_admin_routes_are_closed_in_production(monkeypatch):
    client = TestClient(app)
    production_config = SimpleNamespace(
        is_production=True,
        webhook=SimpleNamespace(vapi_secret=""),
    )
    monkeypatch.setattr(leads, "get_config", lambda: production_config)
    monkeypatch.setattr(kb, "get_config", lambda: production_config)
    monkeypatch.setattr(vapi, "get_config", lambda: production_config)

    assert client.get("/api/v1/leads").status_code == 404
    assert client.get("/api/v1/leads/missing").status_code == 404
    assert client.post("/api/v1/kb/index", json={"records": []}).status_code == 403
    assert client.post("/api/v1/vapi/webhook", json={}).status_code == 503