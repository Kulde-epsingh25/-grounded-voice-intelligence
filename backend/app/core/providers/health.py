"""
Provider Health Tracking and Circuit Breaker.

Maintains live runtime metrics and health states for all integrated providers:
- success_count, failure_count, timeout_count, rate_limit_count
- last_success, last_failure, consecutive_failures
- circuit breaker status: healthy, degraded, standby, unhealthy
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ProviderHealthRecord:
    provider: str
    category: str = "general"
    status: str = "standby"  # healthy, degraded, standby, unhealthy
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    rate_limit_count: int = 0
    consecutive_failures: int = 0
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    last_error: Optional[str] = None
    verification: str = "CONFIGURED"  # CONFIGURED, LIVE VERIFIED, MOCK VERIFIED, LOCAL VERIFIED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "category": self.category,
            "status": self.status,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "timeout_count": self.timeout_count,
            "rate_limit_count": self.rate_limit_count,
            "consecutive_failures": self.consecutive_failures,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "last_error": self.last_error,
            "verification": self.verification,
        }


class ProviderHealthTracker:
    """Singleton health tracker for active and fallback providers."""

    _instance: Optional[ProviderHealthTracker] = None

    def __new__(cls) -> ProviderHealthTracker:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._records: Dict[str, ProviderHealthRecord] = {}
        return cls._instance

    def register_provider(
        self,
        provider: str,
        category: str = "general",
        initial_status: str = "standby",
        verification: str = "CONFIGURED",
    ) -> ProviderHealthRecord:
        key = provider.lower()
        if key not in self._records:
            self._records[key] = ProviderHealthRecord(
                provider=key,
                category=category,
                status=initial_status,
                verification=verification,
            )
        return self._records[key]

    def record_success(
        self,
        provider: str,
        verification_type: str = "LIVE VERIFIED",
    ) -> None:
        key = provider.lower()
        rec = self.register_provider(key)
        rec.success_count += 1
        rec.consecutive_failures = 0
        rec.status = "healthy"
        rec.last_success = datetime.now(timezone.utc).isoformat()
        rec.verification = verification_type

    def record_failure(
        self,
        provider: str,
        error: str,
        error_type: str = "error",
    ) -> None:
        key = provider.lower()
        rec = self.register_provider(key)
        rec.failure_count += 1
        rec.consecutive_failures += 1
        rec.last_failure = datetime.now(timezone.utc).isoformat()
        rec.last_error = error

        err_lower = error.lower()
        if "timeout" in err_lower or "timed out" in err_lower or error_type == "timeout":
            rec.timeout_count += 1
        elif "429" in err_lower or "rate limit" in err_lower or error_type == "rate_limit":
            rec.rate_limit_count += 1

        # Small circuit breaker threshold
        if rec.consecutive_failures >= 5:
            rec.status = "unhealthy"
        elif rec.consecutive_failures >= 2:
            rec.status = "degraded"

    def is_healthy(self, provider: str) -> bool:
        rec = self._records.get(provider.lower())
        if not rec:
            return True
        return rec.status in ("healthy", "standby")

    def get_record(self, provider: str) -> Optional[ProviderHealthRecord]:
        return self._records.get(provider.lower())

    def get_all_records(self) -> Dict[str, Dict[str, Any]]:
        return {k: v.to_dict() for k, v in self._records.items()}

    def reset(self) -> None:
        """Reset all metrics (primarily for test isolation)."""
        self._records.clear()


def get_health_tracker() -> ProviderHealthTracker:
    return ProviderHealthTracker()
