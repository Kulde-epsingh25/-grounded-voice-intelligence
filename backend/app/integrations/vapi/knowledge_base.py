"""
Vapi Integration — Custom Knowledge Base Configuration.

Generates Vapi Custom KB payload pointing to the Q2 retrieval endpoint.
"""

from __future__ import annotations

from app.integrations.vapi.schemas import VapiCustomKBConfig


def build_custom_kb_config(server_base_url: str = "http://localhost:8000") -> VapiCustomKBConfig:
    """Generate Vapi Custom Knowledge Base definition pointing to /kb/search."""
    clean_url = server_base_url.rstrip("/")
    endpoint = f"{clean_url}/kb/search"

    return VapiCustomKBConfig(
        provider="custom-knowledge-base",
        server={"url": endpoint},
        description="Grounded business loan knowledge base with confidence gating and citations.",
    )
