"""
Tests for deterministic and semantic signal extraction.
"""

from app.realtime.models import SignalType, Speaker, TranscriptEvent
from app.realtime.signals import SignalExtractor


def test_missed_cross_sell_vehicle():
    extractor = SignalExtractor()
    evt = TranscriptEvent(
        session_id="s1",
        chunk_sequence=1,
        timestamp=2.0,
        text="I also have another vehicle that I might want to insure.",
        is_final=True,
        speaker=Speaker.CUSTOMER,
    )
    signals = extractor.process_event(evt)
    cross_sells = [s for s in signals if s.type == SignalType.MISSED_OPPORTUNITY]
    assert len(cross_sells) == 1
    assert "vehicle" in cross_sells[0].evidence_text.lower()
    assert cross_sells[0].confidence >= 0.85


def test_compliance_gap_missing_recording_disclosure():
    extractor = SignalExtractor()
    evt = TranscriptEvent(
        session_id="s1",
        chunk_sequence=1,
        timestamp=2.0,
        text="Please provide your social security number and revenue.",
        is_final=True,
        speaker=Speaker.AGENT,
    )
    signals = extractor.process_event(evt)
    compliance_sigs = [s for s in signals if s.type == SignalType.COMPLIANCE_GAP]
    assert len(compliance_sigs) == 1
    assert compliance_sigs[0].severity == "critical"


def test_compliance_gap_not_triggered_if_already_disclosed():
    extractor = SignalExtractor()
    # Prior disclosure
    evt_disclose = TranscriptEvent(
        session_id="s1",
        chunk_sequence=1,
        timestamp=1.0,
        text="Thank you for calling. This call is recorded for quality.",
        is_final=True,
        speaker=Speaker.AGENT,
    )
    extractor.process_event(evt_disclose)

    # Next turn asking for details
    evt_ask = TranscriptEvent(
        session_id="s1",
        chunk_sequence=2,
        timestamp=3.0,
        text="Please provide your social security number and revenue.",
        is_final=True,
        speaker=Speaker.AGENT,
    )
    signals = extractor.process_event(evt_ask)
    compliance_sigs = [s for s in signals if s.type == SignalType.COMPLIANCE_GAP]
    assert len(compliance_sigs) == 0


def test_frustration_signal_detection():
    extractor = SignalExtractor()
    evt = TranscriptEvent(
        session_id="s1",
        chunk_sequence=1,
        timestamp=4.0,
        text="I've explained this three times! Why is this taking so long?",
        is_final=True,
        speaker=Speaker.CUSTOMER,
    )
    signals = extractor.process_event(evt)
    frustrations = [s for s in signals if s.type == SignalType.FRUSTRATION]
    assert len(frustrations) == 1
    assert frustrations[0].confidence >= 0.90


def test_callback_signal_detection():
    extractor = SignalExtractor()
    evt = TranscriptEvent(
        session_id="s1",
        chunk_sequence=1,
        timestamp=4.0,
        text="I am driving right now, please call me back in two hours.",
        is_final=True,
        speaker=Speaker.CUSTOMER,
    )
    signals = extractor.process_event(evt)
    callbacks = [s for s in signals if s.type == SignalType.CALLBACK_NEED]
    assert len(callbacks) == 1
    assert callbacks[0].confidence >= 0.85
