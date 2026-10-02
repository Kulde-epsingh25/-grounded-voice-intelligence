"""
Core Fallback Runner and Telemetry Pipeline.

Executes operations through an ordered fallback chain of providers:
1. Primary Provider
   ↓ (retryable failure / missing key / mock)
2. Fallback Provider 1
   ↓ (retryable failure)
3. Fallback Provider 2
   ↓
All failed → Controlled Service Unavailable error.

Never loops, never falls back on bad client inputs or business errors,
and logs structured telemetry for every attempt.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import uuid4

from app.core.config import get_config
from app.core.logging import get_logger
from app.core.providers.exceptions import (
    AllProvidersFailedError,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    is_retryable_provider_error,
)
from app.core.providers.health import get_health_tracker

logger = get_logger(__name__)


@dataclass
class ProviderResult:
    """Standardized output envelope for any provider invocation."""
    success: bool
    provider: str
    model: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    fallback_used: bool = False
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    request_id: Optional[str] = None


@dataclass
class ProviderCandidate:
    """Represents an executable provider invocation candidate."""
    name: str
    execute_fn: Callable[..., Any]
    model: Optional[str] = None
    is_configured: bool = True
    verification_type: str = "LIVE VERIFIED"  # LIVE VERIFIED, LOCAL VERIFIED, MOCK VERIFIED


def check_simulated_mock_failure(provider_name: str) -> None:
    """Check if environment or config forces failure simulation for testing."""
    config = get_config()
    p_lower = provider_name.lower().replace("-", "_")

    # Check config mock flags
    mock_active = False
    if hasattr(config, "mock_failure"):
        mock_active = getattr(config.mock_failure, p_lower, False)

    # Check env var fallback: MOCK_<PROVIDER>_FAILURE
    env_key = f"MOCK_{p_lower.upper()}_FAILURE"
    env_val = os.getenv(env_key, "").lower() in ("true", "1", "yes", "on")

    if mock_active or env_val:
        logger.info(
            f"Simulated fault injection active for provider '{provider_name}'",
            extra={"extra_data": {"provider": provider_name, "simulated": True}}
        )
        if "deepgram" in p_lower:
            raise ProviderRateLimitError(f"Simulated 429 Rate Limit for {provider_name}", provider=provider_name, status_code=429)
        elif "eleven" in p_lower:
            raise ProviderUnavailableError(f"Simulated 503 Service Unavailable for {provider_name}", provider=provider_name, status_code=503)
        elif "vapi" in p_lower:
            raise ProviderUnavailableError(f"Simulated Vapi connection failure for {provider_name}", provider=provider_name, status_code=503)
        else:
            raise ProviderTimeoutError(f"Simulated timeout error for {provider_name}", provider=provider_name)


async def execute_with_fallback(
    providers: List[ProviderCandidate],
    operation: str,
    context: Optional[Dict[str, Any]] = None,
    timeout_per_provider: float = 20.0,
) -> ProviderResult:
    """
    Execute an operation across an ordered list of providers with automatic fallback.

    Guarantees:
    - Providers are executed in priority order (primary first).
    - Provider loop prevention: each provider name is executed at most once per request.
    - Controlled error propagation: non-retryable errors abort immediately without fallback.
    - Telemetry emission for monitoring and audit evidence.
    """
    context = context or {}
    request_id = context.get("request_id") or f"req_{uuid4().hex[:8]}"
    health_tracker = get_health_tracker()

    # Deduplicate providers in order to strictly prevent fallback loops
    seen_names = set()
    deduped_candidates: List[ProviderCandidate] = []
    for p in providers:
        p_name = p.name.lower()
        if p_name not in seen_names:
            seen_names.add(p_name)
            deduped_candidates.append(p)

    if not deduped_candidates:
        raise ProviderConfigurationError(f"No providers configured for operation '{operation}'")

    primary_name = deduped_candidates[0].name
    attempts: List[Dict[str, Any]] = []
    t_start_total = time.perf_counter()

    for idx, candidate in enumerate(deduped_candidates):
        is_primary = (idx == 0)
        provider_name = candidate.name
        t0 = time.perf_counter()

        # 1. Check configuration
        if not candidate.is_configured:
            err_msg = f"Provider '{provider_name}' missing credentials or configuration"
            logger.info(
                f"Skipping unconfigured provider: {provider_name}",
                extra={"extra_data": {"request_id": request_id, "provider": provider_name, "reason": "unconfigured"}}
            )
            attempts.append({
                "provider": provider_name,
                "status": "skipped",
                "error": err_msg,
                "latency_ms": 0.0,
            })
            continue

        # 2. Check circuit breaker status (unless forced testing or primary attempt)
        if not health_tracker.is_healthy(provider_name) and len(deduped_candidates) > 1 and not is_primary:
            logger.warning(
                f"Provider '{provider_name}' is currently degraded/unhealthy. Skipping.",
                extra={"extra_data": {"request_id": request_id, "provider": provider_name, "status": "degraded"}}
            )
            attempts.append({
                "provider": provider_name,
                "status": "circuit_open",
                "error": "Provider temporarily marked unhealthy by circuit breaker",
                "latency_ms": 0.0,
            })
            continue

        # 3. Execute Candidate
        try:
            # Check fault injection
            check_simulated_mock_failure(provider_name)

            # Invoke target function with timeout guard
            if inspect.iscoroutinefunction(candidate.execute_fn):
                coro = candidate.execute_fn()
                raw_data = await asyncio.wait_for(coro, timeout=timeout_per_provider)
            else:
                call_res = candidate.execute_fn()
                if inspect.isawaitable(call_res):
                    raw_data = await asyncio.wait_for(call_res, timeout=timeout_per_provider)
                else:
                    raw_data = call_res

            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            total_latency_ms = round((time.perf_counter() - t_start_total) * 1000, 2)

            health_tracker.record_success(provider_name, verification_type=candidate.verification_type)

            attempts.append({
                "provider": provider_name,
                "status": "success",
                "latency_ms": latency_ms,
            })

            fallback_used = not is_primary
            # Emit structured telemetry
            telemetry = {
                "request_id": request_id,
                "operation": operation,
                "primary_provider": primary_name,
                "primary_status": "success" if is_primary else "failed",
                "primary_error": attempts[0].get("error") if fallback_used else None,
                "fallback_provider": provider_name if fallback_used else None,
                "fallback_status": "success" if fallback_used else None,
                "fallback_used": fallback_used,
                "fallback_count": idx if fallback_used else 0,
                "final_provider": provider_name,
                "latency_ms": latency_ms,
                "total_latency_ms": total_latency_ms,
            }
            logger.info("Provider execution telemetry", extra={"extra_data": telemetry})

            return ProviderResult(
                success=True,
                provider=provider_name,
                model=candidate.model,
                data=raw_data,
                latency_ms=latency_ms,
                fallback_used=fallback_used,
                attempts=attempts,
                request_id=request_id,
            )

        except asyncio.TimeoutError as te:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            err_str = f"Execution timeout after {timeout_per_provider}s"
            health_tracker.record_failure(provider_name, err_str, error_type="timeout")
            attempts.append({
                "provider": provider_name,
                "status": "timeout",
                "error": err_str,
                "latency_ms": latency_ms,
            })
            logger.warning(
                f"Provider '{provider_name}' timed out. Falling back to next provider...",
                extra={"extra_data": {"request_id": request_id, "provider": provider_name, "error": err_str}}
            )

        except Exception as exc:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            err_str = str(exc)

            if is_retryable_provider_error(exc):
                health_tracker.record_failure(provider_name, err_str)
                attempts.append({
                    "provider": provider_name,
                    "status": "failed",
                    "error": err_str,
                    "latency_ms": latency_ms,
                })
                logger.warning(
                    f"Provider '{provider_name}' failed with retryable error: {err_str}. Advancing fallback chain...",
                    extra={"extra_data": {"request_id": request_id, "provider": provider_name, "error": err_str}}
                )
            else:
                # Non-retryable error (validation, client 400, business logic rejection)
                # DO NOT fallback blindly
                logger.error(
                    f"Non-retryable error in provider '{provider_name}': {err_str}. Aborting fallback chain.",
                    extra={"extra_data": {"request_id": request_id, "provider": provider_name, "error": err_str}}
                )
                raise exc

    # All candidate providers failed
    total_latency_ms = round((time.perf_counter() - t_start_total) * 1000, 2)
    failure_telemetry = {
        "request_id": request_id,
        "operation": operation,
        "primary_provider": primary_name,
        "primary_status": "failed",
        "fallback_used": True,
        "fallback_count": len(attempts),
        "final_provider": "none",
        "error": "SERVICE_UNAVAILABLE",
        "total_latency_ms": total_latency_ms,
        "attempts": attempts,
    }
    logger.error("All providers in fallback chain failed", extra={"extra_data": failure_telemetry})

    return ProviderResult(
        success=False,
        provider="none",
        model=None,
        data=None,
        error="SERVICE_UNAVAILABLE",
        latency_ms=total_latency_ms,
        fallback_used=True,
        attempts=attempts,
        request_id=request_id,
    )
