"""Evaluation harness for multilingual ASR, pronunciation, and regional accents."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field


class ASREvaluationItemResult(BaseModel):
    """Result for a single ASR test utterance."""
    id: str
    market: str
    category: str
    reference_transcript: str
    hypothesis_transcript: Optional[str] = None
    wer: Optional[float] = None
    critical_terms_present: Optional[bool] = None
    status: str = "NOT RUN — AUDIO NOT AVAILABLE"


class ASREvaluationSummary(BaseModel):
    """Aggregate evaluation report across an ASR test suite."""
    market: str
    total_test_cases: int
    executed_cases: int
    audio_available: bool
    status: str
    average_wer: Optional[float] = None
    critical_term_accuracy: Optional[float] = None
    code_switch_accuracy: Optional[float] = None
    detailed_results: list[ASREvaluationItemResult] = Field(default_factory=list)


def evaluate_asr_manifest(manifest_path: str | Path) -> ASREvaluationSummary:
    """Read an ASR test suite JSON and compute or manifest evaluation results."""
    p = Path(manifest_path)
    if not p.exists():
        raise FileNotFoundError(f"ASR manifest not found at {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    market = data[0]["market"] if data else "UNKNOWN"
    total = len(data)
    items: list[ASREvaluationItemResult] = []

    for entry in data:
        items.append(
            ASREvaluationItemResult(
                id=entry["id"],
                market=entry["market"],
                category=entry.get("category", "general"),
                reference_transcript=entry["reference_transcript"],
                hypothesis_transcript=entry.get("hypothesis"),
                status=entry.get("status", "NOT RUN — AUDIO NOT AVAILABLE"),
            )
        )

    # All tests currently have audio: null in assessment baseline
    return ASREvaluationSummary(
        market=market,
        total_test_cases=total,
        executed_cases=0,
        audio_available=False,
        status="NOT RUN — AUDIO NOT AVAILABLE",
        average_wer=None,
        critical_term_accuracy=None,
        code_switch_accuracy=None,
        detailed_results=items,
    )
