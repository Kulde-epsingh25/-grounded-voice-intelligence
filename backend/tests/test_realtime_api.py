"""
Tests for Realtime API endpoints and session lifecycle.
"""

from fastapi.testclient import TestClient
from app.main import app


def test_create_and_get_session():
    client = TestClient(app)
    resp = client.post("/api/v1/realtime/sessions", json={
        "session_id": "test_sess_01",
        "mode": "replay",
        "language": "en",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "test_sess_01"
    assert data["mode"] == "replay"
    assert data["status"] == "created"

    # Fetch session
    get_resp = client.get("/api/v1/realtime/sessions/test_sess_01")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["session_id"] == "test_sess_01"

    # Fetch stats
    stats_resp = client.get("/api/v1/realtime/sessions/test_sess_01/stats")
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()
    assert "latency_summary" in stats_data


def test_session_not_found():
    client = TestClient(app)
    resp = client.get("/api/v1/realtime/sessions/nonexistent_session")
    assert resp.status_code == 404
