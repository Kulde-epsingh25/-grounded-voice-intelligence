"""
Q2 Knowledge Base — Retrieval Package.

Exports core retrieval components:
- SectionChunker
- EmbeddingGenerator
- BM25Index
- KBVectorStore
- HybridRetriever
- Reranker
- ConfidenceGate
- CitationBuilder
- KBChunk, Citation, RetrievalScore, RetrievalResult
"""

from app.retrieval.chunking import SectionChunker
from app.retrieval.citations import CitationBuilder
from app.retrieval.confidence import ConfidenceGate
from app.retrieval.embeddings import EmbeddingGenerator
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.models import Citation, KBChunk, RetrievalResult, RetrievalScore
from app.retrieval.reranker import Reranker
from app.retrieval.sparse import BM25Index
from app.retrieval.store import KBVectorStore

__all__ = [
    "SectionChunker",
    "CitationBuilder",
    "ConfidenceGate",
    "EmbeddingGenerator",
    "HybridRetriever",
    "Citation",
    "KBChunk",
    "RetrievalResult",
    "RetrievalScore",
    "Reranker",
    "BM25Index",
    "KBVectorStore",
]
