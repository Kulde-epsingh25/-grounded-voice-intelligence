"""
Q2 Knowledge Base — Content Cleaner.

Removes navigation, headers, footers, boilerplate, and normalizes content
without destroying semantic information.
"""

from __future__ import annotations

import re
import unicodedata

from app.core.logging import get_logger
from app.kb.models import (
    CleanedDocument,
    ExtractedDocument,
    ExtractedElement,
    ElementType,
)

logger = get_logger(__name__)

# Patterns that indicate navigation/boilerplate
_NAV_PATTERNS = [
    re.compile(r"^(home|about|contact|privacy|terms|sitemap|menu|login|sign up|sign in|register)\s*$", re.IGNORECASE),
    re.compile(r"^(cookie|accept|decline|preferences|settings)\s", re.IGNORECASE),
    re.compile(r"^©\s*\d{4}", re.IGNORECASE),
    re.compile(r"^all rights reserved", re.IGNORECASE),
    re.compile(r"^page \d+ of \d+$", re.IGNORECASE),
    re.compile(r"^\d+\s*$"),  # Standalone page numbers
]

# Patterns for repeated headers/footers
_FOOTER_PATTERNS = [
    re.compile(r"^confidential", re.IGNORECASE),
    re.compile(r"^internal use only", re.IGNORECASE),
    re.compile(r"^draft", re.IGNORECASE),
]


def _is_navigation(text: str) -> bool:
    """Check if text looks like navigation or boilerplate."""
    stripped = text.strip()
    return any(pat.search(stripped) for pat in _NAV_PATTERNS)


def _is_footer_header(text: str) -> bool:
    """Check if text looks like a repeated header/footer."""
    stripped = text.strip()
    if len(stripped) < 3:
        return True
    return any(pat.search(stripped) for pat in _FOOTER_PATTERNS)


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace without destroying structure."""
    # Normalize Unicode
    text = unicodedata.normalize("NFKC", text)
    # Collapse multiple spaces to single
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse more than 2 newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip lines
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _normalize_dates(text: str) -> str:
    """Light date normalization — standardize obvious formats."""
    # Convert common date separators: 01/15/2024 -> 01-15-2024
    text = re.sub(r"(\d{1,2})/(\d{1,2})/(\d{4})", r"\1-\2-\3", text)
    return text


def clean_document(extracted: ExtractedDocument) -> CleanedDocument:
    """Clean an extracted document.

    Removes:
    - Navigation/menu elements
    - Repeated headers/footers
    - Page numbers (standalone)
    - Excessive whitespace
    - Encoding artifacts

    Preserves:
    - Financial amounts
    - Eligibility rules
    - Dates, product names, conditions
    - Tables
    - Source references

    Args:
        extracted: The raw extracted document.

    Returns:
        CleanedDocument with cleaning log.
    """
    cleaned = CleanedDocument(
        source_id=extracted.source_id,
        tables=extracted.tables,  # Tables preserved as-is
    )

    for element in extracted.elements:
        # Skip navigation elements
        if element.element_type == ElementType.NAVIGATION:
            cleaned.removed_elements.append(element)
            cleaned.cleaning_log.append(f"Removed navigation element: {element.element_id}")
            continue

        # Skip footer/header boilerplate
        if element.element_type in (ElementType.FOOTER, ElementType.HEADER):
            if _is_footer_header(element.text):
                cleaned.removed_elements.append(element)
                cleaned.cleaning_log.append(f"Removed header/footer: {element.element_id}")
                continue

        # Check content for nav patterns
        if _is_navigation(element.text):
            cleaned.removed_elements.append(element)
            cleaned.cleaning_log.append(f"Removed navigation content: {element.element_id}")
            continue

        # Skip very short meaningless fragments
        if len(element.text.strip()) < 3 and element.element_type == ElementType.PARAGRAPH:
            cleaned.removed_elements.append(element)
            cleaned.cleaning_log.append(f"Removed short fragment: {element.element_id}")
            continue

        # Normalize the text
        clean_text = _normalize_whitespace(element.text)
        clean_text = _normalize_dates(clean_text)

        # Create cleaned element
        cleaned_element = element.model_copy(update={"text": clean_text})
        cleaned.elements.append(cleaned_element)

    logger.info(
        "Document cleaned",
        extra={"extra_data": {
            "source_id": extracted.source_id,
            "kept": len(cleaned.elements),
            "removed": len(cleaned.removed_elements),
        }},
    )

    return cleaned
