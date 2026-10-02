"""
AI Engineer Assessment — Q4 Signal & False Positive Evaluator.

Evaluates signal extraction and nudge triggering across labelled cases,
measuring True Positives, False Positives, True Negatives, False Negatives,
Precision, Recall, and False Positive Rate.
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.realtime.models import Speaker, TranscriptEvent
from app.realtime.nudge_engine import NudgeEngine
from app.realtime.signals import SignalExtractor
CASES_FILE = ROOT_DIR / "data" / "eval" / "q4_signals" / "cases.json"
EVIDENCE_DIR = ROOT_DIR / "evidence" / "q4"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def evaluate_q4_signals(output_dir: Path = EVIDENCE_DIR):
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    extractor = SignalExtractor()
    nudge_engine = NudgeEngine()

    tp = 0
    fp = 0
    tn = 0
    fn = 0
    failures = []
    case_results = []

    for idx, case in enumerate(cases):
        extractor.reset()
        nudge_engine.reset()

        speaker = Speaker[case.get("speaker", "CUSTOMER")]
        text = case["text"]
        should_alert = case["should_alert"]

        evt = TranscriptEvent(
            session_id=f"eval_sess_{idx}",
            chunk_sequence=idx,
            timestamp=float(idx * 2.0),
            text=text,
            is_final=True,
            speaker=speaker,
            confidence=1.0,
        )

        signals = extractor.process_event(evt)
        active_nudge = None
        for sig in signals:
            nudge = nudge_engine.process(sig, session_id=evt.session_id, current_time=evt.timestamp)
            if nudge:
                active_nudge = nudge
                break

        predicted_alert = active_nudge is not None
        matched_type = active_nudge.type.value if active_nudge else (signals[0].type.value if signals else None)

        if should_alert and predicted_alert:
            tp += 1
            verdict = "TP"
        elif not should_alert and not predicted_alert:
            tn += 1
            verdict = "TN"
        elif not should_alert and predicted_alert:
            fp += 1
            verdict = "FP"
            failures.append({
                "case_id": case["id"],
                "expected": "No alert",
                "predicted": f"Alert: {matched_type}",
                "confidence": active_nudge.confidence if active_nudge else 0.0,
                "reason": "False Positive trigger on neutral/benign text",
            })
        else:
            fn += 1
            verdict = "FN"
            failures.append({
                "case_id": case["id"],
                "expected": f"Alert: {case.get('expected_signal_type')}",
                "predicted": "No alert emitted",
                "confidence": signals[0].confidence if signals else 0.0,
                "reason": "Signal or nudge failed to trigger for target pattern",
            })

        case_results.append({
            "case_id": case["id"],
            "category": case["category"],
            "text": text,
            "should_alert": should_alert,
            "predicted_alert": predicted_alert,
            "verdict": verdict,
            "signal_type": matched_type,
            "nudge_message": active_nudge.message if active_nudge else None,
        })

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    summary = {
        "evaluation_dataset": str(CASES_FILE),
        "total_cases": total,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "false_positive_rate": round(fpr, 4),
            "f1_score": round(f1, 4),
        },
        "failures_count": len(failures),
        "failures": failures,
    }

    # Save evidence to the requested location. Tests pass a temporary directory
    # so routine test runs never rewrite tracked submission artifacts.
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "false_positive_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with open(output_dir / "signal_results.json", "w", encoding="utf-8") as f:
        json.dump(case_results, f, indent=2)

    print("=== Q4 False-Positive & Signal Evaluation ===")
    print(f"Total Cases: {total}")
    print(f"TP: {tp} | TN: {tn} | FP: {fp} | FN: {fn}")
    print(f"Precision: {precision*100:.1f}% | Recall: {recall*100:.1f}% | FPR: {fpr*100:.1f}% | F1: {f1*100:.1f}%")
    print(f"Results saved to {output_dir / 'false_positive_results.json'}")

    return summary


if __name__ == "__main__":
    evaluate_q4_signals()
