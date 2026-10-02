"""
Q2 Knowledge Base — PII Detection and Protection.

Uses deterministic regex patterns for email, phone, and identifiers.
Presidio integration is available if installed.
Raw PII is NEVER written to logs.
"""

from __future__ import annotations

import re

from app.core.logging import get_logger
from app.kb.models import PIIEntity, PIIEntityType, PIIAction, PIIResult

logger = get_logger(__name__)

# ============================================================================
# Regex patterns for deterministic PII detection
# ============================================================================

_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

_PHONE_PATTERNS = [
    re.compile(r"\+?\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}"),  # International
    re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),  # US format
    re.compile(r"\b\d{10,12}\b"),  # Plain digits
]

_ACCOUNT_ID_PATTERNS = [
    re.compile(r"\b(?:account|acct|acc)[#:\s-]*\d{4,}\b", re.IGNORECASE),
    re.compile(r"\b(?:policy|pol)[#:\s-]*\d{4,}\b", re.IGNORECASE),
    re.compile(r"\b(?:customer|cust|cid)[#:\s-]*\d{4,}\b", re.IGNORECASE),
]

# Simple name detection: "Mr./Mrs./Dr. Firstname Lastname" pattern
_NAME_PATTERN = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b"
)


def detect_pii(text: str) -> list[PIIEntity]:
    """Detect PII entities in text using regex patterns.

    Args:
        text: Content to scan.

    Returns:
        List of detected PII entities (text field populated for masking only,
        never logged).
    """
    entities: list[PIIEntity] = []

    # Emails
    for match in _EMAIL_PATTERN.finditer(text):
        entities.append(PIIEntity(
            entity_type=PIIEntityType.EMAIL,
            start=match.start(),
            end=match.end(),
            text=match.group(),
            confidence=0.99,
            action=PIIAction.MASK,
        ))

    # Phones
    for pattern in _PHONE_PATTERNS:
        for match in pattern.finditer(text):
            # Avoid matching years or small numbers
            matched = match.group().replace(" ", "").replace("-", "").replace(".", "")
            if len(matched) >= 7:
                entities.append(PIIEntity(
                    entity_type=PIIEntityType.PHONE,
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    confidence=0.85,
                    action=PIIAction.MASK,
                ))

    # Account/Policy/Customer IDs
    for pattern in _ACCOUNT_ID_PATTERNS:
        for match in pattern.finditer(text):
            entities.append(PIIEntity(
                entity_type=PIIEntityType.ACCOUNT_ID,
                start=match.start(),
                end=match.end(),
                text=match.group(),
                confidence=0.90,
                action=PIIAction.MASK,
            ))

    # Names (simple pattern — not comprehensive)
    for match in _NAME_PATTERN.finditer(text):
        entities.append(PIIEntity(
            entity_type=PIIEntityType.PERSON_NAME,
            start=match.start(),
            end=match.end(),
            text=match.group(),
            confidence=0.70,
            action=PIIAction.MASK,
        ))

    # Remove overlapping entities (keep highest confidence)
    entities = _resolve_overlaps(entities)

    return entities


def _resolve_overlaps(entities: list[PIIEntity]) -> list[PIIEntity]:
    """Remove overlapping PII entities, keeping highest confidence."""
    if not entities:
        return entities

    # Sort by start position, then by confidence descending
    entities.sort(key=lambda e: (e.start, -e.confidence))

    resolved: list[PIIEntity] = []
    last_end = -1

    for entity in entities:
        if entity.start >= last_end:
            resolved.append(entity)
            last_end = entity.end

    return resolved


def mask_pii(text: str, entities: list[PIIEntity]) -> str:
    """Replace PII entities with type-based masks.

    Args:
        text: Original text.
        entities: Detected PII entities.

    Returns:
        Sanitized text with PII replaced by masks.
    """
    if not entities:
        return text

    # Sort by start position in reverse to replace from end
    sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
    result = text

    for entity in sorted_entities:
        mask = f"[{entity.entity_type.value.upper()}]"
        result = result[:entity.start] + mask + result[entity.end:]

    return result


def process_pii(source_id: str, content: str) -> PIIResult:
    """Full PII processing: detect and mask.

    Args:
        source_id: Source identifier.
        content: Text to process.

    Returns:
        PIIResult with sanitized content and entity details.
        Raw PII text is stored internally but never logged.
    """
    entities = detect_pii(content)
    sanitized = mask_pii(content, entities)

    result = PIIResult(
        source_id=source_id,
        original_content=content,
        sanitized_content=sanitized,
        entities_found=entities,
        total_entities=len(entities),
    )

    # Log count only — never log raw PII
    if entities:
        logger.info(
            "PII detected and masked",
            extra={"extra_data": {
                "source_id": source_id,
                "entities_count": len(entities),
                "types": list(set(e.entity_type.value for e in entities)),
            }},
        )

    return result
