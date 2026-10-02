"""Language, dialect, and register detection heuristics for Philippines and Indonesia markets.

NOTE: This is a heuristic text-based classifier intended as a development fallback.
When live ASR (e.g. Deepgram Nova 3 multilingual) is operational, the provider's
detected language metadata and audio confidence take precedence.
"""
from __future__ import annotations

import re
from app.localization.models import (
    Language,
    LanguageDetectionResult,
    Market,
    Register,
)

# Marker words for Filipino / Tagalog
FIL_MARKERS = {
    "ang", "ng", "mga", "sa", "ay", "si", "ni", "kay", "po", "opo", "ho",
    "ba", "na", "pa", "naman", "kasi", "kaya", "pero", "para", "kung", "kapag",
    "ito", "iyan", "iyon", "dito", "diyan", "doon", "ako", "ikaw", "siya",
    "kami", "tayo", "kayo", "sila", "gusto", "kailangan", "meron", "wala",
    "oo", "hindi", "salamat", "magkano", "ano", "paano", "kailan", "saan",
    "maganda", "magandang", "araw", "inyo", "nais", "ibig", "ko", "mo", "sanang",
    "sana", "magtanong", "ukol", "proteksyon", "buhay", "pamilya",
}

# Taglish code-switch indicators (Tagalog verb affixes attached to English roots or mixed markers)
TAGLISH_PREFIXES = ["mag-", "nag-", "i-", "pag-", "makapag-", "ma-", "pa-"]
TAGLISH_CONNECTORS = ["so", "actually", "like", "tapos", "kasi", "pero", "then", "which is"]

# Marker words for Indonesian (Formal)
ID_FORMAL_MARKERS = {
    "saya", "anda", "bapak", "ibu", "beliau", "kami", "mereka", "dengan",
    "untuk", "adalah", "sebagai", "bahwa", "dalam", "dapat", "akan", "telah",
    "apakah", "bagaimana", "mengapa", "mohon", "silakan", "terima kasih",
    "pembiayaan", "angsuran", "kewajiban", "persyaratan", "ketentuan",
}

# Marker words for Indonesian (Colloquial / Informal)
ID_COLLOQUIAL_MARKERS = {
    "aku", "kamu", "lu", "gue", "gw", "loe", "lo", "elu", "nggak", "gak", "ngga",
    "enggak", "udah", "udh", "gimana", "gmn", "bisa", "bs", "dong", "deh", "sih",
    "nih", "tuh", "aja", "kok", "banget", "bgt", "beneran", "kalo", "kl",
    "pengen", "nyari", "dp-nya", "cicilannya", "kak", "bro", "sis",
}


class LanguageDetector:
    """Heuristic language and register detector for localized voice bots."""

    @classmethod
    def detect(cls, text: str, market_hint: Market = Market.PH) -> LanguageDetectionResult:
        """Detect language, register, and code-switching in an utterance."""
        clean_text = text.strip()
        if not clean_text:
            default_lang = Language.TAGLISH if market_hint == Market.PH else Language.ID_COLLOQUIAL
            return LanguageDetectionResult(
                detected_language=default_lang,
                confidence=0.5,
                conversational_register=Register.COLLOQUIAL,
                code_switch_detected=False,
                code_switch_details="Empty utterance default",
                is_development_fallback=True,
            )

        tokens = [t.lower() for t in re.findall(r"\b[\w\-]+\b", clean_text)]
        token_count = max(1, len(tokens))

        if market_hint == Market.PH:
            return cls._detect_ph(tokens, token_count, clean_text)
        else:
            return cls._detect_id(tokens, token_count, clean_text)

    @classmethod
    def _detect_ph(cls, tokens: list[str], count: int, raw_text: str) -> LanguageDetectionResult:
        fil_matches = sum(1 for t in tokens if t in FIL_MARKERS)
        fil_ratio = fil_matches / count

        # Check for English business words (insurance / finance)
        en_business_words = {
            "insurance", "policy", "premium", "coverage", "beneficiary",
            "rider", "loan", "interest", "bank", "bancassurance", "plan",
            "renewal", "account", "monthly", "payment", "application",
        }
        en_matches = sum(1 for t in tokens if t in en_business_words)

        # Check for Taglish morphological code-switching (e.g., mag-apply, na-check)
        code_switch_patterns = sum(
            1 for t in tokens if re.match(r"^(?:mag|nag|i|pag|na)-[a-z]+", t)
        )

        has_politeness = any(t in tokens for t in ["po", "opo", "ho"])
        register = Register.FORMAL if has_politeness else Register.MIXED

        # Pure English detection
        if fil_matches == 0 and not any(t in tokens for t in ["po", "opo"]):
            return LanguageDetectionResult(
                detected_language=Language.EN,
                confidence=0.90,
                conversational_register=Register.PROFESSIONAL,
                code_switch_detected=False,
                is_development_fallback=True,
            )

        # Pure Tagalog detection (very high Tagalog ratio, no English keywords)
        if fil_ratio > 0.65 and en_matches == 0 and code_switch_patterns == 0:
            return LanguageDetectionResult(
                detected_language=Language.FIL,
                confidence=0.85,
                conversational_register=register,
                code_switch_detected=False,
                is_development_fallback=True,
            )

        # Taglish code-switching detected
        code_switch_details = f"Filipino marker ratio: {fil_ratio:.2f}, English keywords: {en_matches}"
        return LanguageDetectionResult(
            detected_language=Language.TAGLISH,
            confidence=0.88,
            conversational_register=register,
            code_switch_detected=True,
            code_switch_details=code_switch_details,
            is_development_fallback=True,
        )

    @classmethod
    def _detect_id(cls, tokens: list[str], count: int, raw_text: str) -> LanguageDetectionResult:
        formal_matches = sum(1 for t in tokens if t in ID_FORMAL_MARKERS)
        colloquial_matches = sum(1 for t in tokens if t in ID_COLLOQUIAL_MARKERS)

        # Check for English loanwords used in Indonesian consumer finance
        en_finance_loanwords = {
            "down", "payment", "dp", "tenor", "leasing", "multifinance",
            "rate", "credit", "score", "survey", "approval", "online",
        }
        loanword_matches = sum(1 for t in tokens if t in en_finance_loanwords)

        code_switch = loanword_matches > 0

        # Register classification
        if formal_matches > colloquial_matches and formal_matches > 0:
            detected_lang = Language.ID_FORMAL
            reg = Register.FORMAL
            conf = min(0.95, 0.70 + (formal_matches / count) * 0.5)
        elif colloquial_matches > 0 or ("kak" in tokens or "gimana" in tokens or "nggak" in tokens):
            detected_lang = Language.ID_COLLOQUIAL
            reg = Register.COLLOQUIAL
            conf = min(0.95, 0.70 + (colloquial_matches / count) * 0.5)
        else:
            detected_lang = Language.ID_MIXED
            reg = Register.MIXED
            conf = 0.75

        details = None
        if code_switch:
            details = f"English finance loanwords detected: {loanword_matches}"

        return LanguageDetectionResult(
            detected_language=detected_lang,
            confidence=conf,
            conversational_register=reg,
            code_switch_detected=code_switch,
            code_switch_details=details,
            is_development_fallback=True,
        )


def detect_language(text: str, market_hint: Market = Market.PH) -> LanguageDetectionResult:
    """Public helper for language detection."""
    return LanguageDetector.detect(text, market_hint=market_hint)
