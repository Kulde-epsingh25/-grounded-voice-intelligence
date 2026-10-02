"""Vapi integration package."""

from app.integrations.vapi.assistant import build_assistant_config, get_vapi_tools
from app.integrations.vapi.client import VapiClient
from app.integrations.vapi.knowledge_base import build_custom_kb_config
from app.integrations.vapi.schemas import (
    VapiAssistantConfig,
    VapiCustomKBConfig,
    VapiFunctionTool,
    VapiWebhookMessage,
)

__all__ = [
    "VapiClient",
    "build_assistant_config",
    "build_custom_kb_config",
    "get_vapi_tools",
    "VapiAssistantConfig",
    "VapiCustomKBConfig",
    "VapiFunctionTool",
    "VapiWebhookMessage",
]
