"""
AI Engineer Assessment — Latency Instrumentation and Percentile Calculation.

Instruments point-in-time timestamps across all pipeline stages (T0 through T4)
and computes true P50 and P95 percentiles with explicit sample size validation.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from app.realtime.models import LatencyMeasurement


class LatencyTracker:
    """
    Collects timing points for every event:
    T0 = audio chunk received
    T1 = transcript available
    T2 = signal detected
    T3 = nudge generated
    T4 = dashboard/WebSocket delivery
    """

    def __init__(self):
        self._measurements: List[LatencyMeasurement] = []

    def record(self, measurement: LatencyMeasurement) -> None:
        self._measurements.append(measurement)

    def clear(self) -> None:
        self._measurements.clear()

    @property
    def sample_count(self) -> int:
        return len(self._measurements)

    def _calculate_percentile(self, values: List[float], percentile: float) -> Optional[float]:
        if not values:
            return None
        sorted_vals = sorted(values)
        if len(sorted_vals) == 1:
            return sorted_vals[0]
        # Linear interpolation percentile
        k = (len(sorted_vals) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return round(sorted_vals[int(k)], 2)
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return round(d0 + d1, 2)

    def get_summary(self) -> Dict[str, dict]:
        """
        Produce P50, P95, mean, min, max, and sample size for each latency segment.
        """
        asr_latencies = [m.asr_latency_ms for m in self._measurements]
        signal_latencies = [m.signal_latency_ms for m in self._measurements if m.signal_latency_ms is not None]
        nudge_latencies = [m.nudge_latency_ms for m in self._measurements if m.nudge_latency_ms is not None]
        delivery_latencies = [m.delivery_latency_ms for m in self._measurements if m.delivery_latency_ms is not None]
        e2e_latencies = [m.end_to_end_ms for m in self._measurements]

        def _stats(vals: List[float]) -> dict:
            if not vals:
                return {"sample_size": 0, "p50_ms": None, "p95_ms": None, "min_ms": None, "max_ms": None}
            return {
                "sample_size": len(vals),
                "p50_ms": self._calculate_percentile(vals, 50.0),
                "p95_ms": self._calculate_percentile(vals, 95.0),
                "min_ms": round(min(vals), 2),
                "max_ms": round(max(vals), 2),
                "mean_ms": round(sum(vals) / len(vals), 2),
            }

        return {
            "asr": _stats(asr_latencies),
            "signal": _stats(signal_latencies),
            "nudge": _stats(nudge_latencies),
            "delivery": _stats(delivery_latencies),
            "end_to_end": _stats(e2e_latencies),
        }
