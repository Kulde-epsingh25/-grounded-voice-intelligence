"""
LLM Fallback Service.

Orchestrates LLM generation across an ordered fallback chain:
1. Primary: OpenAI (gpt-4o-mini)
2. Fallback 1: Gemini (gemini-2.5-flash)
3. Fallback 2: Groq (llama-3.3-70b-versatile)
4. Fallback 3: OpenRouter (llama-3.3-70b)
"""

from __future__ import annotations

import httpx
from typing import Any, Dict, List, Optional
from app.core.config import get_config
from app.core.logging import get_logger
from app.core.providers.fallback import (
    ProviderCandidate,
    ProviderResult,
    execute_with_fallback,
)
from app.core.providers.registry import ProviderRegistry

logger = get_logger(__name__)


class LLMService:
    """Provider-agnostic LLM caller with automatic fallback routing."""

    def __init__(self):
        self.config = get_config()
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0, limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _call_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        api_key = self.config.openai.api_key
        model = self.config.openai.llm_model or "gpt-4o-mini"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        client = self._get_client()
        resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def _call_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        api_key = self.config.gemini.api_key
        model = self.config.gemini.text_model or "gemini-3.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"[System Instructions]: {system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        client = self._get_client()
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            return "".join(p.get("text", "") for p in parts)
        return ""

    async def _call_groq(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        api_key = self.config.groq.api_key
        model = self.config.groq.model or "llama-3.3-70b-versatile"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        client = self._get_client()
        resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def _call_openrouter(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        api_key = self.config.openrouter.api_key
        model = self.config.openrouter.model or "nvidia/nemotron-3.5-lightning:free"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        client = self._get_client()
        resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        context: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """
        Execute LLM generation across OpenAI → Gemini → Groq → OpenRouter.
        """
        config = get_config()

        candidates = [
            ProviderCandidate(
                name="openai",
                model=config.openai.llm_model,
                is_configured=ProviderRegistry.is_provider_configured("openai"),
                verification_type="LIVE VERIFIED",
                execute_fn=lambda: self._call_openai(prompt, system_prompt, max_tokens, temperature),
            ),
            ProviderCandidate(
                name="gemini",
                model=config.gemini.text_model,
                is_configured=ProviderRegistry.is_provider_configured("gemini"),
                verification_type="LIVE VERIFIED",
                execute_fn=lambda: self._call_gemini(prompt, system_prompt, max_tokens, temperature),
            ),
            ProviderCandidate(
                name="groq",
                model=config.groq.model,
                is_configured=ProviderRegistry.is_provider_configured("groq"),
                verification_type="LIVE VERIFIED",
                execute_fn=lambda: self._call_groq(prompt, system_prompt, max_tokens, temperature),
            ),
            ProviderCandidate(
                name="openrouter",
                model=config.openrouter.model,
                is_configured=ProviderRegistry.is_provider_configured("openrouter"),
                verification_type="LIVE VERIFIED",
                execute_fn=lambda: self._call_openrouter(prompt, system_prompt, max_tokens, temperature),
            ),
        ]

        return await execute_with_fallback(
            providers=candidates,
            operation="llm_generation",
            context=context,
        )


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
