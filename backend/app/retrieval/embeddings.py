"""
Q2 Knowledge Base — Dense Vector Embeddings.

Provides dense vector embeddings:
1. OpenAI text-embedding-3-small (when OPENAI_API_KEY is configured)
2. Local deterministic fallback (hash-projected L2-normalized vector)
   for offline testing, development, and guaranteed zero-downtime execution.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Optional

from app.core.config import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingGenerator:
    """Generates normalized dense vector embeddings for texts and queries."""

    DEFAULT_DIMENSION = 384

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimension: int = DEFAULT_DIMENSION,
    ):
        config = get_config()
        self.api_key = api_key if api_key is not None else config.openai.api_key
        self.model = model or config.openai.embedding_model or "text-embedding-3-small"
        self.dimension = dimension
        self._openai_client = None

        if self.api_key:
            try:
                import openai
                self._openai_client = openai.OpenAI(api_key=self.api_key)
                logger.info("OpenAI embeddings client initialized", extra={"extra_data": {"model": self.model}})
            except Exception as e:
                logger.warning(
                    "Could not initialize OpenAI client, using deterministic fallback",
                    extra={"extra_data": {"error": str(e)}},
                )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate normalized vector embeddings for a list of texts."""
        if not texts:
            return []

        if self._openai_client:
            try:
                # Call OpenAI API
                response = self._openai_client.embeddings.create(
                    input=texts,
                    model=self.model,
                )
                embeddings = [data.embedding for data in response.data]
                return embeddings
            except Exception as e:
                logger.warning(
                    "OpenAI embeddings call failed, falling back to local deterministic embeddings",
                    extra={"extra_data": {"error": str(e), "batch_size": len(texts)}},
                )

        # Local deterministic embedding
        return [self._embed_deterministic(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        """Generate normalized vector embedding for a single search query."""
        results = self.embed_texts([query])
        return results[0] if results else [0.0] * self.dimension

    def _embed_deterministic(self, text: str) -> list[float]:
        """Compute deterministic feature-hashed dense vector with L2 normalization.

        Captures word tokens, bi-grams, and char n-grams into a fixed-dimension vector.
        Semantically similar texts produce high cosine similarity.
        """
        clean_text = text.lower().strip()
        tokens = re.findall(r"[a-z0-9_]+", clean_text)
        if not tokens:
            return [0.0] * self.dimension

        vector = [0.0] * self.dimension

        # 1. Unigrams
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            vector[idx] += 3.0

        # 2. Bigrams
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]}_{tokens[i+1]}"
            h = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            vector[idx] += 0.5

        # 3. Numeric tokens bonus (crucial for loan amounts, interest rates, terms)
        for num in re.findall(r"\b\d+(?:\.\d+)?\b", clean_text):
            h = int(hashlib.md5(f"num_{num}".encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            vector[idx] += 2.0

        # 4. L2 Normalize
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 1e-9:
            vector = [x / norm for x in vector]
        else:
            vector[0] = 1.0

        return vector

    @staticmethod
    def cosine_similarity(v1: list[float], v2: list[float]) -> float:
        """Calculate cosine similarity between two normalized vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        return max(-1.0, min(1.0, dot))
