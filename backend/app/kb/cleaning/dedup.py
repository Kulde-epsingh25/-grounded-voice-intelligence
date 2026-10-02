"""
Q2 Knowledge Base — Deduplication.

Detects exact and near-duplicate content.
Does NOT automatically delete duplicates — flags them for canonicalization.
"""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher

from app.core.logging import get_logger
from app.kb.models import DuplicateRecord, DuplicateType

logger = get_logger(__name__)

# Default near-duplicate threshold
DEFAULT_SIMILARITY_THRESHOLD = 0.90


def _normalize_for_hash(text: str) -> str:
    """Normalize text for consistent hashing."""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized content."""
    normalized = _normalize_for_hash(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def detect_exact_duplicate(
    content_a: str,
    content_b: str,
    record_id_a: str,
    record_id_b: str,
) -> DuplicateRecord | None:
    """Detect if two content strings are exact duplicates after normalization.

    Returns:
        DuplicateRecord if duplicate, None otherwise.
    """
    hash_a = compute_content_hash(content_a)
    hash_b = compute_content_hash(content_b)

    if hash_a == hash_b:
        return DuplicateRecord(
            canonical_record_id=record_id_a,
            duplicate_record_id=record_id_b,
            duplicate_type=DuplicateType.EXACT,
            similarity=1.0,
        )
    return None


def compute_similarity(text_a: str, text_b: str) -> float:
    """Compute normalized token similarity between two texts."""
    norm_a = _normalize_for_hash(text_a)
    norm_b = _normalize_for_hash(text_b)

    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0

    return SequenceMatcher(None, norm_a, norm_b).ratio()


def detect_near_duplicate(
    content_a: str,
    content_b: str,
    record_id_a: str,
    record_id_b: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> DuplicateRecord | None:
    """Detect if two content strings are near-duplicates.

    Args:
        content_a: First content string.
        content_b: Second content string.
        record_id_a: ID of first record (treated as canonical).
        record_id_b: ID of second record (treated as duplicate).
        threshold: Similarity threshold (default 0.90).

    Returns:
        DuplicateRecord if near-duplicate, None otherwise.
    """
    similarity = compute_similarity(content_a, content_b)

    if similarity >= threshold:
        return DuplicateRecord(
            canonical_record_id=record_id_a,
            duplicate_record_id=record_id_b,
            duplicate_type=DuplicateType.NEAR if similarity < 1.0 else DuplicateType.EXACT,
            similarity=round(similarity, 4),
            threshold=threshold,
        )
    return None


class DeduplicationIndex:
    """Index for tracking and detecting duplicates across the KB."""

    def __init__(self, similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> None:
        self._hash_index: dict[str, str] = {}  # content_hash -> record_id
        self._content_cache: dict[str, str] = {}  # record_id -> normalized content
        self._duplicates: list[DuplicateRecord] = []
        self._threshold = similarity_threshold

    def check_and_add(self, record_id: str, content: str) -> list[DuplicateRecord]:
        """Check content against existing index and add it.

        Returns:
            List of DuplicateRecords found (may be empty).
        """
        found = []
        content_hash = compute_content_hash(content)

        # Check exact duplicate
        if content_hash in self._hash_index:
            existing_id = self._hash_index[content_hash]
            dup = DuplicateRecord(
                canonical_record_id=existing_id,
                duplicate_record_id=record_id,
                duplicate_type=DuplicateType.EXACT,
                similarity=1.0,
            )
            found.append(dup)
            self._duplicates.append(dup)
            logger.info(
                "Exact duplicate detected",
                extra={"extra_data": {
                    "canonical": existing_id,
                    "duplicate": record_id,
                }},
            )

        # Check near duplicates against cached content
        normalized = _normalize_for_hash(content)
        for existing_id, existing_content in self._content_cache.items():
            if existing_id == record_id:
                continue
            # Only check near-dup if not already exact
            if content_hash == compute_content_hash(existing_content):
                continue

            sim = SequenceMatcher(None, normalized, existing_content).ratio()
            if sim >= self._threshold:
                dup = DuplicateRecord(
                    canonical_record_id=existing_id,
                    duplicate_record_id=record_id,
                    duplicate_type=DuplicateType.NEAR,
                    similarity=round(sim, 4),
                    threshold=self._threshold,
                )
                found.append(dup)
                self._duplicates.append(dup)
                logger.info(
                    "Near duplicate detected",
                    extra={"extra_data": {
                        "canonical": existing_id,
                        "duplicate": record_id,
                        "similarity": round(sim, 4),
                    }},
                )

        # Index this content
        self._hash_index[content_hash] = record_id
        self._content_cache[record_id] = normalized

        return found

    @property
    def all_duplicates(self) -> list[DuplicateRecord]:
        return list(self._duplicates)
