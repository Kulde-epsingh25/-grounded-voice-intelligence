"""
Q2 Knowledge Base — Vector & Hybrid Document Store.

Stores KBChunks with dense embeddings and BM25 sparse index.
Supports metadata filtering (category, product, language, version).
Provides in-memory operation with optional Qdrant collection sync and JSON persistence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_config
from app.core.logging import get_logger
from app.retrieval.embeddings import EmbeddingGenerator
from app.retrieval.models import KBChunk
from app.retrieval.sparse import BM25Index

logger = get_logger(__name__)


class KBVectorStore:
    """Hybrid knowledge base store supporting dense vectors, BM25, and metadata filters."""

    def __init__(
        self,
        embedder: Optional[EmbeddingGenerator] = None,
        bm25: Optional[BM25Index] = None,
    ):
        self.embedder = embedder or EmbeddingGenerator()
        self.bm25 = bm25 or BM25Index()
        self.chunks: dict[str, KBChunk] = {}
        self.embeddings: dict[str, list[float]] = {}
        self._qdrant_client = None

        # Attempt optional Qdrant initialization
        config = get_config()
        try:
            from qdrant_client import QdrantClient
            if config.qdrant.url:
                self._qdrant_client = QdrantClient(url=config.qdrant.url, timeout=2.0)
        except Exception:
            # In-memory store continues seamlessly without external dependency
            self._qdrant_client = None

    def index_chunks(self, chunks: list[KBChunk]) -> int:
        """Index a batch of KBChunks into both dense and sparse representations."""
        if not chunks:
            return 0

        texts_to_embed: list[str] = []
        new_chunks: list[KBChunk] = []

        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk
            # Index into BM25
            search_text = f"{chunk.title} {chunk.section or ''} {chunk.content}"
            self.bm25.add_document(chunk.chunk_id, search_text)

            texts_to_embed.append(f"{chunk.title}\n{chunk.content}")
            new_chunks.append(chunk)

        # Batch embed texts
        embedded_vectors = self.embedder.embed_texts(texts_to_embed)
        for chunk, vector in zip(new_chunks, embedded_vectors):
            self.embeddings[chunk.chunk_id] = vector

        logger.info(
            "Indexed KB chunks",
            extra={"extra_data": {"count": len(chunks), "total_in_store": len(self.chunks)}},
        )
        return len(chunks)

    def search_dense(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[tuple[KBChunk, float]]:
        """Dense vector cosine similarity search with metadata filtering."""
        candidates = self._filter_chunks(filters)
        if not candidates or not query_vector:
            return []

        scored: list[tuple[KBChunk, float]] = []
        for chunk_id in candidates:
            vec = self.embeddings.get(chunk_id)
            if vec is None:
                continue
            sim = self.embedder.cosine_similarity(query_vector, vec)
            scored.append((self.chunks[chunk_id], sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def search_sparse(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[tuple[KBChunk, float]]:
        """Sparse lexical BM25 search with metadata filtering."""
        candidates = self._filter_chunks(filters)
        bm25_results = self.bm25.search(query, top_k=top_k * 2)

        results: list[tuple[KBChunk, float]] = []
        for chunk_id, score in bm25_results:
            if chunk_id in candidates and chunk_id in self.chunks:
                results.append((self.chunks[chunk_id], score))
                if len(results) >= top_k:
                    break
        return results

    def _filter_chunks(self, filters: Optional[dict[str, Any]]) -> set[str]:
        """Apply metadata filtering to get matching chunk IDs."""
        if not filters:
            return set(self.chunks.keys())

        matching_ids = set()
        for chunk_id, chunk in self.chunks.items():
            match = True
            for key, val in filters.items():
                if val is None or val == "":
                    continue
                chunk_val = getattr(chunk, key, None)
                if chunk_val is None and key in chunk.metadata:
                    chunk_val = chunk.metadata.get(key)

                if isinstance(val, (list, tuple, set)):
                    if chunk_val not in val:
                        match = False
                        break
                elif str(chunk_val).lower() != str(val).lower():
                    match = False
                    break

            if match:
                matching_ids.add(chunk_id)

        return matching_ids

    def get_chunk(self, chunk_id: str) -> Optional[KBChunk]:
        """Get chunk by ID."""
        return self.chunks.get(chunk_id)

    def count(self) -> int:
        """Total chunks in store."""
        return len(self.chunks)

    def clear(self) -> None:
        """Clear all stored chunks and indices."""
        self.chunks.clear()
        self.embeddings.clear()
        self.bm25 = BM25Index()

    def save_to_file(self, filepath: Path | str) -> None:
        """Persist indexed chunks and embeddings to JSON."""
        data = {
            "chunks": [c.model_dump(mode="json") for c in self.chunks.values()],
            "embeddings": self.embeddings,
        }
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def load_from_file(self, filepath: Path | str) -> int:
        """Load indexed chunks and embeddings from JSON."""
        path = Path(filepath)
        if not path.exists():
            return 0
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        chunks_data = data.get("chunks", [])
        loaded_chunks = [KBChunk.model_validate(c) for c in chunks_data]
        self.index_chunks(loaded_chunks)

        saved_embeddings = data.get("embeddings", {})
        for cid, vec in saved_embeddings.items():
            if cid in self.chunks:
                self.embeddings[cid] = vec

        return len(loaded_chunks)
