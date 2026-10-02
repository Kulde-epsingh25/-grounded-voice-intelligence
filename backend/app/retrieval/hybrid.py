"""
Q2 Knowledge Base — Hybrid Retrieval Engine.

Combines:
1. Dense vector cosine search (semantic concepts)
2. Sparse BM25 search (exact keywords, terms, numbers)
3. Rank / Score Fusion (RRF or weighted combination)
4. Lexical Reranker
5. Confidence Gate (abstains if confidence < threshold)
6. Source Lineage & Citation Builder
"""

from __future__ import annotations

import time
from typing import Any, Optional

from app.core.config import get_config
from app.core.logging import get_logger
from app.retrieval.citations import CitationBuilder
from app.retrieval.confidence import ConfidenceGate
from app.retrieval.models import KBChunk, RetrievalResult, RetrievalScore
from app.retrieval.reranker import Reranker
from app.retrieval.store import KBVectorStore

logger = get_logger(__name__)


class HybridRetriever:
    """Hybrid search orchestrator fusing dense vector and sparse lexical results."""

    def __init__(
        self,
        store: Optional[KBVectorStore] = None,
        reranker: Optional[Reranker] = None,
        confidence_gate: Optional[ConfidenceGate] = None,
        alpha: float = 0.50,
        rrf_k: int = 60,
    ):
        self.store = store or KBVectorStore()
        self.reranker = reranker or Reranker()
        self.confidence_gate = confidence_gate or ConfidenceGate()
        self.alpha = max(0.0, min(1.0, alpha))
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        filters: Optional[dict[str, Any]] = None,
        top_k: Optional[int] = None,
        alpha: Optional[float] = None,
        fusion_method: str = "rrf",
    ) -> RetrievalResult:
        """Execute hybrid search on the query with metadata filtering and confidence gating."""
        t0 = time.perf_counter()
        config = get_config()
        effective_top_k = top_k or config.retrieval.top_k or 5
        effective_alpha = self.alpha if alpha is None else max(0.0, min(1.0, alpha))

        clean_query = query.strip()
        if not clean_query:
            return RetrievalResult(
                query=query,
                confidence=0.0,
                grounded=False,
                answer=ConfidenceGate.DEFAULT_FALLBACK_ANSWER,
                abstain_reason="empty_query",
                processing_time_ms=0.0,
            )

        # 1. Dense retrieval
        query_vector = self.store.embedder.embed_query(clean_query)
        dense_candidates = self.store.search_dense(
            query_vector=query_vector,
            top_k=effective_top_k * 3,
            filters=filters,
        )

        # 2. Sparse retrieval
        sparse_candidates = self.store.search_sparse(
            query=clean_query,
            top_k=effective_top_k * 3,
            filters=filters,
        )

        # 3. Fusion
        if fusion_method == "rrf":
            candidate_scores = self._fuse_rrf(dense_candidates, sparse_candidates)
        else:
            candidate_scores = self._fuse_weighted(
                dense_candidates, sparse_candidates, alpha=effective_alpha
            )

        # 4. Rerank
        reranked = self.reranker.rerank(
            query=clean_query,
            candidates=candidate_scores,
            top_k=effective_top_k,
        )

        # 5. Build citations for top candidates
        citations = []
        for cand in reranked:
            cit = CitationBuilder.build_citation(cand.chunk, confidence=cand.rerank_score)
            cand.citation = cit
            citations.append(cit)

        # 6. Confidence evaluation
        confidence, should_answer, abstain_reason = self.confidence_gate.evaluate(
            query=clean_query,
            candidates=reranked,
        )

        t1 = time.perf_counter()
        elapsed_ms = round((t1 - t0) * 1000, 2)

        # 7. Formulate grounded response
        if should_answer and reranked:
            primary_chunk = reranked[0].chunk
            raw_answer = primary_chunk.content.strip()
            answer = CitationBuilder.format_grounded_answer(
                raw_answer, citations[:2], include_inline=True
            )
            grounded = True
        else:
            answer = ConfidenceGate.DEFAULT_FALLBACK_ANSWER
            grounded = False

        logger.info(
            "Hybrid search completed",
            extra={
                "extra_data": {
                    "query": clean_query,
                    "confidence": confidence,
                    "grounded": grounded,
                    "results_count": len(reranked),
                    "elapsed_ms": elapsed_ms,
                }
            },
        )

        return RetrievalResult(
            query=clean_query,
            matches=reranked,
            confidence=confidence,
            grounded=grounded,
            answer=answer,
            citations=citations if grounded else [],
            abstain_reason=abstain_reason,
            processing_time_ms=elapsed_ms,
            filters_applied=filters or {},
        )

    def _fuse_rrf(
        self,
        dense: list[tuple[KBChunk, float]],
        sparse: list[tuple[KBChunk, float]],
    ) -> list[RetrievalScore]:
        """Reciprocal Rank Fusion."""
        chunk_map: dict[str, KBChunk] = {}
        dense_ranks: dict[str, int] = {}
        dense_scores: dict[str, float] = {}
        for rank, (chunk, score) in enumerate(dense, start=1):
            chunk_map[chunk.chunk_id] = chunk
            dense_ranks[chunk.chunk_id] = rank
            dense_scores[chunk.chunk_id] = score

        sparse_ranks: dict[str, int] = {}
        sparse_scores: dict[str, float] = {}
        for rank, (chunk, score) in enumerate(sparse, start=1):
            chunk_map[chunk.chunk_id] = chunk
            sparse_ranks[chunk.chunk_id] = rank
            sparse_scores[chunk.chunk_id] = score

        all_ids = set(chunk_map.keys())
        results: list[RetrievalScore] = []

        for cid in all_ids:
            chunk = chunk_map[cid]
            d_rank = dense_ranks.get(cid)
            s_rank = sparse_ranks.get(cid)

            rrf_dense = 1.0 / (self.rrf_k + d_rank) if d_rank is not None else 0.0
            rrf_sparse = 1.0 / (self.rrf_k + s_rank) if s_rank is not None else 0.0
            combined = rrf_dense + rrf_sparse

            # Normalize combined score
            norm_combined = min(1.0, combined * (self.rrf_k / 2.0))

            results.append(
                RetrievalScore(
                    chunk=chunk,
                    dense_score=round(dense_scores.get(cid, 0.0), 4),
                    sparse_score=round(sparse_scores.get(cid, 0.0), 4),
                    combined_score=round(norm_combined, 4),
                )
            )

        results.sort(key=lambda x: x.combined_score, reverse=True)
        return results

    def _fuse_weighted(
        self,
        dense: list[tuple[KBChunk, float]],
        sparse: list[tuple[KBChunk, float]],
        alpha: float,
    ) -> list[RetrievalScore]:
        """Linear weighted combination."""
        chunk_map: dict[str, KBChunk] = {}
        dense_scores: dict[str, float] = {c.chunk_id: s for c, s in dense}
        sparse_scores: dict[str, float] = {c.chunk_id: s for c, s in sparse}

        for c, _ in dense:
            chunk_map[c.chunk_id] = c
        for c, _ in sparse:
            chunk_map[c.chunk_id] = c

        results: list[RetrievalScore] = []
        for cid, chunk in chunk_map.items():
            d_score = max(0.0, dense_scores.get(cid, 0.0))
            s_score = max(0.0, sparse_scores.get(cid, 0.0))
            combined = alpha * d_score + (1.0 - alpha) * s_score

            results.append(
                RetrievalScore(
                    chunk=chunk,
                    dense_score=round(d_score, 4),
                    sparse_score=round(s_score, 4),
                    combined_score=round(combined, 4),
                )
            )

        results.sort(key=lambda x: x.combined_score, reverse=True)
        return results
