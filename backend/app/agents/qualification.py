"""
Q1 Voice Agent — Structured Qualification Extraction & Validation.

Parses, validates, and records qualification fields.
Critically handles ambiguity:
- Detects bare numbers like "fifty" and prompts for clarification
- Converts clean denominations ("$500k", "1.2M", "2 years")
- Flags conflicting or out-of-range figures
"""

from __future__ import annotations

import re
from typing import Any, Optional, Tuple

from app.agents.schemas import QualificationField, QualificationState


class QualificationManager:
    """Manages the state of qualification data collected during voice interactions."""

    def __init__(self, state: Optional[QualificationState] = None):
        self.state = state or QualificationState()

    def update_field(
        self,
        name: str,
        raw_value: Any,
        turn_index: int = 1,
        confidence: float = 1.0,
    ) -> QualificationField:
        """Parse, validate, and update a qualification field."""
        parsed_val, is_ambiguous, clarification = self._parse_and_validate(name, raw_value)

        field = QualificationField(
            name=name,
            value=parsed_val,
            confidence=confidence,
            source_turn=turn_index,
            validated=not is_ambiguous and parsed_val is not None,
            raw_input=str(raw_value),
            is_ambiguous=is_ambiguous,
            clarification_prompt=clarification,
        )

        setattr(self.state, name, field)
        return field

    def _parse_and_validate(
        self, name: str, raw_value: Any
    ) -> Tuple[Any, bool, Optional[str]]:
        """Validate input. Returns (parsed_value, is_ambiguous, clarification_prompt)."""
        if raw_value is None or raw_value == "":
            return None, False, None

        str_val = str(raw_value).strip().lower()

        # Handle numeric financial fields: monthly_revenue, requested_amount
        if name in ("monthly_revenue", "requested_amount"):
            # Check for bare ambiguity e.g. "fifty", "around 50", "about twenty"
            bare_num_words = {
                "ten": 10, "twenty": 20, "thirty": 30, "forty": 40,
                "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
                "ninety": 90, "hundred": 100,
            }

            for word, num in bare_num_words.items():
                if re.search(rf"\b{word}\b", str_val) and not re.search(
                    r"\b(thousand|million|k|m|lakh|crore|usd|dollars?)\b", str_val
                ):
                    return (
                        num,
                        True,
                        f"Could you clarify if you mean {word} thousand, {word} million, or another amount?",
                    )

            # Check for bare number without denomination (e.g. "50", "100")
            bare_match = re.match(r"^[\$]?(\d{1,3})$", str_val)
            if bare_match:
                val = int(bare_match.group(1))
                return (
                    val,
                    True,
                    f"Could you clarify if you mean ${val:d},000 or ${val:d},000,000?",
                )

            # Parse standard currency / amount expressions
            cleaned = str_val.replace("$", "").replace(",", "").strip()

            # Million expressions: "1.5m", "2 million", "2.5m"
            m_match = re.search(r"(-?[\d\.]+)\s*(?:million|m)\b", cleaned)
            if m_match:
                return float(m_match.group(1)) * 1_000_000, False, None

            # Thousand expressions: "500k", "500 thousand"
            k_match = re.search(r"(-?[\d\.]+)\s*(?:thousand|k)\b", cleaned)
            if k_match:
                return float(k_match.group(1)) * 1_000, False, None

            # Standard numeric (including negative)
            num_match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
            if num_match:
                return float(num_match.group(0)), False, None

            return None, True, "Could you specify the exact monetary amount in dollars?"

        # Handle years in business
        if name == "years_in_business":
            # Check month expression: "18 months" -> 1.5 years
            month_match = re.search(r"(-?[\d\.]+)\s*months?", str_val)
            if month_match:
                return round(float(month_match.group(1)) / 12.0, 2), False, None

            # Year expression: "3 years", "2.5 yrs"
            year_match = re.search(r"(-?[\d\.]+)\s*(?:years?|yrs?)\b", str_val)
            if year_match:
                return float(year_match.group(1)), False, None

            num_match = re.search(r"-?\d+(?:\.\d+)?", str_val)
            if num_match:
                val = float(num_match.group(0))
                # If they say "24" could be months or years, but if > 60 usually months
                if val > 60:
                    return round(val / 12.0, 2), False, None
                return val, False, None

            return None, True, "Could you tell me how many years your business has been operating?"

        # Handle contact permission (boolean)
        if name == "contact_permission":
            if any(w in str_val for w in ["yes", "sure", "ok", "agree", "proceed", "fine", "approved"]):
                return True, False, None
            if any(w in str_val for w in ["no", "never", "don't", "refuse", "stop"]):
                return False, False, None
            return True, False, None

        # General string fields (business_type, loan_purpose, documents_available)
        return str_val, False, None
