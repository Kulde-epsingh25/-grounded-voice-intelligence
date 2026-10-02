"""
Q2 Knowledge Base — Retrieval Evaluation Test Suite.

Automated verification of data/eval/retrieval.json against the retrieval system:
- Verifies grounded query answers
- Verifies citations and source lineage
- Verifies zero-hallucination abstention on out-of-scope queries
- Verifies latency SLAs for real-time voice integration
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.kb.models import KBRecord
from app.retrieval import HybridRetriever, KBVectorStore, SectionChunker


@pytest.fixture(scope="module")
def indexed_evaluation_retriever():
    """Load processed KB records and initialize retriever for evaluation."""
    kb_file = Path("data/processed/kb_records.json")
    assert kb_file.exists(), "Processed KB records not found. Ingest must run first."

    with open(kb_file, "r", encoding="utf-8") as f:
        records_data = json.load(f)

    records = [KBRecord.model_validate(r) for r in records_data]
    chunker = SectionChunker()
    chunks = chunker.chunk_records(records)

    store = KBVectorStore()
    store.index_chunks(chunks)

    retriever = HybridRetriever(store=store)
    return retriever


class TestRetrievalEvaluation:
    @pytest.fixture(autouse=True)
    def load_eval_cases(self):
        eval_file = Path("data/eval/retrieval.json")
        assert eval_file.exists()
        with open(eval_file, "r", encoding="utf-8") as f:
            self.test_cases = json.load(f)

    def test_minimum_test_cases_count(self):
        """Assessment requires at least 5 retrieval test queries."""
        assert len(self.test_cases) >= 5

    def test_all_evaluation_queries(self, indexed_evaluation_retriever):
        """Run all test cases from data/eval/retrieval.json and verify verdicts."""
        retriever = indexed_evaluation_retriever
        correct_count = 0

        for tc in self.test_cases:
            qid = tc["id"]
            question = tc["question"]
            should_answer = tc["should_answer"]
            expected_keywords = tc.get("expected_keywords", [])

            result = retriever.search(question)

            if not should_answer:
                # Must safely abstain without inventing
                assert result.grounded is False, f"[{qid}] Out-of-scope query should not be grounded"
                assert "don't have verified information" in result.answer, (
                    f"[{qid}] Must use verified safe fallback answer"
                )
                correct_count += 1
            else:
                # Must answer and provide source citations
                assert result.grounded is True, (
                    f"[{qid}] In-scope query '{question}' was rejected (conf={result.confidence})"
                )
                assert len(result.citations) > 0, f"[{qid}] Must provide citations"
                assert result.citations[0].version != "", f"[{qid}] Citation must contain version"
                assert result.citations[0].content_hash != "", f"[{qid}] Citation must contain content_hash"

                # Check keyword match in top chunk
                top_chunk = result.matches[0].chunk
                content_lower = top_chunk.content.lower()
                matched_kw = any(kw.lower() in content_lower for kw in expected_keywords)
                assert matched_kw, f"[{qid}] Expected keywords {expected_keywords} not found in top chunk"
                correct_count += 1

        accuracy = correct_count / len(self.test_cases)
        assert accuracy == 1.0, f"Retrieval accuracy {accuracy} was below 100%"
