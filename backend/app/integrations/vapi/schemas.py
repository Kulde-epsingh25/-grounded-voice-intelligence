"""
Vapi Integration — Schemas.

Pydantic models for Vapi Assistant configurations, Custom Knowledge Base,
Function Tools, and Webhook payloads.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class VapiCustomKBConfig(BaseModel):
    """Configuration for Vapi Custom Knowledge Base."""
    provider: str = "custom-knowledge-base"
    server: dict[str, str] = Field(
        default_factory=lambda: {"url": "http://localhost:8000/kb/search"}
    )
    description: str = "Official Business Loan Knowledge Base for grounded factual retrieval."


class VapiToolFunctionParameter(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class VapiFunctionTool(BaseModel):
    """Vapi Function Tool definition."""
    type: str = "function"
    function: dict[str, Any]


class VapiAssistantConfig(BaseModel):
    """Full Vapi Assistant configuration model."""
    name: str = "Business Loan Qualification Assistant"
    model: dict[str, Any] = Field(
        default_factory=lambda: {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.2,
        }
    )
    voice: dict[str, Any] = Field(
        default_factory=lambda: {
            "provider": "11labs",
            "voiceId": "sarah",
        }
    )
    transcriber: Optional[dict[str, Any]] = None
    firstMessage: str = "Hello, thank you for calling commercial lending. I can help answer questions or see what loan products your business qualifies for. How can I help you today?"
    knowledgeBase: Optional[VapiCustomKBConfig] = None
    tools: list[VapiFunctionTool] = Field(default_factory=list)
    serverUrl: str = "http://localhost:8000/api/v1/vapi/webhook"
    recordingEnabled: bool = True
    endCallPhrases: list[str] = Field(
        default_factory=lambda: ["goodbye", "bye", "have a good day"]
    )


class VapiWebhookMessage(BaseModel):
    """Incoming webhook from Vapi."""
    type: str
    call: Optional[dict[str, Any]] = None
    toolCalls: Optional[list[dict[str, Any]]] = None
    message: Optional[dict[str, Any]] = None
