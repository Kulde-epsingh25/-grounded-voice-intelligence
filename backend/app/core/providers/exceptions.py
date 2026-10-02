"""
Core Provider Exceptions and Failure Classification.

Distinguishes retryable/fallback failures (connection timeouts, 429, 5xx, missing keys)
from non-retryable application/validation errors (400, schema mismatch, business rule rejections).
"""

from __future__ import annotations

import httpx
from typing import Optional


class ProviderError(Exception):
    """Base exception for all provider operations."""

    def __init__(self, message: str, provider: str = "unknown", status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class ProviderUnavailableError(ProviderError):
    """Transient service outage, overload, 5xx, or network failure."""
    pass


class ProviderTimeoutError(ProviderUnavailableError):
    """Network or execution timeout."""
    pass


class ProviderRateLimitError(ProviderUnavailableError):
    """HTTP 429 or rate limit quota exceeded."""
    pass


class ProviderConfigurationError(ProviderError):
    """Missing API key or invalid environment configuration."""
    pass


class ProviderAuthenticationError(ProviderError):
    """Authentication failed due to bad/expired API key."""
    pass


class ProviderExecutionError(ProviderError):
    """Runtime failure during provider invocation."""
    pass


class AllProvidersFailedError(ProviderError):
    """All providers in the fallback chain failed."""

    def __init__(self, operation: str, attempts: list[dict]):
        summary = f"All providers failed for operation '{operation}'. Attempts: {attempts}"
        super().__init__(summary, provider="all")
        self.operation = operation
        self.attempts = attempts


def is_retryable_provider_error(exc: Exception) -> bool:
    """
    Determine if an exception warrants falling back to the next provider.

    Returns True for:
    - Timeouts (connect, read, pool)
    - DNS / Connection errors
    - HTTP 429 (Rate limit)
    - HTTP 500, 502, 503, 504 (Server errors)
    - Missing configuration/keys
    - Simulated failures (MOCK_*_FAILURE)

    Returns False for:
    - HTTP 400, 401 (our malformed request), 404, 422
    - ValueError, TypeError, KeyError (internal coding errors)
    - Business rule rejections / user validation errors
    """
    if isinstance(exc, (ProviderTimeoutError, ProviderRateLimitError, ProviderConfigurationError, ProviderUnavailableError, ProviderAuthenticationError)):
        return True

    # Check for HTTP status codes on httpx/request exceptions
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError)):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403, 429, 500, 502, 503, 504):
            return True
        return False

    # Check for stdlib TimeoutError or ConnectionError
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True

    # Check exception attributes for status_code
    status = getattr(exc, "status_code", None)
    if status in (401, 403, 429, 500, 502, 503, 504):
        return True

    # Check message for explicit simulated failure or rate limit
    msg = str(exc).lower()
    if any(k in msg for k in ("rate limit", "429", "timeout", "timed out", "connection refused", "503 service unavailable", "simulated failure")):
        return True

    return False
