"""HTTP contract tests for the interactive Philippines and Indonesia demos."""

from fastapi.testclient import TestClient

from app.api.localization import _sessions
from app.main import app


def test_market_catalog_exposes_both_supported_locales():
    response = TestClient(app).get("/api/v1/localization/markets")
    assert response.status_code == 200
    markets = {item["market"]: item for item in response.json()}
    assert {"PH", "ID"} <= set(markets)
    assert markets["PH"]["sector"] == "bancassurance"
    assert markets["ID"]["sector"] == "multifinance"
    assert markets["PH"]["supported_languages"]
    assert markets["ID"]["asr"]["model"]


def test_localized_market_turn_reports_language_and_escalation():
    client = TestClient(app)
    cases = [
        ("PH", "Gusto ko po sanang makausap ang Bancassurance Specialist sa branch.", "ph-locale-api-test"),
        ("ID", "Halo Kak, saya mau ngomong sama petugas pembiayaan.", "id-locale-api-test"),
    ]
    for market, transcript, session_id in cases:
        _sessions.pop(session_id, None)
        response = client.post(
            f"/api/v1/localization/{market}/turn",
            json={"session_id": session_id, "transcript": transcript},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["market"] == market
        assert result["language"]
        assert result["register"]
        assert result["escalated"] is True
        assert result["response"]
        client.delete(f"/api/v1/localization/sessions/{session_id}")


def test_localized_session_cannot_switch_markets():
    client = TestClient(app)
    session_id = "market-lock-api-test"
    client.post(
        "/api/v1/localization/PH/turn",
        json={"session_id": session_id, "transcript": "Magandang araw po."},
    )
    response = client.post(
        "/api/v1/localization/ID/turn",
        json={"session_id": session_id, "transcript": "Halo Kak."},
    )
    assert response.status_code == 409
    client.delete(f"/api/v1/localization/sessions/{session_id}")