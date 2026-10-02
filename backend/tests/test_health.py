"""
AI Engineer Assessment — Health Endpoint Tests.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client: TestClient):
        """Health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, client: TestClient):
        """Health endpoint reports healthy status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_contains_required_fields(self, client: TestClient):
        """Health response contains all required fields."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
        assert "services" in data

    def test_health_contains_service_status(self, client: TestClient):
        """Health response contains service configuration status."""
        response = client.get("/health")
        services = response.json()["services"]
        assert "openai" in services
        assert "vapi" in services
        assert "deepgram" in services
        assert "elevenlabs" in services
        assert "qdrant" in services

    def test_health_does_not_expose_secrets(self, client: TestClient):
        """Health endpoint must not expose API keys or secrets."""
        response = client.get("/health")
        raw = response.text
        # No actual API key patterns should appear
        assert "sk-" not in raw
        assert "api_key" not in raw.lower() or "configured" in raw.lower()

    def test_health_reports_version(self, client: TestClient):
        """Health endpoint reports correct version."""
        response = client.get("/health")
        data = response.json()
        assert data["version"] == "0.1.0"
