"""
Provider Fallback and Health Architecture.
"""

from app.core.providers.exceptions import (
    AllProvidersFailedError,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    is_retryable_provider_error,
)
from app.core.providers.fallback import (
    ProviderCandidate,
    ProviderResult,
    check_simulated_mock_failure,
    execute_with_fallback,
)
from app.core.providers.health import (
    ProviderHealthRecord,
    ProviderHealthTracker,
    get_health_tracker,
)
from app.core.providers.registry import ProviderRegistry

__all__ = [
    "AllProvidersFailedError",
    "ProviderAuthenticationError",
    "ProviderCandidate",
    "ProviderConfigurationError",
    "ProviderError",
    "ProviderHealthRecord",
    "ProviderHealthTracker",
    "ProviderRateLimitError",
    "ProviderRegistry",
    "ProviderResult",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "check_simulated_mock_failure",
    "execute_with_fallback",
    "get_health_tracker",
    "is_retryable_provider_error",
]
