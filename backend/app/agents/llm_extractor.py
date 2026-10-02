"""
Q1 Voice Agent — LLM-Driven Intent & Entity Extractor.

Replaces the regex _extract_fields() with a real LLM call that:
- Understands natural language expressions (e.g. "I run a shop" -> RETAIL)
- Extracts qualification entities in structured JSON
- Detects high-level conversation intent
- Returns confidence scores

The LLM is the understanding layer ONLY.
Qualification decisions remain in the deterministic rules engine.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# System prompt for extraction — never asks the LLM to make eligibility calls
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM_PROMPT = """
You are a structured entity extraction engine for a commercial loan voice agent.

Given a customer utterance and conversation history, extract qualification entities and detect intent.

OUTPUT FORMAT — return ONLY a JSON object with no extra text:
{
  "intent": "<one of: qualification_info | knowledge_question | human_escalation | objection | greeting | acknowledgment | other>",
  "entities": {
    "business_type": "<string: retail | restaurant | manufacturing | construction | technology | logistics | trading | healthcare | services | wholesale | real_estate | agriculture | education | null>",
    "years_in_business": "<number or null>",
    "monthly_revenue": "<number or null — in absolute numeric value, e.g. 800000 for 8 lakh>",
    "requested_amount": "<number or null — in absolute numeric value>",
    "loan_purpose": "<string or null>",
    "contact_permission": "<true | false | null>"
  },
  "ambiguous_fields": ["<list of field names where value is unclear and needs clarification>"],
  "clarification_needed": "<string: specific clarification question if ambiguous, else null>",
  "confidence": "<high | medium | low>"
}

BUSINESS TYPE MAPPING EXAMPLES:
- shop, store, boutique, retail store, clothing store, electronics shop -> retail
- restaurant, cafe, eatery, food business, dhaba, hotel dining -> restaurant
- factory, production, assembly, manufacturing unit -> manufacturing
- builder, contractor, construction company -> construction
- software, tech startup, IT company, app development -> technology
- transport, logistics, delivery, freight -> logistics
- import export, trading company, distribution -> trading
- clinic, hospital, medical, pharmacy, health -> healthcare

REVENUE/AMOUNT CONVERSION:
- 8 lakh = 800000
- 50 lakh = 5000000
- 1 crore = 10000000
- fifty thousand = 50000
- 2 million = 2000000
- 500k = 500000
- bare "fifty" without denomination -> mark as ambiguous, clarification_needed = "Could you clarify if you mean fifty thousand or fifty million?"

YEARS CONVERSION:
- 18 months = 1.5
- two and a half years = 2.5

INTENT RULES:
- Questions about rates, documents, requirements, policies -> knowledge_question
- human, manager, person, speak to someone, representative -> human_escalation
- too high, too long, why do I need, objections -> objection
- Providing business information -> qualification_info

