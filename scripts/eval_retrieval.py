"""
Q2 Knowledge Base — Retrieval Evaluation Runner.

Evaluates retrieval quality against data/eval/retrieval.json:
- Grounded query precision
- Citation presence and lineage
- Out-of-scope abstention enforcement (zero-hallucination verification)
- Latency measurements (P50, P95)

Saves evidence output to evidence/q2/retrieval_results.json.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.logging import setup_logging
from app.kb.models import KBRecord
from app.retrieval import HybridRetriever, KBVectorStore, SectionChunker


def run_evaluation() -> dict:
    setup_logging("INFO")

    eval_file = Path("data/eval/retrieval.json")
    if not eval_file.exists():
        print(f"Error: {eval_file} not found")
        sys.exit(1)

    with open(eval_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    # Load KB records
    kb_file = Path("data/processed/kb_records.json")
    if not kb_file.exists():
        print(f"Error: {kb_file} not found. Run scripts/ingest.py first.")
        sys.exit(1)

    with open(kb_file, "r", encoding="utf-8") as f:
        records_data = json.load(f)
    records = [KBRecord.model_validate(r) for r in records_data]

    chunker = SectionChunker()
    chunks = chunker.chunk_records(records)

    store = KBVectorStore()
    store.index_chunks(chunks)

    retriever = HybridRetriever(store=store)

    eval_results = []
    latencies: list[float] = []
    correct_count = 0

    print("=" * 70)
    print("RUNNING Q2 RETRIEVAL EVALUATION")
    print("=" * 70)

    for tc in test_cases:
        qid = tc["id"]
        qtype = tc["type"]
        question = tc["question"]
        expected_src = tc.get("expected_source")
        should_answer = tc["should_answer"]
        expected_keywords = tc.get("expected_keywords", [])

        t0 = time.perf_counter()
        result = retriever.search(question, top_k=5)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000
        latencies.append(latency_ms)

        # Check verdict
        verdict = "incorrect"
        if not should_answer:
            # Must safely abstain without hallucination
            if not result.grounded and "don't have verified information" in result.answer:
                verdict = "correct"
                correct_count += 1
        else:
            # Must answer and retrieve expected source / keywords
            if result.grounded and result.matches:
                top_match = result.matches[0]
                matched_src = (
                    expected_src in (top_match.chunk.source_name or "")
                    or expected_src in (top_match.chunk.title or "")
                ) if expected_src else True

                content_lower = top_match.chunk.content.lower()
                matched_kw = any(kw.lower() in content_lower for kw in expected_keywords) if expected_keywords else True

                if matched_src or matched_kw:
                    verdict = "correct"
                    correct_count += 1

        top_citation = result.citations[0].model_dump(mode="json") if result.citations else None

        case_summary = {
            "id": qid,
            "type": qtype,
            "question": question,
            "grounded": result.grounded,
            "confidence": result.confidence,
            "verdict": verdict,
            "latency_ms": round(latency_ms, 2),
            "citations_count": len(result.citations),
            "top_citation": top_citation,
            "answer_preview": result.answer[:120] + "..." if len(result.answer) > 120 else result.answer,
        }
        eval_results.append(case_summary)

        print(f"\n[{qid}] {qtype.upper()}: {question}")
        print(f"  Verdict:    {verdict.upper()} (grounded={result.grounded}, conf={result.confidence:.2f})")
        print(f"  Latency:    {latency_ms:.2f} ms")
        if top_citation:
            print(f"  Source:     {top_citation['source_name']} (v{top_citation['version']})")

    accuracy = correct_count / max(1, len(test_cases))
    p50_latency = statistics.median(latencies) if latencies else 0.0
    p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies or [0.0])

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_queries": len(test_cases),
        "correct": correct_count,
        "accuracy": round(accuracy, 4),
        "latency_p50_ms": round(p50_latency, 2),
        "latency_p95_ms": round(p95_latency, 2),
        "results": eval_results,
    }

    # Save to evidence/q2/retrieval_results.json
    out_dir = Path("evidence/q2")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "retrieval_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total test queries: {len(test_cases)}")
    print(f"Correct verdicts:   {correct_count} / {len(test_cases)} ({accuracy * 100:.1f}%)")
    print(f"Latency P50:        {p50_latency:.2f} ms")
    print(f"Latency P95:        {p95_latency:.2f} ms")
    print(f"Results saved to:   {out_path}")

    return summary


if __name__ == "__main__":
    run_evaluation()
