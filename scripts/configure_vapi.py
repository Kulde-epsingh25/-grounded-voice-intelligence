"""
Q1 Voice Agent — Vapi Configuration Script.

Configures or exports the Vapi Assistant with custom knowledge base and tools.
Usage:
    python scripts/configure_vapi.py [--dry-run] [--server-url https://...]

Rules:
- Never prints private API keys
- Safe to repeat (idempotent)
- Defaults to DRY_RUN mode if VAPI_API_KEY is not configured
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_config
from app.core.logging import setup_logging
from app.integrations.vapi.client import VapiClient


def main() -> None:
    config = get_config()
    parser = argparse.ArgumentParser(description="Configure Vapi Voice Assistant")
    parser.add_argument(
        "--server-url",
        default="http://localhost:8000",
        help="Public base URL for webhooks and custom KB (e.g. from Cloudflare Tunnel)",
    )
    parser.add_argument(
        "--assistant-id",
        default=config.vapi.assistant_id,
        help="Target Vapi Assistant ID to update",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate schema and generate configuration locally without calling Vapi API",
    )
    args = parser.parse_args()

    dry_run = args.dry_run or not bool(config.vapi.api_key)

    print("=" * 60)
    print("VAPI VOICE ASSISTANT CONFIGURATION")
    print("=" * 60)
    print(f"Server Base URL: {args.server_url}")
    print(f"Assistant ID:    {args.assistant_id or 'Will create new'}")
    print(f"Mode:            {'DRY_RUN (Offline Schema Generation)' if dry_run else 'LIVE API DEPLOYMENT'}")
    print(f"Has API Key:     {bool(config.vapi.api_key)} (Key is hidden)")
    print(f"Has Public Key:  {bool(config.vapi.public_key)}")

    client = VapiClient()
    result = client.sync_assistant(
        server_base_url=args.server_url,
        assistant_id=args.assistant_id or None,
        dry_run=dry_run,
    )

    print("\nResult:")
    print(f"  Status:       {result.get('status')}")
    print(f"  Assistant ID: {result.get('assistant_id')}")
    if "config_saved_to" in result:
        print(f"  Saved config: {result.get('config_saved_to')}")
    if "error" in result:
        print(f"  Error Detail: {result.get('error')}")
    print(f"  Message:      {result.get('message', 'Completed')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