CRITICAL: Only extract what is clearly stated. Set null for anything not mentioned. Never invent values.
""".strip()


def _build_extraction_prompt(utterance: str, history: List[dict]) -> str:
    """Build the user prompt for extraction."""
    history_text = ""
    if history:
        lines = []
        for turn in history[-4:]:  # Last 4 turns for context
            lines.append(f"Agent: {turn.get('assistant', '')}")
            lines.append(f"Customer: {turn.get('user', '')}")
        history_text = "\nRecent conversation:\n" + "\n".join(lines) + "\n"

    return f"{history_text}\nCurrent customer utterance: {utterance}\n\nExtract entities and intent as JSON:"


def _parse_llm_json(raw: str) -> Optional[dict]:
    """Parse JSON from LLM output, handling markdown code fences."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = cleaned.rstrip("`").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def _entities_to_fields(entities: dict) -> Dict[str, Any]:
    """Convert extracted entities dict to qualification fields dict."""
    fields: Dict[str, Any] = {}

    if entities.get("business_type"):
        fields["business_type"] = entities["business_type"]

    if entities.get("years_in_business") is not None:
        try:
            fields["years_in_business"] = float(entities["years_in_business"])
        except (TypeError, ValueError):
            pass

    if entities.get("monthly_revenue") is not None:
        try:
            fields["monthly_revenue"] = float(entities["monthly_revenue"])
        except (TypeError, ValueError):
            pass

    if entities.get("requested_amount") is not None:
        try:
            fields["requested_amount"] = float(entities["requested_amount"])
        except (TypeError, ValueError):
            pass

    if entities.get("loan_purpose"):
        fields["loan_purpose"] = entities["loan_purpose"]

    if entities.get("contact_permission") is not None:
        fields["contact_permission"] = entities["contact_permission"]

    return fields


class ExtractionResult:
    """Result from LLM or regex extraction."""

    def __init__(
        self,
        intent: str,
        fields: Dict[str, Any],
        ambiguous_fields: List[str],
        clarification_needed: Optional[str],
        confidence: str,
        source: str = "llm",
        provider: str = "",
    ):
        self.intent = intent
        self.fields = fields
        self.ambiguous_fields = ambiguous_fields
        self.clarification_needed = clarification_needed
        self.confidence = confidence
        self.source = source
        self.provider = provider

    def has_ambiguity(self) -> bool:
        return bool(self.ambiguous_fields) or bool(self.clarification_needed)

    def __repr__(self) -> str:
        return (
            f"ExtractionResult(intent={self.intent!r}, fields={self.fields}, "
            f"ambiguous={self.ambiguous_fields}, source={self.source!r})"
        )


class LLMExtractor:
    """
    LLM-powered intent and entity extraction for the voice agent.

    Falls back to improved regex extraction if the LLM call fails,
    ensuring the agent remains functional without API access.
    """

    def __init__(self):
        self._llm_service = None

    def _get_llm_service(self):
        if self._llm_service is None:
            from app.core.providers.llm import get_llm_service
            self._llm_service = get_llm_service()
        return self._llm_service

    async def extract_async(
        self,
        utterance: str,
        history: Optional[List[dict]] = None,
    ) -> ExtractionResult:
        """
        Extract intent and entities from an utterance using the LLM.

        Returns ExtractionResult with entities, intent, and clarification info.
        Falls back to regex on LLM failure.
        """
        history = history or []
        prompt = _build_extraction_prompt(utterance, history)

        try:
            llm = self._get_llm_service()
            result = await llm.generate(
                prompt=prompt,
                system_prompt=_EXTRACTION_SYSTEM_PROMPT,
                max_tokens=350,
                temperature=0.1,
            )

            raw_output = result.output if hasattr(result, "output") else str(result)
            parsed = _parse_llm_json(raw_output)

            if parsed:
                entities = parsed.get("entities", {})
                fields = _entities_to_fields(entities)
                return ExtractionResult(
                    intent=parsed.get("intent", "other"),
                    fields=fields,
                    ambiguous_fields=parsed.get("ambiguous_fields", []),
                    clarification_needed=parsed.get("clarification_needed"),
                    confidence=parsed.get("confidence", "medium"),
                    source="llm",
                    provider=getattr(result, "provider", "unknown"),
                )
            else:
                logger.warning(
                    "LLM extractor returned unparseable JSON, falling back to regex",
                    extra={"extra_data": {"raw": raw_output[:200] if raw_output else ""}},
                )
        except Exception as e:
            logger.warning(
                "LLM extractor failed, falling back to regex",
                extra={"extra_data": {"error": str(e)}},
            )

        return self._regex_fallback(utterance)

    def extract_sync(self, utterance: str, history: Optional[List[dict]] = None) -> ExtractionResult:
        """
        Synchronous wrapper. If called from within a running event loop (FastAPI context),
        falls back immediately to regex to avoid nested loop issues.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.debug("Sync extract in running loop — using regex")
                return self._regex_fallback(utterance)
            return loop.run_until_complete(self.extract_async(utterance, history))
        except RuntimeError:
            return self._regex_fallback(utterance)

    def _regex_fallback(self, utterance: str) -> ExtractionResult:
        """
        Enhanced regex/keyword extraction covering natural-language patterns
        including Indian denominations (lakh/crore) and common business synonyms.
        """
        fields: Dict[str, Any] = {}
        ambiguous: List[str] = []
        clarification: Optional[str] = None
        lower = utterance.lower()

        # ---- Intent detection ----
        intent = "qualification_info"
        human_phrases = [
            "human", "representative", "specialist", "agent", "person",
            "manager", "operator", "speak with someone", "talk to someone",
            "connect me", "real person",
        ]
        objection_phrases = ["too long", "too high", "not fair", "that's too", "why do i need"]
        question_phrases = [
            "why", "how", "rate", "document", "requirement",
            "can i", "what is", "tell me about", "interested in", "qualify for",
        ]

        if any(p in lower for p in human_phrases):
            intent = "human_escalation"
        elif any(p in lower for p in objection_phrases):
            intent = "objection"
        elif any(p in lower for p in question_phrases) or "?" in utterance:
            intent = "knowledge_question"

        # ---- Business type — expanded vocabulary ----
        business_type_map = {
            "retail": ["retail", "shop", "store", "boutique", "showroom", "outlet",
                       "clothing store", "electronics shop", "general store"],
            "restaurant": ["restaurant", "cafe", "eatery", "food", "dhaba", "hotel",
                           "canteen", "bakery", "mess", "tiffin"],
            "manufacturing": ["manufacturing", "factory", "production", "assembly",
                              "plant", "mill", "fabrication"],
            "construction": ["construction", "builder", "contractor", "infrastructure",
                             "real estate developer", "civil"],
            "technology": ["technology", "tech", "software", "it company", "startup",
                           "app", "digital", "saas", "ecommerce", "e-commerce"],
            "logistics": ["logistics", "transport", "delivery", "freight", "courier",
                          "shipping", "trucking"],
            "trading": ["trading", "import", "export", "distribution", "wholesale",
                        "merchant", "commodities"],
            "healthcare": ["healthcare", "clinic", "hospital", "medical", "pharmacy",
                           "health", "diagnostic", "lab"],
            "services": ["services", "service provider", "consultancy", "consulting",
                         "agency", "outsourcing", "bpo"],
            "agriculture": ["agriculture", "farming", "farm", "agri", "crop", "dairy",
                            "poultry"],
            "education": ["education", "school", "training", "coaching", "institute",
                          "college", "tutoring"],
        }
        for btype, keywords in business_type_map.items():
            if any(kw in lower for kw in keywords):
                fields["business_type"] = btype
                break

        # ---- Years in business ----
        year_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b", lower)
        month_match = re.search(r"(\d+(?:\.\d+)?)\s*months?\b", lower)
        if year_match:
            fields["years_in_business"] = float(year_match.group(1))
        elif month_match:
            fields["years_in_business"] = round(float(month_match.group(1)) / 12.0, 2)

        # ---- Revenue — with denomination detection ----
        _bare_word_nums = {
            "ten": 10, "twenty": 20, "thirty": 30, "forty": 40,
            "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
            "ninety": 90, "hundred": 100,
        }
        _denom_patterns = [
            (r"(\d+(?:\.\d+)?)\s*(?:crore|cr)\b", 10_000_000),
            (r"(\d+(?:\.\d+)?)\s*(?:lakh|lac)\b", 100_000),
            (r"(\d+(?:\.\d+)?)\s*(?:million|m)\b", 1_000_000),
            (r"(\d+(?:\.\d+)?)\s*(?:thousand|k)\b", 1_000),
        ]

        rev_context = re.search(
            r"(?:monthly\s+revenue|revenue|monthly\s+income|earnings?|monthly|turnover)"
            r"\s+(?:is|of|are|was|around|about|roughly|approximately)?\s*"
            r"(?:about|around|roughly|approximately)?\s*"
            r"([^\.\,\?]+)",
            lower,
        )

        if rev_context:
            raw_rev = rev_context.group(1).strip()
            parsed_rev = None

            # Check denominated patterns first
            for pat, mult in _denom_patterns:
                m = re.search(pat, raw_rev)
                if m:
                    parsed_rev = float(m.group(1)) * mult
                    break

            if parsed_rev is not None:
                fields["monthly_revenue"] = parsed_rev
            else:
                # Check word numbers
                for word, num in _bare_word_nums.items():
                    if re.search(rf"\b{word}\b", raw_rev):
                        ambiguous.append("monthly_revenue")
                        clarification = (
                            f"Could you clarify if you mean {word} thousand or {word} million dollars?"
                        )
                        fields["monthly_revenue"] = num
                        break
                if "monthly_revenue" not in fields:
                    # Try plain numeric
                    num_m = re.search(r"[\d,]+(?:\.\d+)?", raw_rev.replace(",", ""))
                    if num_m:
                        val = float(num_m.group(0))
                        if val < 1000:
                            ambiguous.append("monthly_revenue")
                            clarification = (
                                f"Could you clarify if you mean {val:,.0f} thousand or "
                                f"{val:,.0f} million dollars?"
                            )
                        fields["monthly_revenue"] = val

        # ---- Loan amount ----
        loan_context = re.search(
            r"(?:loan\s*(?:of|amount)?|borrow(?:ing)?|need(?:ing)?|requesting?|looking\s+for)"
            r"\s+(?:around|about|roughly|approximately)?\s*"
            r"([^\.\,\?]+)",
            lower,
        )
        if loan_context:
            raw_loan = loan_context.group(1).strip()
            for pat, mult in _denom_patterns:
                m = re.search(pat, raw_loan)
                if m:
                    fields["requested_amount"] = float(m.group(1)) * mult
                    break
            if "requested_amount" not in fields:
                num_m = re.search(r"[\d,]+(?:\.\d+)?", raw_loan.replace(",", ""))
                if num_m:
                    fields["requested_amount"] = float(num_m.group(0))

        # ---- Contact permission ----
        if any(w in lower for w in [
            "yes", "sure", "ok", "agree", "proceed", "fine", "go ahead",
            "permission", "you have my", "contact me",
        ]):
            fields["contact_permission"] = True

        return ExtractionResult(
            intent=intent,
            fields=fields,
            ambiguous_fields=ambiguous,
            clarification_needed=clarification,
            confidence="medium",
            source="regex",
        )


# Global singleton
_extractor: Optional[LLMExtractor] = None


def get_extractor() -> LLMExtractor:
    global _extractor
    if _extractor is None:
        _extractor = LLMExtractor()
    return _extractor
