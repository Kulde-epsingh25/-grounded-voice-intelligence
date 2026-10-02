"""Base abstract class for localized voice agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional
from app.agents.schemas import ConversationState, VoiceAgentTurn
from app.localization.language import LanguageDetector
from app.localization.models import (
    Language,
    LanguageDetectionResult,
    Market,
    MarketConfig,
    Register,
)


class BaseLocalizedAgent(ABC):
    """Abstract base class establishing the contract for market-localized voice agents."""

    def __init__(self, market_config: MarketConfig, call_id: Optional[str] = None):
        self.market_config = market_config
        self.call_id = call_id or f"loc-call-{market_config.market.value}"
        self.current_language: Language = market_config.default_language
        self.current_register: Register = market_config.default_register
        self.detected_code_switch: bool = False

    @abstractmethod
    def process_turn(self, utterance: str) -> VoiceAgentTurn:
        """Process caller turn with localized intent understanding and response generation."""
        pass

    def detect_language(self, utterance: str) -> LanguageDetectionResult:
        """Analyze caller utterance for language, register, and code-switching."""
        result = LanguageDetector.detect(utterance, market_hint=self.market_config.market)
        self.current_language = result.detected_language
        self.current_register = result.register
        self.detected_code_switch = result.code_switch_detected
        return result

    @abstractmethod
    def get_localized_fallback(self, reason: str) -> str:
        """Retrieve localized fallback preserving current language and register."""
        pass
