"""Shared isolation for tests that exercise stateful, file-backed services."""

import pytest

from app.services.leads import get_lead_service


@pytest.fixture(autouse=True)
def isolate_lead_storage(tmp_path):
    """Prevent any agent/tool test from rewriting committed sample lead data."""
    service = get_lead_service()
    original_storage_path = service.storage_path
    service.storage_path = tmp_path / "leads.json"
    service.clear()
    yield
    service.clear()
    service.storage_path = original_storage_path
    service._load()