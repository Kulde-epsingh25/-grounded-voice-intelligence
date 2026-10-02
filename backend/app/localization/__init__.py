"""Localization package for regional voice agents (Philippines and Indonesia)."""
from app.localization.agent import LocalizedVoiceAgent
from app.localization.base import BaseLocalizedAgent
from app.localization.fallback import LocalizedFallbackManager
from app.localization.indonesia import ID_MARKET_CONFIG
from app.localization.language import LanguageDetector, detect_language
from app.localization.market import get_market_config, list_supported_markets
from app.localization.models import (
    Language,
    LanguageDetectionResult,
    LocalizationExample,
    Market,
    MarketConfig,
    Register,
    Sector,
    TerminologyItem,
)
from app.localization.philippines import PH_MARKET_CONFIG
from app.localization.terminology import ID_TERMINOLOGY, PH_TERMINOLOGY

__all__ = [
    "BaseLocalizedAgent",
    "LocalizedVoiceAgent",
    "Market",
    "Language",
    "Sector",
    "Register",
    "TerminologyItem",
    "LanguageDetectionResult",
    "LocalizationExample",
    "MarketConfig",
    "PH_MARKET_CONFIG",
    "ID_MARKET_CONFIG",
    "PH_TERMINOLOGY",
    "ID_TERMINOLOGY",
    "LanguageDetector",
    "detect_language",
    "LocalizedFallbackManager",
    "get_market_config",
    "list_supported_markets",
]
