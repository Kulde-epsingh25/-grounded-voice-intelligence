"""
Q2 Knowledge Base — Confidence Gate & Abstention Engine.

Enforces zero-hallucination policy:
If confidence < threshold, the system abstains with:
"I don't have verified information about that."
No retrieval evidence -> no answer.
"""

from __future__ import annotations

import re
from typing import Optional

from app.core.config import get_config
from app.retrieval.models import RetrievalResult, RetrievalScore


class ConfidenceGate:
    """Evaluates retrieval confidence and enforces safe abstention."""

    DEFAULT_FALLBACK_ANSWER = "I don't have verified information about that."

    def __init__(self, threshold: Optional[float] = None):
        config = get_config()
        self.threshold = threshold if threshold is not None else config.retrieval.confidence_threshold

    def evaluate(
        self,
        query: str,
        candidates: list[RetrievalScore],
    ) -> tuple[float, bool, Optional[str]]:
        """Calculate confidence score and determine whether to answer or abstain.

        Returns:
            (confidence, should_answer, abstain_reason)
        """
        if not candidates:
            return 0.0, False, "no_matching_records"

        top_match = candidates[0]
        top_score = top_match.rerank_score or top_match.combined_score

        # If top score is very weak
        if top_score < 0.20:
            return round(top_score, 4), False, "weak_candidate_score"

        # Check keyword coverage on top match (filter stopwords/question words)
        clean_query = query.lower().strip()
        all_words = set(re.findall(r"[a-z0-9_]{2,}", clean_query))
        stopwords = {
            "what", "why", "how", "when", "where", "who", "which", "can",
            "could", "would", "should", "is", "are", "was", "were", "the",
            "a", "an", "and", "or", "for", "with", "to", "of", "in", "on",
            "at", "by", "from", "there", "this", "that", "these", "those",
            "about", "have", "has", "had", "been", "being", "does", "did",
        }
        query_words = all_words - stopwords
        if not query_words:
            query_words = all_words

        content_words = set(re.findall(r"[a-z0-9_]{2,}", top_match.chunk.content.lower()))
        title_words = set(re.findall(r"[a-z0-9_]{2,}", (top_match.chunk.title or "").lower()))
        section_words = set(re.findall(r"[a-z0-9_]{2,}", (top_match.chunk.section or "").lower()))

        matched_words = query_words.intersection(content_words.union(title_words).union(section_words))
        coverage = len(matched_words) / max(1, len(query_words))

        # Margin over second result (indicates clarity of evidence)
        second_score = candidates[1].rerank_score or candidates[1].combined_score if len(candidates) > 1 else 0.0
        margin = max(0.0, top_score - second_score)

        # Composite confidence metric:
        # 50% top score + 45% keyword coverage + 5% margin bonus
        confidence = (0.50 * top_score) + (0.45 * coverage) + (0.05 * min(1.0, margin * 2.0))
        confidence = min(1.0, max(0.0, round(confidence, 4)))

        if confidence < self.threshold:
            return confidence, False, f"confidence_below_threshold_{self.threshold}"

        return confidence, True, None
