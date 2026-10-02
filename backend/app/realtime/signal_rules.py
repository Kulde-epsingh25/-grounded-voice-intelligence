"""
AI Engineer Assessment — Deterministic Signal Rules Engine.

Rule-based pattern detection for missed cross-sells, compliance gaps,
customer frustration, payment difficulty/risk, callback needs, and buying signals.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.realtime.models import Signal, SignalType, Speaker


class RulePattern:
    def __init__(
        self,
        name: str,
        signal_type: SignalType,
        regex_patterns: List[str],
        base_confidence: float,
        severity: str,
        speaker_constraint: Optional[Speaker] = None,
        context_condition: Optional[str] = None,
    ):
        self.name = name
        self.signal_type = signal_type
        self.regexes = [re.compile(p, re.IGNORECASE) for p in regex_patterns]
        self.base_confidence = base_confidence
        self.severity = severity
        self.speaker_constraint = speaker_constraint
        self.context_condition = context_condition


DEFAULT_RULES: List[RulePattern] = [
    # 1. Missed Opportunity / Cross-Sell
    RulePattern(
        name="cross_sell_second_vehicle",
        signal_type=SignalType.MISSED_OPPORTUNITY,
        regex_patterns=[
            r"\b(another|second|2nd|other)\s+(vehicle|car|motorcycle|motor|truck|auto)\b",
            r"\b(mobil|motor|kendaraan)\s+(lain|kedua|satu lagi)\b",
            r"\bmay\s+(isa\s+pang|isa\s+pang\s+sasakyan|pangalawang\s+kotse)\b",
        ],
        base_confidence=0.88,
        severity="medium",
        speaker_constraint=Speaker.CUSTOMER,
    ),
    RulePattern(
        name="cross_sell_family_dependent",
        signal_type=SignalType.MISSED_OPPORTUNITY,
        regex_patterns=[
            r"\b(also|extra|additional)\s+(coverage|insurance|policy)\s+for\s+my\s+(wife|husband|child|son|daughter|family)\b",
            r"\b(asuransi|perlindungan)\s+(buat|untuk)\s+(anak|istri|suami|keluarga)\b",
            r"\bpara\s+sa\s+(anak|asawa|pamilya)\s+ko\b",
        ],
        base_confidence=0.86,
        severity="medium",
        speaker_constraint=Speaker.CUSTOMER,
    ),
    RulePattern(
        name="cross_sell_second_business",
        signal_type=SignalType.MISSED_OPPORTUNITY,
        regex_patterns=[
            r"\b(second|another|2nd)\s+(branch|business|store|company|shop)\b",
            r"\b(cabang|usaha|toko|bisnis)\s+(kedua|lain|baru)\b",
        ],
        base_confidence=0.87,
        severity="medium",
        speaker_constraint=Speaker.CUSTOMER,
    ),

    # 2. Compliance Gap
    RulePattern(
        name="compliance_missing_recording_disclosure",
        signal_type=SignalType.COMPLIANCE_GAP,
        regex_patterns=[
            r"\b(social security|credit card|bank account|income|revenue|gaji|npwp|rekening)\b",
        ],
        base_confidence=0.92,
        severity="critical",
        context_condition="require_prior_recording_disclosure",
    ),
    RulePattern(
        name="compliance_explicit_rate_guarantee_risk",
        signal_type=SignalType.COMPLIANCE_GAP,
        regex_patterns=[
            r"\b(guaranteed\s+(return|approval|zero\s+risk)|pasti\s+cair\s+tanpa\s+syarat|walang\s+risk)\b",
        ],
        base_confidence=0.94,
        severity="critical",
        speaker_constraint=Speaker.AGENT,
    ),

    # 3. Callback Need
    RulePattern(
        name="callback_busy_driving",
        signal_type=SignalType.CALLBACK_NEED,
        regex_patterns=[
            r"\b(call\s+(me\s+)?back|call\s+later|busy\s+right\s+now|driving\s+right\s+now|in\s+a\s+meeting)\b",
            r"\b(hubungi\s+(saya\s+)?nanti|telepon\s+lagi\s+nanti|lagi\s+sibuk|lagi\s+di\s+jalan|lagi\s+meeting)\b",
            r"\b(tumawag\s+(na\s+lang\s+)?mamaya|busy\s+ako\s+ngayon|nagmamaneho\s+ako)\b",
        ],
        base_confidence=0.92,
        severity="medium",
        speaker_constraint=Speaker.CUSTOMER,
    ),

    # 4. Payment Difficulty / Financial Risk
    RulePattern(
        name="financial_risk_inability_to_pay",
        signal_type=SignalType.RISK,
        regex_patterns=[
            r"\b(can'?t\s+pay|cannot\s+afford|lost\s+my\s+job|bankruptcy|behind\s+on\s+payments|financial\s+hardship)\b",
            r"\b(nggak\s+sanggup\s+bayar|tidak\s+bisa\s+bayar|kehilangan\s+pekerjaan|kena\s+phk|gagal\s+bayar)\b",
            r"\b(hindi\s+ko\s+kayang\s+bayaran|nawalan\s+ng\s+trabaho|nagigipit\s+ako)\b",
        ],
        base_confidence=0.90,
        severity="high",
        speaker_constraint=Speaker.CUSTOMER,
    ),

    # 5. Customer Frustration
    RulePattern(
        name="customer_frustration_repetition_delay",
        signal_type=SignalType.FRUSTRATION,
        regex_patterns=[
            r"\b(explained\s+this\s+(three|multiple|several|2|3)\s+times|taking\s+so\s+long|speak\s+to\s+(your\s+)?(manager|supervisor)|waste\s+of\s+(my\s+)?time|ridiculous)\b",
            r"\b(sudah\s+(tiga|berkali-kali)\s+kali\s+saya\s+jelaskan|lama\s+banget|mana\s+manajer|buang-buang\s+waktu|bikin\s+emosi)\b",
            r"\b(pangatlong\s+beses\s+ko\s+nang\s+paliwanag|ang\s+tagal-tagal|nagsasayang\s+ng\s+oras|kakausapin\s+ko\s+ang\s+manager)\b",
        ],
        base_confidence=0.93,
        severity="high",
        speaker_constraint=Speaker.CUSTOMER,
    ),

    # 6. Buying Signal
    RulePattern(
        name="customer_ready_to_buy",
        signal_type=SignalType.BUYING_SIGNAL,
        regex_patterns=[
            r"\b(ready\s+to\s+(buy|sign|proceed)|where\s+do\s+I\s+sign|take\s+my\s+card|send\s+the\s+agreement|sign\s+up\s+today)\b",
            r"\b(mau\s+ambil\s+(paket|penawaran)\s+ini|saya\s+setuju|kirim\s+kontraknya|langsung\s+proses\s+aja)\b",
            r"\b(kukunin\s+ko\s+na|pirmahan\s+ko\s+na|i-process\s+na\s+natin)\b",
        ],
        base_confidence=0.88,
        severity="medium",
        speaker_constraint=Speaker.CUSTOMER,
    ),
]


class DeterministicSignalDetector:
    """Evaluates rule-based signals against transcript text and contextual history."""

    def __init__(self, rules: Optional[List[RulePattern]] = None):
        self.rules = rules or DEFAULT_RULES

    def detect(
        self,
        text: str,
        speaker: Speaker,
        timestamp: float,
        history: List[dict],
    ) -> List[Signal]:
        signals: List[Signal] = []
        normalized_text = text.strip()
        if not normalized_text:
            return signals

        # Check if recording disclosure has occurred in session history
        has_recording_disclosure = any(
            re.search(r"\b(recorded|recording|quality\s+and\s+training|rekam|nirerekord)\b", h.get("text", ""), re.IGNORECASE)
            for h in history
        )

        for rule in self.rules:
            # Check speaker constraint
            if rule.speaker_constraint and rule.speaker_constraint != speaker:
                continue

            # Check context conditions
            if rule.context_condition == "require_prior_recording_disclosure":
                # If disclosure already occurred, no compliance gap
                if has_recording_disclosure:
                    continue

            # Match patterns
            matched = False
            evidence = ""
            for regex in rule.regexes:
                match = regex.search(normalized_text)
                if match:
                    matched = True
                    evidence = match.group(0)
                    break

            if matched:
                sig = Signal(
                    signal_id=f"sig_{rule.name}_{int(timestamp*1000)}",
                    type=rule.signal_type,
                    timestamp=timestamp,
                    confidence=rule.base_confidence,
                    speaker=speaker,
                    evidence_text=evidence,
                    severity=rule.severity,
                    source="rule",
                    metadata={"rule_name": rule.name, "full_utterance": normalized_text},
                )
                signals.append(sig)

        return signals
