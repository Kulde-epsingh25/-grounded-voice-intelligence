"""
Tests for NudgeEngine: confidence thresholding, duplicate suppression, cooldown, expiry, and priority.
"""

from app.realtime.models import NudgePriority, NudgeStatus, Signal, SignalType, Speaker
from app.realtime.nudge_engine import NudgeEngine, NudgeEngineConfig


def test_confidence_threshold_suppresses_low_confidence():
    engine = NudgeEngine(NudgeEngineConfig(min_confidence=0.70))
    low_conf_signal = Signal(
        signal_id="sig_low",
        type=SignalType.MISSED_OPPORTUNITY,
        timestamp=1.0,
        confidence=0.45,  # Below threshold
        speaker=Speaker.CUSTOMER,
        evidence_text="mumble vehicle",
    )
    nudge = engine.process(low_conf_signal, session_id="s1", current_time=1.0)
    assert nudge is None
    assert engine.suppressed_count == 1


def test_duplicate_suppression():
    engine = NudgeEngine(NudgeEngineConfig())
    sig1 = Signal(
        signal_id="sig_1",
        type=SignalType.MISSED_OPPORTUNITY,
        timestamp=1.0,
        confidence=0.88,
        speaker=Speaker.CUSTOMER,
        evidence_text="second car",
        metadata={"rule_name": "cross_sell_second_vehicle"},
    )
    nudge1 = engine.process(sig1, session_id="s1", current_time=1.0)
    assert nudge1 is not None
    assert nudge1.status == NudgeStatus.ACTIVE

    # Immediately following duplicate signal
    sig2 = Signal(
        signal_id="sig_2",
        type=SignalType.MISSED_OPPORTUNITY,
        timestamp=2.0,
        confidence=0.89,
        speaker=Speaker.CUSTOMER,
        evidence_text="another car",
        metadata={"rule_name": "cross_sell_second_vehicle"},
    )
    nudge2 = engine.process(sig2, session_id="s1", current_time=2.0)
    assert nudge2 is None
    assert engine.suppressed_count == 1


def test_cooldown_window_suppression():
    # Cooldown of 30 seconds
    engine = NudgeEngine(NudgeEngineConfig(default_cooldown_seconds=30.0, default_expiry_seconds=10.0))
    sig1 = Signal(
        signal_id="sig_1",
        type=SignalType.MISSED_OPPORTUNITY,
        timestamp=1.0,
        confidence=0.88,
        speaker=Speaker.CUSTOMER,
        evidence_text="second car",
        metadata={"rule_name": "cross_sell_second_vehicle"},
    )
    nudge1 = engine.process(sig1, session_id="s1", current_time=1.0)
    assert nudge1 is not None

    # Advance time to t=15s (after expiry of 10s, but WITHIN 30s cooldown)
    sig2 = Signal(
        signal_id="sig_2",
        type=SignalType.MISSED_OPPORTUNITY,
        timestamp=15.0,
        confidence=0.88,
        speaker=Speaker.CUSTOMER,
        evidence_text="second car",
        metadata={"rule_name": "cross_sell_second_vehicle"},
    )
    nudge2 = engine.process(sig2, session_id="s1", current_time=15.0)
    assert nudge2 is None  # Suppressed due to cooldown

    # Advance time to t=35s (after cooldown)
    sig3 = Signal(
        signal_id="sig_3",
        type=SignalType.MISSED_OPPORTUNITY,
        timestamp=35.0,
        confidence=0.88,
        speaker=Speaker.CUSTOMER,
        evidence_text="second car",
        metadata={"rule_name": "cross_sell_second_vehicle"},
    )
    nudge3 = engine.process(sig3, session_id="s1", current_time=35.0)
    assert nudge3 is not None  # Allowed after cooldown!


def test_expiry_pruning():
    engine = NudgeEngine(NudgeEngineConfig(default_expiry_seconds=10.0))
    sig = Signal(
        signal_id="sig_1",
        type=SignalType.FRUSTRATION,
        timestamp=1.0,
        confidence=0.92,
        speaker=Speaker.CUSTOMER,
        evidence_text="taking so long",
    )
    engine.process(sig, session_id="s1", current_time=1.0)
    assert len(engine.active_nudges) == 1

    # Check at t=12s
    expired = engine.prune_expired(current_time=12.0)
    assert len(expired) == 1
    assert expired[0].status == NudgeStatus.EXPIRED
    assert len(engine.active_nudges) == 0


def test_priority_assignment():
    engine = NudgeEngine()
    # Critical compliance
    sig_comp = Signal(
        signal_id="c1",
        type=SignalType.COMPLIANCE_GAP,
        timestamp=1.0,
        confidence=0.95,
        evidence_text="SSN requested",
        severity="critical",
    )
    nudge_comp = engine.process(sig_comp, "s1", 1.0)
    assert nudge_comp.priority == NudgePriority.HIGH

    # High frustration
    sig_fru = Signal(
        signal_id="f1",
        type=SignalType.FRUSTRATION,
        timestamp=5.0,
        confidence=0.92,
        evidence_text="waste of time",
        severity="high",
    )
    nudge_fru = engine.process(sig_fru, "s1", 5.0)
    assert nudge_fru.priority == NudgePriority.HIGH
