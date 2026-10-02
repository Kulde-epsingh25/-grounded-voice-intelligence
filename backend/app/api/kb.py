"""
Q2 Knowledge Base — FastAPI KB Router.

Exposes:
- POST /api/v1/kb/search (Standard retrieval interface)
- POST /kb/search (Vapi custom KB interface alias)
- POST /api/v1/kb/index (Reindexing endpoint)
- GET /api/v1/kb/stats (Store and indexing statistics)
- GET /api/v1/kb/chunks (List indexed chunks)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import get_config
from app.core.logging import get_logger
from app.kb.models import KBRecord
from app.retrieval import (
    CitationBuilder,
    HybridRetriever,
    KBChunk,
    KBVectorStore,
    RetrievalResult,
    SectionChunker,
)

logger = get_logger(__name__)

router = APIRouter()

# Global in-process store and retriever (shared across requests)
_store = KBVectorStore()
_chunker = SectionChunker()
_retriever = HybridRetriever(store=_store)


def get_retriever() -> HybridRetriever:
    return _retriever


def get_store() -> KBVectorStore:
    return _store


def get_chunker() -> SectionChunker:
    return _chunker


# =============================================================================
# Request / Response Schemas
# =============================================================================

class SearchRequest(BaseModel):
    """Retrieval search query."""
    query: Optional[str] = None
    messages: Optional[list[dict[str, Any]]] = None  # Vapi custom KB format support
    filters: Optional[dict[str, Any]] = None
    top_k: Optional[int] = None
    alpha: Optional[float] = None
    fusion_method: str = "rrf"


class SearchResponse(BaseModel):
    """Search response with confidence gating and citations."""
    query: str
    answer: str
    grounded: bool
    confidence: float
    citations: list[dict[str, Any]]
    results: list[dict[str, Any]]
    abstain_reason: Optional[str] = None
    processing_time_ms: float = 0.0


class IndexRequest(BaseModel):
    """Request to index records from file or payload."""
    records: Optional[list[KBRecord]] = None
    file_path: Optional[str] = None


class IndexResponse(BaseModel):
    status: str
    records_indexed: int
    chunks_created: int
    total_chunks: int


# =============================================================================
# Helper: auto-load processed KB records if store is empty
# =============================================================================

def ensure_kb_loaded() -> None:
    """If store is empty, attempt to load processed KB records from disk."""
    if _store.count() > 0:
        return

    processed_file = Path("data/processed/kb_records.json")
    localized_file = Path("data/processed/localized_kb_records.json")

    all_records: list[KBRecord] = []

    if processed_file.exists():
        try:
            with open(processed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            all_records.extend([KBRecord.model_validate(r) for r in data])
        except Exception as e:
            logger.warning("Could not load base KB records", extra={"extra_data": {"error": str(e)}})

    if localized_file.exists():
        try:
            with open(localized_file, "r", encoding="utf-8") as f:
                loc_data = json.load(f)
            all_records.extend([KBRecord.model_validate(r) for r in loc_data])
        except Exception as e:
            logger.warning("Could not load localized KB records", extra={"extra_data": {"error": str(e)}})

    if all_records:
        chunks = _chunker.chunk_records(all_records)
        _store.index_chunks(chunks)
        logger.info("Auto-loaded KB records into store", extra={"extra_data": {"records": len(all_records), "chunks": len(chunks)}})


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/search", response_model=SearchResponse)
async def search_kb(request: SearchRequest) -> SearchResponse:
    """Search knowledge base with hybrid retrieval, confidence gating, and citations.

    Compatible with both standard queries and Vapi custom KB payload format.
    """
    ensure_kb_loaded()

    # Extract query text
    query_text = request.query
    if not query_text and request.messages:
        # Extract last user message for Vapi custom KB
        for msg in reversed(request.messages):
            if msg.get("role") in ("user", "human"):
                query_text = msg.get("content", "")
                break
        if not query_text and request.messages:
            query_text = request.messages[-1].get("content", "")

    if not query_text:
        return SearchResponse(
            query="",
            answer="I don't have verified information about that.",
            grounded=False,
            confidence=0.0,
            citations=[],
            results=[],
            abstain_reason="empty_query",
            processing_time_ms=0.0,
        )

    result: RetrievalResult = _retriever.search(
        query=query_text,
        filters=request.filters,
        top_k=request.top_k,
        alpha=request.alpha,
        fusion_method=request.fusion_method,
    )

    formatted_citations = [c.model_dump(mode="json") for c in result.citations]
    formatted_results = [
        {
            "chunk_id": m.chunk.chunk_id,
            "title": m.chunk.title,
            "section": m.chunk.section,
            "content": m.chunk.content,
            "source_name": m.chunk.source_name,
            "source_id": m.chunk.source_id,
            "score": m.rerank_score or m.combined_score,
            "citation": m.citation.model_dump(mode="json") if m.citation else None,
        }
        for m in result.matches
    ]

    return SearchResponse(
        query=result.query,
        answer=result.answer,
        grounded=result.grounded,
        confidence=result.confidence,
        citations=formatted_citations,
        results=formatted_results,
        abstain_reason=result.abstain_reason,
        processing_time_ms=result.processing_time_ms,
    )


@router.post("/index", response_model=IndexResponse)
async def index_records(request: IndexRequest) -> IndexResponse:
    """Index records into vector store."""
    records_to_process: list[KBRecord] = []

    if request.records:
        records_to_process = request.records
    elif request.file_path:
        path = Path(request.file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File {path} not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        records_to_process = [KBRecord.model_validate(r) for r in data]
    else:
        # Default to processed records
        path = Path("data/processed/kb_records.json")
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            records_to_process = [KBRecord.model_validate(r) for r in data]

    chunks = _chunker.chunk_records(records_to_process)
    _store.index_chunks(chunks)

    return IndexResponse(
        status="success",
        records_indexed=len(records_to_process),
        chunks_created=len(chunks),
        total_chunks=_store.count(),
    )


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Retrieve knowledge base store statistics."""
    ensure_kb_loaded()
    categories = set()
    sources = set()
    products = set()

    for chunk in _store.chunks.values():
        if chunk.category:
            categories.add(chunk.category)
        if chunk.source_id:
            sources.add(chunk.source_id)
        if chunk.product:
            products.add(chunk.product)

    return {
        "total_chunks": _store.count(),
        "total_sources": len(sources),
        "categories": list(categories),
        "products": list(products),
        "confidence_threshold": get_config().retrieval.confidence_threshold,
    }


@router.get("/chunks")
async def list_chunks(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List chunks in store with pagination."""
    ensure_kb_loaded()
    all_chunks = list(_store.chunks.values())
    paginated = all_chunks[offset : offset + limit]
    return {
        "total": len(all_chunks),
        "limit": limit,
        "offset": offset,
        "chunks": [c.model_dump(mode="json") for c in paginated],
    }
