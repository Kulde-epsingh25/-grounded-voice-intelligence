"""
Tests for LatencyTracker: T0-T4 calculation, percentiles P50 and P95, sample size handling.
"""

from app.realtime.latency import LatencyTracker
from app.realtime.models import LatencyMeasurement


def test_latency_empty_tracker():
    tracker = LatencyTracker()
    summary = tracker.get_summary()
    assert summary["end_to_end"]["sample_size"] == 0
    assert summary["end_to_end"]["p50_ms"] is None
    assert summary["end_to_end"]["p95_ms"] is None


def test_latency_p50_and_p95_percentiles():
    tracker = LatencyTracker()
    # Record 20 measurements with known latencies 10ms, 20ms, ..., 200ms
    for i in range(1, 21):
        delta = i * 0.010  # 10ms to 200ms
        meas = LatencyMeasurement(
            event_id=f"e_{i}",
            t0_audio_received=1.0,
            t1_transcript_available=1.0 + delta * 0.5,
            t2_signal_detected=1.0 + delta * 0.7,
            t3_nudge_generated=1.0 + delta * 0.9,
            t4_delivered=1.0 + delta,
        )
        tracker.record(meas)

    summary = tracker.get_summary()
    e2e = summary["end_to_end"]
    assert e2e["sample_size"] == 20
    assert e2e["min_ms"] == 10.0
    assert e2e["max_ms"] == 200.0
    # Median of 1..20 is around 105ms
    assert 100.0 <= e2e["p50_ms"] <= 110.0
    # 95th percentile is around 190.5ms
    assert 185.0 <= e2e["p95_ms"] <= 200.0


def test_latency_sample_count():
    tracker = LatencyTracker()
    assert tracker.sample_count == 0
    meas = LatencyMeasurement(
        event_id="e1",
        t0_audio_received=0.0,
        t1_transcript_available=0.05,
    )
    tracker.record(meas)
    assert tracker.sample_count == 1
