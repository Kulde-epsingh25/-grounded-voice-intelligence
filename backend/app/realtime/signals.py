"""
AI Engineer Assessment — Realtime Signal Extractor.

Maintains rolling conversational context and orchestrates deterministic rules
and semantic signal analysis without unbounded LLM token consumption.
"""

from __future__ import annotations

import re
from typing import List, Optional

from app.realtime.models import Signal, SignalType, Speaker, TranscriptEvent
from app.realtime.signal_rules import DeterministicSignalDetector


class SignalExtractor:
    """
    Extracts behavioral signals incrementally from incoming transcript events.
    """

    def __init__(
        self,
        max_context_turns: int = 25,
        semantic_threshold_words: int = 4,
    ):
        self.max_context_turns = max_context_turns
        self.semantic_threshold_words = semantic_threshold_words
        self.rule_detector = DeterministicSignalDetector()
        self.history: List[dict] = []
        self._last_topic = "greeting"

    def reset(self) -> None:
        self.history.clear()
        self._last_topic = "greeting"

    def process_event(self, event: TranscriptEvent) -> List[Signal]:
        """
        Process a single TranscriptEvent through the rolling window and signal extractors.
        """
        text = event.text.strip()
        if not text:
            return []

        word_count = len(text.split())

        # For partials, only process if meaningful length or critical trigger
        if not event.is_final and word_count < self.semantic_threshold_words:
            return []

        # 1. Evaluate deterministic signals
        signals = self.rule_detector.detect(
            text=text,
            speaker=event.speaker,
            timestamp=event.timestamp,
            history=self.history,
        )

        # 2. Check for Topic Shift / Intent (Semantic / State-based)
        if event.is_final:
            detected_topic = self._detect_topic(text)
            if detected_topic and detected_topic != self._last_topic:
                shift_signal = Signal(
                    signal_id=f"sig_topic_{int(event.timestamp*1000)}",
                    type=SignalType.TOPIC_SHIFT,
                    timestamp=event.timestamp,
                    confidence=0.82,
                    speaker=event.speaker,
                    evidence_text=f"Shifted from {self._last_topic} to {detected_topic}",
                    severity="low",
                    source="semantic",
                    metadata={"previous_topic": self._last_topic, "new_topic": detected_topic},
                )
                signals.append(shift_signal)
                self._last_topic = detected_topic

            # Append to rolling context window
            self.history.append({
                "chunk_sequence": event.chunk_sequence,
                "timestamp": event.timestamp,
                "speaker": event.speaker.value,
                "text": text,
                "confidence": event.confidence,
            })
            if len(self.history) > self.max_context_turns:
                self.history.pop(0)

        return signals

    def _detect_topic(self, text: str) -> Optional[str]:
        t = text.lower()
        if any(w in t for w in ["hello", "good morning", "magandang araw", "selamat siang", "kumusta"]):
            return "greeting"
        if any(w in t for w in ["annual revenue", "credit score", "years in business", "income", "pendapatan", "omzet"]):
            return "qualification"
        if any(w in t for w in ["interest rate", "premium", "down payment", "cicilan", "biaya", "pricing", "quote"]):
            return "pricing"
        if any(w in t for w in ["too expensive", "not interested", "mahina", "berat", "ragu", "scam", "mahal"]):
            return "objection"
        if any(w in t for w in ["pay", "card", "transfer", "bank", "bayar", "rekening"]):
            return "payment"
        if any(w in t for w in ["bye", "thank you", "salamat", "terima kasih", "talk later"]):
            return "closing"
        return None
