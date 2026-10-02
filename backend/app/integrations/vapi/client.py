"""
Vapi Integration — API Client.

Supports:
1. Dry-run local configuration generation (when API key is missing or in offline mode)
2. Live assistant creation/updates via Vapi REST API when configured
3. Never leaks private API keys in logs or exceptions
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import httpx

from app.core.config import get_config
from app.core.logging import get_logger
from app.integrations.vapi.assistant import build_assistant_config
from app.integrations.vapi.schemas import VapiAssistantConfig

logger = get_logger(__name__)


class VapiClient:
    """Client for Vapi Voice Platform API with dry-run support."""

    VAPI_BASE_URL = "https://api.vapi.ai"

    def __init__(self, api_key: Optional[str] = None):
        config = get_config()
        self.api_key = api_key if api_key is not None else config.vapi.api_key

    def sync_assistant(
        self,
        server_base_url: str = "http://localhost:8000",
        assistant_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Create or update assistant in Vapi (or simulate in dry_run mode)."""
        assistant_config = build_assistant_config(server_base_url=server_base_url)
        payload = assistant_config.model_dump(mode="json")
        if "tools" in payload and payload["tools"]:
            payload["model"]["tools"] = payload.pop("tools")
        if "knowledgeBase" in payload and payload["knowledgeBase"]:
            kb = payload.pop("knowledgeBase")
            if isinstance(kb, dict):
                kb.pop("description", None)
            payload["model"]["knowledgeBase"] = kb

        if dry_run or not self.api_key:
            logger.info(
                "Vapi client running in DRY_RUN mode",
                extra={"extra_data": {"has_key": bool(self.api_key), "assistant_name": assistant_config.name}},
            )
            # Save configuration locally
            out_file = Path("config/vapi_assistant.json")
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            return {
                "status": "dry_run_success",
                "mode": "dry_run",
                "assistant_id": assistant_id or "asst_synthetic_demo_01",
                "config_saved_to": str(out_file),
                "assistant_name": assistant_config.name,
                "message": "Assistant schema validated and saved locally. No live Vapi API call made.",
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                if assistant_id:
                    # Update
                    url = f"{self.VAPI_BASE_URL}/assistant/{assistant_id}"
                    resp = client.patch(url, headers=headers, json=payload)
                else:
                    # Create
                    url = f"{self.VAPI_BASE_URL}/assistant"
                    resp = client.post(url, headers=headers, json=payload)

                resp.raise_for_status()
                data = resp.json()
                returned_id = data.get("id", assistant_id or "unknown")
                logger.info("Vapi assistant synced successfully", extra={"extra_data": {"assistant_id": returned_id}})
                return {
                    "status": "live_success",
                    "mode": "live",
                    "assistant_id": returned_id,
                    "data": data,
                }
        except Exception as e:
            logger.error("Vapi API call failed", extra={"extra_data": {"error": str(e)}})
            return {
                "status": "error",
                "mode": "live",
                "error": str(e),
                "message": "Failed to sync with live Vapi API. Verify VAPI_API_KEY and network access.",
            }
