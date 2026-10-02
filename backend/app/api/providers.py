"""
Provider Status and Health API Router.

Provides real-time visibility into primary and fallback provider statuses,
circuit breaker conditions, and configuration state without exposing credentials.
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter
from app.core.providers.health import get_health_tracker
from app.core.providers.registry import ProviderRegistry

router = APIRouter()


@router.get("/status")
async def get_provider_status() -> Dict[str, Any]:
    """
    Return provider configuration matrix across all modalities.
    No secrets or API keys are exposed.
    """
    overview = ProviderRegistry.get_status_overview()
    health_records = get_health_tracker().get_all_records()

    return {
        **overview,
        "_health": health_records,
    }


@router.get("/health")
async def get_provider_health_summary() -> Dict[str, Any]:
    """Return health tracker state and circuit breaker statuses."""
    return {
        "status": "healthy",
        "providers": get_health_tracker().get_all_records(),
    }
