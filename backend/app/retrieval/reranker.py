"""
Q2 Knowledge Base — Reranking Engine.

Reranks candidate search results by evaluating:
1. Meaningful sub-phrase and n-gram matches (e.g. "interest rate", "maximum loan amount")
2. Heading / Section title relevance with stopword filtering
3. Numeric and financial entity alignment (rates, amounts, years)
4. Meaningful query keyword coverage density
"""

from __future__ import annotations

import re
from typing import Optional

from app.retrieval.models import KBChunk, RetrievalScore
from app.retrieval.sparse import STOPWORDS


class Reranker:
    """Reranker that enhances dense + sparse candidates with fine-grained lexical signals."""

    def __init__(
        self,
        subphrase_weight: float = 0.25,
        title_match_weight: float = 0.25,
        numeric_match_weight: float = 0.20,
        coverage_weight: float = 0.30,
    ):
        self.subphrase_weight = subphrase_weight
        self.title_match_weight = title_match_weight
        self.numeric_match_weight = numeric_match_weight
        self.coverage_weight = coverage_weight

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalScore],
        top_k: int = 5,
    ) -> list[RetrievalScore]:
        """Rerank a list of candidates and return top_k results."""
        if not candidates:
            return []

        clean_query = query.lower().strip()
        all_query_words = re.findall(r"[a-z0-9_]+", clean_query)
        meaningful_words = [w for w in all_query_words if w not in STOPWORDS and len(w) > 1]
        if not meaningful_words:
            meaningful_words = all_query_words

        meaningful_set = set(meaningful_words)
        query_numbers = set(re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?%?\b", clean_query))

        # Generate 2-gram subphrases from meaningful words
        subphrases = []
        for i in range(len(all_query_words) - 1):
            w1, w2 = all_query_words[i], all_query_words[i + 1]
            if w1 not in STOPWORDS or w2 not in STOPWORDS:
                subphrases.append(f"{w1} {w2}")

        reranked: list[RetrievalScore] = []

        for candidate in candidates:
            chunk = candidate.chunk
            content_lower = chunk.content.lower()
            title_lower = (chunk.title or "").lower()
            section_lower = (chunk.section or "").lower()

            # 1. Sub-phrase match
            phrase_score = 0.0
            if clean_query in content_lower:
                phrase_score = 1.0
            elif subphrases:
                matched_phrases = sum(1 for sp in subphrases if sp in content_lower)
                phrase_score = matched_phrases / len(subphrases)

            # 2. Title / Section match (with stopword filtering)
            title_score = 0.0
            combined_header = f"{title_lower} {section_lower}"
            header_words = set(re.findall(r"[a-z0-9_]+", combined_header)) - STOPWORDS
            overlap = len(meaningful_set.intersection(header_words))
            title_score = overlap / max(1, len(meaningful_set))

            # 3. Numeric / entity match
            numeric_score = 0.0
            if query_numbers:
                content_normalized = content_lower.replace(",", "")
                matched_nums = sum(
                    1 for num in query_numbers
                    if num.replace(",", "").replace("%", "") in content_normalized
                )
                numeric_score = matched_nums / len(query_numbers)
            else:
                numeric_score = candidate.combined_score

            # 4. Keyword coverage density
            content_words = set(re.findall(r"[a-z0-9_]+", content_lower)) - STOPWORDS
            coverage_score = len(meaningful_set.intersection(content_words)) / max(1, len(meaningful_set))

            # Composite rerank boost
            boost = (
                self.subphrase_weight * phrase_score
                + self.title_match_weight * title_score
                + self.numeric_match_weight * numeric_score
                + self.coverage_weight * coverage_score
            )

            # Combine original candidate score (50%) with fine-grained boost (50%)
            final_score = 0.50 * candidate.combined_score + 0.50 * boost
            final_score = min(1.0, max(0.0, final_score))

            candidate.rerank_score = round(final_score, 4)
            reranked.append(candidate)

        reranked.sort(key=lambda x: x.rerank_score, reverse=True)
        return reranked[:top_k]
