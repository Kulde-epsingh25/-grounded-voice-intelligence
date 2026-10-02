"""
Q2 Knowledge Base — Sparse Lexical BM25 Retrieval.

Implements Okapi BM25 ranking algorithm with inverted index.
Ideal for exact terminology, product names, numbers, and keyword matching.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Optional

# Common stopwords to filter for sparse lexical search
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "could", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into",
    "is", "it", "its", "itself", "just", "me", "more", "most", "my",
    "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves",
}


class BM25Index:
    """Okapi BM25 sparse lexical index."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_lengths: dict[str, int] = {}
        self.doc_term_freqs: dict[str, Counter[str]] = {}
        self.inverted_index: dict[str, set[str]] = defaultdict(set)
        self.avg_doc_length: float = 0.0
        self.total_docs: int = 0

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Tokenize text into lowercase terms, stripping stopwords."""
        words = re.findall(r"[a-z0-9_]+", text.lower())
        return [w for w in words if w not in STOPWORDS]

    def add_document(self, doc_id: str, text: str) -> None:
        """Index a single document."""
        tokens = self.tokenize(text)
        length = len(tokens)
        self.doc_lengths[doc_id] = length
        term_counts = Counter(tokens)
        self.doc_term_freqs[doc_id] = term_counts

        for term in term_counts:
            self.inverted_index[term].add(doc_id)

        self.total_docs = len(self.doc_lengths)
        self.avg_doc_length = sum(self.doc_lengths.values()) / max(1, self.total_docs)

    def remove_document(self, doc_id: str) -> None:
        """Remove a document from index."""
        if doc_id not in self.doc_lengths:
            return
        del self.doc_lengths[doc_id]
        if doc_id in self.doc_term_freqs:
            for term in self.doc_term_freqs[doc_id]:
                self.inverted_index[term].discard(doc_id)
            del self.doc_term_freqs[doc_id]

        self.total_docs = len(self.doc_lengths)
        self.avg_doc_length = (
            sum(self.doc_lengths.values()) / max(1, self.total_docs)
            if self.total_docs > 0
            else 0.0
        )

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Score all matching documents for a query using BM25."""
        query_terms = self.tokenize(query)
        if not query_terms or self.total_docs == 0:
            return []

        # Find candidate documents containing at least one query term
        candidates: set[str] = set()
        for term in query_terms:
            candidates.update(self.inverted_index.get(term, set()))

        if not candidates:
            return []

        scores: dict[str, float] = defaultdict(float)

        for term in query_terms:
            doc_set = self.inverted_index.get(term, set())
            doc_freq = len(doc_set)
            if doc_freq == 0:
                continue

            # Okapi BM25 IDF with smoothing
            idf = math.log((self.total_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
            if idf <= 0:
                idf = 0.01

            for doc_id in candidates:
                freq = self.doc_term_freqs[doc_id].get(term, 0)
                if freq == 0:
                    continue

                doc_len = self.doc_lengths.get(doc_id, self.avg_doc_length)
                denominator = freq + self.k1 * (
                    1.0 - self.b + self.b * (doc_len / max(1e-6, self.avg_doc_length))
                )
                scores[doc_id] += idf * (freq * (self.k1 + 1.0)) / max(1e-6, denominator)

        if not scores:
            return []

        # Normalize scores to [0.0, 1.0] range
        max_score = max(scores.values())
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        if max_score > 0:
            return [(doc_id, score / max_score) for doc_id, score in ranked]
        return [(doc_id, 0.0) for doc_id, _ in ranked]
