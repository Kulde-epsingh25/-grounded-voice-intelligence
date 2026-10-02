"""
Q2 Knowledge Base — Comprehensive Retrieval & Evaluation Tests.

Tests:
1. Section-aware chunking (headings, tables, paragraphs, lineage)
2. Dense vector embeddings (dimensions, normalization, cosine similarity)
3. Sparse BM25 retrieval (inverted index, tokenization, stop words)
4. Hybrid retrieval & fusion (RRF and weighted combination)
5. Reranker (subphrase boost, title match, numeric alignment)
6. Confidence gate (threshold gating, safe zero-hallucination abstention)
7. Source citations (lineage, content hash, formatting)
8. FastAPI KB endpoints (standard search, Vapi custom KB format, stats)
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_config
from app.kb.models import KBRecord
from app.main import app
from app.retrieval import (
    Citation,
    CitationBuilder,
    ConfidenceGate,
    EmbeddingGenerator,
    HybridRetriever,
    KBChunk,
    KBVectorStore,
    Reranker,
    RetrievalResult,
    RetrievalScore,
    SectionChunker,
)
from app.retrieval.sparse import BM25Index


# =============================================================================
# 1. Chunking Tests
# =============================================================================

class TestChunking:
    def test_short_record_single_chunk(self):
        chunker = SectionChunker(chunk_size=512)
        rec = KBRecord(
            title="Short Doc",
            content="This is a brief qualification rule for loan eligibility.",
            source_id="src_1",
            source_name="rule.txt",
            version="1.0",
        )
        rec.compute_hash()
        chunks = chunker.chunk_record(rec)
        assert len(chunks) == 1
        assert chunks[0].record_id == rec.record_id
        assert chunks[0].source_id == rec.source_id
        assert chunks[0].content_hash == rec.content_hash
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks == 1

    def test_section_splitting(self):
        chunker = SectionChunker(chunk_size=150, chunk_overlap=30)
        long_content = (
            "# Section A\n"
            "This is the first detailed section describing loan terms and conditions in depth.\n\n"
            "# Section B\n"
            "This is the second detailed section describing interest rates, penalties, and grace periods."
        )
        rec = KBRecord(title="Long Doc", content=long_content, source_id="src_2")
        chunks = chunker.chunk_record(rec)
        assert len(chunks) >= 2
        sections = [c.section for c in chunks if c.section]
        assert any("Section A" in s for s in sections)
        assert any("Section B" in s for s in sections)

    def test_table_preservation(self):
        chunker = SectionChunker(chunk_size=300)
        table_content = (
            "Product | Min Revenue | Max Amount\n"
            "----------------------------------\n"
            "Starter | 500,000 | 2,000,000\n"
            "Growth | 1,000,000 | 5,000,000\n"
            "Premium | 2,500,000 | 15,000,000"
        )
        rec = KBRecord(title="Product Table", content=table_content, source_id="src_3")
        chunks = chunker.chunk_record(rec)
        assert len(chunks) == 1
        # Entire table must remain intact
        assert "Starter" in chunks[0].content
        assert "Premium" in chunks[0].content


# =============================================================================
# 2. Embeddings Tests
# =============================================================================

class TestEmbeddings:
    def test_vector_dimensions_and_normalization(self):
        embedder = EmbeddingGenerator(dimension=384)
        vec = embedder.embed_query("minimum monthly revenue requirement")
        assert len(vec) == 384
        norm = sum(x * x for x in vec)
        assert abs(norm - 1.0) < 1e-4

    def test_cosine_similarity_semantic_relevance(self):
        embedder = EmbeddingGenerator(dimension=384)
        v1 = embedder.embed_query("Starter business loan minimum revenue")
        v2 = embedder.embed_query("Minimum monthly revenue required for Starter loan")
        v3 = embedder.embed_query("Supermarket fresh fruit organic apples and bananas")

        sim_related = embedder.cosine_similarity(v1, v2)
        sim_unrelated = embedder.cosine_similarity(v1, v3)

        assert sim_related > 0.60
        assert sim_unrelated < 0.35

    def test_empty_query_embedding(self):
        embedder = EmbeddingGenerator(dimension=384)
        vec = embedder.embed_query("")
        assert len(vec) == 384


# =============================================================================
# 3. Sparse BM25 Tests
# =============================================================================

class TestSparseBM25:
    def test_bm25_exact_match(self):
        index = BM25Index()
        index.add_document("doc1", "The Starter loan requires $500,000 monthly revenue.")
        index.add_document("doc2", "The Enterprise tier is tailored for large corporate entities.")
        index.add_document("doc3", "Customer service is open 24/7 on weekends.")

        results = index.search("Starter revenue", top_k=3)
        assert len(results) > 0
        top_doc_id, top_score = results[0]
        assert top_doc_id == "doc1"
        assert top_score > 0.0

    def test_bm25_empty_query_and_stopword_handling(self):
        index = BM25Index()
        index.add_document("doc1", "Policy terms and conditions.")
        assert index.search("") == []
        assert index.search("   ") == []

    def test_bm25_document_removal(self):
        index = BM25Index()
        index.add_document("doc1", "Special promotional interest rate.")
        assert len(index.search("promotional")) == 1
        index.remove_document("doc1")
        assert len(index.search("promotional")) == 0


# =============================================================================
# 4. Vector Store & Filtering Tests
# =============================================================================

class TestVectorStore:
    def test_indexing_and_metadata_filter(self):
        store = KBVectorStore()
        c1 = KBChunk(
            record_id="r1",
            source_id="s1",
            title="Starter Loan",
            content="Starter loan terms and maximum $2,000,000 amount.",
            product="Starter",
            category="loans",
        )
        c2 = KBChunk(
            record_id="r2",
            source_id="s2",
            title="Enterprise Loan",
            content="Enterprise loan up to $50,000,000.",
            product="Enterprise",
            category="loans",
        )
        store.index_chunks([c1, c2])
        assert store.count() == 2

        # Search with product filter
        filtered_results = store.search_sparse("loan", filters={"product": "Starter"})
        assert len(filtered_results) == 1
        assert filtered_results[0][0].product == "Starter"


# =============================================================================
# 5. Hybrid Retrieval & Reranker Tests
# =============================================================================

class TestHybridRetrieval:
    @pytest.fixture
    def setup_retriever(self):
        store = KBVectorStore()
        chunks = [
            KBChunk(
                record_id="r1",
                source_id="src_policy",
                source_name="policy_v1.txt",
                title="Processing Time",
                content="Standard processing takes 5-7 business days for all loan applications.",
                category="policy",
                version="1.0",
                content_hash="abc12345",
            ),
            KBChunk(
                record_id="r2",
                source_id="src_faq",
                source_name="faq.html",
                title="Eligibility Criteria",
                content="Applicants must have 2 years in business and minimum revenue of $500,000.",
                category="qualification",
                version="1.0",
                content_hash="def67890",
            ),
        ]
        store.index_chunks(chunks)
        retriever = HybridRetriever(store=store)
        return retriever

    def test_hybrid_search_ranks_correct_content(self, setup_retriever):
        result = setup_retriever.search("How long is the loan processing time?")
        assert result.grounded is True
        assert result.confidence > 0.60
        assert len(result.matches) > 0
        top_match = result.matches[0]
        assert "5-7 business days" in top_match.chunk.content

    def test_reranker_prioritizes_numeric_entities(self):
        reranker = Reranker()
        c1 = KBChunk(
            record_id="r1",
            source_id="s1",
            title="General Policy",
            content="We offer various loans for small businesses.",
        )
        c2 = KBChunk(
            record_id="r2",
            source_id="s2",
            title="Starter Rates",
            content="Starter loans feature interest rate of 12.5% and max amount $2,000,000.",
        )
        cands = [
            RetrievalScore(chunk=c1, combined_score=0.7),
            RetrievalScore(chunk=c2, combined_score=0.7),
        ]
        reranked = reranker.rerank("12.5% interest rate Starter loan", cands)
        assert reranked[0].chunk.record_id == "r2"


# =============================================================================
# 6. Confidence Gating & Zero Hallucination Tests
# =============================================================================

class TestConfidenceGate:
    def test_abstention_on_out_of_scope_query(self):
        store = KBVectorStore()
        c = KBChunk(
            record_id="r1",
            source_id="s1",
            title="Loan Policy",
            content="Standard business loan requires registration and financial statements.",
        )
        store.index_chunks([c])
        retriever = HybridRetriever(store=store)

        result = retriever.search("What is the recipe for chocolate chip cookies?")
        assert result.grounded is False
        assert result.confidence < 0.60
        assert "don't have verified information" in result.answer
        assert result.abstain_reason is not None

    def test_grounded_answer_on_high_confidence(self):
        gate = ConfidenceGate(threshold=0.60)
        c = KBChunk(
            record_id="r1",
            source_id="s1",
            title="Revenue Requirement",
            content="Minimum monthly revenue is $500,000 for Starter loans.",
        )
        cand = RetrievalScore(chunk=c, combined_score=0.85, rerank_score=0.88)
        conf, should_answer, reason = gate.evaluate("minimum monthly revenue", [cand])
        assert should_answer is True
        assert conf >= 0.60
        assert reason is None


# =============================================================================
# 7. Citation Tests
# =============================================================================

class TestCitations:
    def test_citation_builder(self):
        chunk = KBChunk(
            record_id="rec_99",
            source_id="src_99",
            source_name="Loan_Policy_2024.pdf",
            source_page=4,
            section="Underwriting Rules",
            title="Eligibility",
            content="Applicants must have 2 years of operational history.\nAudited statements required.",
            version="2.1",
            content_hash="89abcdef01234567",
        )
        cit = CitationBuilder.build_citation(chunk, confidence=0.92)
        assert cit.source_name == "Loan_Policy_2024.pdf"
        assert cit.source_page == 4
        assert cit.section == "Underwriting Rules"
        assert cit.version == "2.1"
        assert cit.content_hash == "89abcdef01234567"

        formatted = CitationBuilder.format_citation_tag(cit)
        assert "Loan_Policy_2024.pdf" in formatted
        assert "v2.1" in formatted
        assert "hash:89abcdef" in formatted

    def test_format_grounded_answer(self):
        cit = Citation(
            source_name="FAQ.html",
            source_id="src_1",
            record_id="r_1",
            chunk_id="c_1",
            section="Processing",
            version="1.0",
        )
        answer = CitationBuilder.format_grounded_answer("Processing takes 5 days.", [cit])
        assert "Processing takes 5 days." in answer
        assert "Sources:" in answer
        assert "FAQ.html" in answer


# =============================================================================
# 8. API Endpoint Tests
# =============================================================================

class TestKBAPIEndpoints:
    @pytest.fixture(autouse=True)
    def setup_api(self):
        client = TestClient(app)
        # Seed test chunk into API store
        from app.api.kb import get_store
        store = get_store()
        store.clear()
        c = KBChunk(
            record_id="api_rec_1",
            source_id="api_src_1",
            source_name="business_faq.html",
            title="Documents",
            content="Required documents include business registration, 6 months bank statements, and ID.",
            category="faq",
            version="1.0",
            content_hash="feedface1234",
        )
        store.index_chunks([c])
        return client

    def test_search_endpoint_standard(self, setup_api):
        client = setup_api
        resp = client.post("/api/v1/kb/search", json={"query": "What documents are required?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["grounded"] is True
        assert data["confidence"] >= 0.60
        assert len(data["citations"]) > 0
        assert "business registration" in data["answer"].lower()

    def test_search_endpoint_vapi_format(self, setup_api):
        client = setup_api
        # Vapi passes messages array
        vapi_payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What documents are required?"},
            ]
        }
        resp = client.post("/kb/search", json=vapi_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["grounded"] is True
        assert "business registration" in data["answer"].lower()

    def test_search_endpoint_abstains_on_out_of_scope(self, setup_api):
        client = setup_api
        resp = client.post(
            "/api/v1/kb/search",
            json={"query": "What is the capital of Mars?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["grounded"] is False
        assert "don't have verified information" in data["answer"]
        assert data["abstain_reason"] is not None

    def test_stats_endpoint(self, setup_api):
        client = setup_api
        resp = client.get("/api/v1/kb/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_chunks"] >= 1
        assert "confidence_threshold" in data

    def test_chunks_endpoint(self, setup_api):
        client = setup_api
        resp = client.get("/api/v1/kb/chunks?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["chunks"]) >= 1
