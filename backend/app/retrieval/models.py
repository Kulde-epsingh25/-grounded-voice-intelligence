"""
Q2 Knowledge Base — Retrieval Data Models.

Pydantic models for chunking, vector/sparse search, hybrid ranking,
confidence gating, and citations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class KBChunk(BaseModel):
    """A searchable chunk of knowledge derived from a KBRecord."""
    chunk_id: str = Field(default_factory=lambda: f"chk_{uuid4().hex[:8]}")
    record_id: str
    source_id: str
    source_name: str = ""
    source_page: Optional[int] = None
    title: str = ""
    section: Optional[str] = None
    content: str
    category: str = ""
    subcategory: str = ""
    product: str = ""
    version: str = "1.0"
    effective_from: Optional[str] = None
    language: str = "en"
    pii: bool = False
    content_hash: str = ""
    chunk_index: int = 0
    total_chunks: int = 1
    char_count: int = 0
    token_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    """Source citation for grounded retrieval."""
    citation_id: str = Field(default_factory=lambda: f"cit_{uuid4().hex[:8]}")
    source_id: str
    source_name: str
    record_id: str
    chunk_id: str
    section: Optional[str] = None
    source_page: Optional[int] = None
    version: str = "1.0"
    content_hash: str = ""
    confidence: float = 1.0
    snippet: str = ""


class RetrievalScore(BaseModel):
    """Scored search candidate combining dense and sparse metrics."""
    chunk: KBChunk
    dense_score: float = 0.0
    sparse_score: float = 0.0
    combined_score: float = 0.0
    rerank_score: float = 0.0
    citation: Optional[Citation] = None


class RetrievalResult(BaseModel):
    """Final retrieval response including confidence gating and citations."""
    query: str
    matches: list[RetrievalScore] = Field(default_factory=list)
    confidence: float = 0.0
    grounded: bool = False
    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    abstain_reason: Optional[str] = None
    processing_time_ms: float = 0.0
    filters_applied: dict[str, Any] = Field(default_factory=dict)
