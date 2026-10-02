"""
Q2 Knowledge Base — Terminology Normalization.

Normalizes terminology for search/indexing without overwriting original text.
Stores both original and normalized forms.
"""

from __future__ import annotations

import re

from app.core.logging import get_logger
from app.kb.models import TermEntry

logger = get_logger(__name__)

# Default terminology dictionary — synthetic examples only
# Real terminology comes from actual assessment data
DEFAULT_TERMINOLOGY: list[TermEntry] = [
    TermEntry(
        canonical_term="business_loan",
        aliases=["business financing", "SME loan", "commercial loan", "business credit"],
        normalized_form="business loan",
        category="product",
    ),
    TermEntry(
        canonical_term="monthly_revenue",
        aliases=["monthly income", "monthly turnover", "monthly sales", "revenue per month"],
        normalized_form="monthly revenue",
        category="qualification",
    ),
    TermEntry(
        canonical_term="loan_amount",
        aliases=["requested amount", "financing amount", "credit amount", "loan value"],
        normalized_form="loan amount",
        category="qualification",
    ),
    TermEntry(
        canonical_term="interest_rate",
        aliases=["rate of interest", "lending rate", "borrowing rate"],
        normalized_form="interest rate",
        category="terms",
    ),
    TermEntry(
        canonical_term="eligibility",
        aliases=["qualification", "qualification criteria", "eligibility criteria", "requirements"],
        normalized_form="eligibility",
        category="process",
    ),
]


class TerminologyNormalizer:
    """Normalizes terminology in text without destroying original content.

    Stores both original_text and normalized_text.
    """

    def __init__(self, entries: list[TermEntry] | None = None) -> None:
        self._entries = entries or DEFAULT_TERMINOLOGY
        self._alias_map: dict[str, str] = {}
        self._build_alias_map()

    def _build_alias_map(self) -> None:
        """Build a lookup from aliases to canonical normalized forms."""
        for entry in self._entries:
            for alias in entry.aliases:
                self._alias_map[alias.lower()] = entry.normalized_form

    def add_entry(self, entry: TermEntry) -> None:
        """Add a terminology entry."""
        self._entries.append(entry)
        for alias in entry.aliases:
            self._alias_map[alias.lower()] = entry.normalized_form

    def normalize(self, text: str) -> tuple[str, list[dict[str, str]]]:
        """Normalize terminology in text.

        Args:
            text: Original text.

        Returns:
            Tuple of (normalized_text, list of replacements made).
            The original text is NOT modified in-place.
        """
        normalized = text
        replacements = []

        # Sort aliases by length (longest first) to avoid partial matches
        sorted_aliases = sorted(self._alias_map.keys(), key=len, reverse=True)

        for alias in sorted_aliases:
            canonical = self._alias_map[alias]
            # Case-insensitive word-boundary replacement
            pattern = re.compile(re.escape(alias), re.IGNORECASE)
            matches = pattern.findall(normalized)
            if matches:
                normalized = pattern.sub(canonical, normalized)
                for match in matches:
                    replacements.append({
                        "original": match,
                        "normalized": canonical,
                    })

        if replacements:
            logger.info(
                "Terminology normalized",
                extra={"extra_data": {
                    "replacements_count": len(replacements),
                }},
            )

        return normalized, replacements

    @property
    def entries(self) -> list[TermEntry]:
        return list(self._entries)
