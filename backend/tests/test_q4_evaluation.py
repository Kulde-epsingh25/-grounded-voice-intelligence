"""
Tests for Q4 evaluation harness: TP, FP, TN, FN metrics and labelled dataset integrity.
"""

import json
from pathlib import Path
from scripts.eval_q4 import evaluate_q4_signals

ROOT_DIR = Path(__file__).resolve().parents[2]


def test_q4_evaluation_dataset_structure():
    cases_file = ROOT_DIR / "data" / "eval" / "q4_signals" / "cases.json"
    assert cases_file.exists(), "Q4 cases.json dataset must exist"
    with open(cases_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    # Must have at least 20 test cases (we have 28)
    assert len(cases) >= 20
    for c in cases:
        assert "id" in c
        assert "text" in c
        assert "category" in c
        assert "should_alert" in c
        assert isinstance(c["should_alert"], bool)


def test_q4_evaluation_metrics_execution(tmp_path):
    summary = evaluate_q4_signals(output_dir=tmp_path)
    assert summary["total_cases"] >= 20
    assert summary["true_positives"] > 0
    assert summary["true_negatives"] > 0
    assert summary["metrics"]["precision"] >= 0.85
    assert summary["metrics"]["recall"] >= 0.85
    assert "failures" in summary
    assert (tmp_path / "false_positive_results.json").exists()
    assert (tmp_path / "signal_results.json").exists()
