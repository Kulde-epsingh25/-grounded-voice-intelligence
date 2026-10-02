"""Core data models and configurations for native language voice bots and market localization."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class Market(str, Enum):
    """Supported market jurisdictions."""
    PH = "PH"
    ID = "ID"


class Language(str, Enum):
    """Supported market languages and dialects."""
    EN = "en"
    FIL = "fil"
    TAGLISH = "taglish"
    ID_FORMAL = "id_formal"
    ID_COLLOQUIAL = "id_colloquial"
    ID_MIXED = "id_mixed"


class Sector(str, Enum):
    """Business sectors for localized voice agents."""
    LIFE_INSURANCE = "life_insurance"
    BANCASSURANCE = "bancassurance"
    CONSUMER_FINANCE = "consumer_finance"
    MULTIFINANCE = "multifinance"


class Register(str, Enum):
    """Conversational register / formality level."""
    FORMAL = "formal"
    COLLOQUIAL = "colloquial"
    MIXED = "mixed"
    PROFESSIONAL = "professional"


class TerminologyItem(BaseModel):
    """Single domain terminology entry with localized variants and usage rules."""
    canonical_concept: str
    term: str
    market: Market
    language: Language
    domain: Sector
    allowed_variants: list[str] = Field(default_factory=list)
    notes: str = ""


class LanguageDetectionResult(BaseModel):
    """Result of language, register, and code-switch detection."""
    detected_language: Language
    confidence: float
    conversational_register: Register
    code_switch_detected: bool
    code_switch_details: Optional[str] = None
    is_development_fallback: bool = True

    @property
    def register(self) -> Register:
        return self.conversational_register


class LocalizationExample(BaseModel):
    """Documented localization pair showing cultural and linguistic adaptation."""
    category: str
    english_intent: str
    localized_wording: str
    why_localized: str
    cultural_consideration: str
    market: Market
    language: Language
    conversational_register: Register

    @property
    def register(self) -> Register:
        return self.conversational_register


class LocalizedPhrasingSet(BaseModel):
    """Complete collection of conversational phrasing for a market and language."""
    greeting: list[str]
    permission_request: list[str]
    qualification_prompts: dict[str, str]
    objection_responses: dict[str, str]
    clarification: list[str]
    fallback: list[str]
    escalation: list[str]
    closing: list[str]


class MarketConfig(BaseModel):
    """Complete localized market configuration."""
    market: Market
    sector: Sector
    supported_languages: list[Language]
    default_language: Language
    default_register: Register
    transcriber_config: dict[str, Any]
    tts_config: dict[str, Any]
    greeting_style: str
    fallback_style: str
    escalation_style: str
    terminology: list[TerminologyItem] = Field(default_factory=list)
    phrasings: dict[Language, LocalizedPhrasingSet] = Field(default_factory=dict)
    politeness_particles: list[str] = Field(default_factory=list)
