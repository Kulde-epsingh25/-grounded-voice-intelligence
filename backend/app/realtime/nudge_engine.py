"""
AI Engineer Assessment — Realtime Nudge Engine.

Evaluates signals against confidence gates, duplicate suppression, cooldown windows,
expiry deadlines, and priority hierarchies to produce short, actionable agent coaching cues.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from app.realtime.models import (
    Nudge,
    NudgePriority,
    NudgeStatus,
    Signal,
    SignalType,
)


class NudgeEngineConfig:
    """Configurable thresholds for the nudge decision pipeline."""

    def __init__(
        self,
        min_confidence: float = 0.70,
        high_confidence_threshold: float = 0.85,
        default_cooldown_seconds: float = 30.0,
        default_expiry_seconds: float = 45.0,
        compliance_cooldown_seconds: float = 15.0,
    ):
        self.min_confidence = min_confidence
        self.high_confidence_threshold = high_confidence_threshold
        self.default_cooldown_seconds = default_cooldown_seconds
        self.default_expiry_seconds = default_expiry_seconds
        self.compliance_cooldown_seconds = compliance_cooldown_seconds


class NudgeEngine:
    """
    Stateful engine that produces deduplicated, prioritized, actionable agent nudges.
    """

    def __init__(self, config: Optional[NudgeEngineConfig] = None):
        self.config = config or NudgeEngineConfig()
        # Track active nudges by nudge_id
        self._active_nudges: Dict[str, Nudge] = {}
        # Track last emission timestamp by (type, topic/rule) for cooldown
        self._last_emission_times: Dict[str, float] = {}
        # History for audit
        self._all_nudges: List[Nudge] = []
        self._suppressed_count = 0

    def reset(self) -> None:
        self._active_nudges.clear()
        self._last_emission_times.clear()
        self._all_nudges.clear()
        self._suppressed_count = 0

    def prune_expired(self, current_time: Optional[float] = None) -> List[Nudge]:
        """Expire nudges whose validity duration has elapsed."""
        now = current_time if current_time is not None else time.time()
        expired: List[Nudge] = []
        for nid, nudge in list(self._active_nudges.items()):
            if nudge.expires_at <= now:
                nudge.status = NudgeStatus.EXPIRED
                expired.append(nudge)
                del self._active_nudges[nid]
        return expired

    def process(self, signal: Signal, session_id: str, current_time: Optional[float] = None) -> Optional[Nudge]:
        """
        Evaluate a signal and decide whether to emit an active nudge or suppress it.
        """
        now = current_time if current_time is not None else signal.timestamp
        self.prune_expired(now)

        rule_key = signal.metadata.get("rule_name", signal.type.value)
        tracking_key = f"{signal.type.value}:{rule_key}"

        # 1. Confidence gate
        if signal.confidence < self.config.min_confidence:
            self._suppressed_count += 1
            suppressed_nudge = Nudge(
                nudge_id=f"nudge_{int(now*1000)}",
                session_id=session_id,
                type=signal.type,
                priority=NudgePriority.LOW,
                message="",
                confidence=signal.confidence,
                created_at=now,
                expires_at=now,
                cooldown_seconds=0.0,
                source_signal=signal.signal_id,
                evidence=signal.evidence_text,
                status=NudgeStatus.SUPPRESSED,
                suppression_reason=f"Confidence {signal.confidence:.2f} below threshold {self.config.min_confidence:.2f}",
            )
            self._all_nudges.append(suppressed_nudge)
            return None

        # 2. Duplicate suppression (active identical nudge exists)
        for active in self._active_nudges.values():
            if active.type == signal.type and active.status == NudgeStatus.ACTIVE:
                active_rule = active.evidence
                if signal.type == SignalType.COMPLIANCE_GAP or active.type == signal.type:
                    self._suppressed_count += 1
                    return None

        # 3. Cooldown check
        cooldown = (
            self.config.compliance_cooldown_seconds
            if signal.type == SignalType.COMPLIANCE_GAP
            else self.config.default_cooldown_seconds
        )
        last_emitted = self._last_emission_times.get(tracking_key)
        if last_emitted is not None and (now - last_emitted) < cooldown:
            self._suppressed_count += 1
            return None

        # 4. Priority and Message Generation
        priority, message = self._generate_nudge_content(signal)
        if not message:
            return None

        # 5. Create Active Nudge
        nudge_id = f"nudge_{signal.type.value}_{int(now*1000)}"
        expires_at = now + self.config.default_expiry_seconds

        nudge = Nudge(
            nudge_id=nudge_id,
            session_id=session_id,
            type=signal.type,
            priority=priority,
            message=message,
            confidence=signal.confidence,
            created_at=now,
            expires_at=expires_at,
            cooldown_seconds=cooldown,
            source_signal=signal.signal_id,
            evidence=signal.evidence_text,
            status=NudgeStatus.ACTIVE,
        )

        self._active_nudges[nudge_id] = nudge
        self._last_emission_times[tracking_key] = now
        self._all_nudges.append(nudge)
        return nudge

    def _generate_nudge_content(self, signal: Signal) -> Tuple[NudgePriority, str]:
        """
        Formulate short, actionable, agent-facing coaching prompts.
        """
        t = signal.type
        rule = signal.metadata.get("rule_name", "")

        if t == SignalType.COMPLIANCE_GAP:
            return (
                NudgePriority.HIGH,
                "Required disclosure appears missing. Deliver mandatory call recording disclosure before proceeding.",
            )

        if t == SignalType.MISSED_OPPORTUNITY:
            if "vehicle" in rule:
                return (
                    NudgePriority.LOW if signal.confidence < self.config.high_confidence_threshold else NudgePriority.MEDIUM,
                    "Customer mentioned a second vehicle. Check multi-vehicle offer.",
                )
            if "family" in rule:
                return (
                    NudgePriority.LOW,
                    "Customer mentioned family members. Inquire if dependent coverage add-on is desired.",
                )
            return (
                NudgePriority.LOW,
                "Customer referenced an additional business or property. Probe for cross-sell eligibility.",
            )

        if t == SignalType.CALLBACK_NEED:
            return (
                NudgePriority.MEDIUM,
                "Customer requested callback. Confirm preferred phone number and callback time.",
            )

        if t == SignalType.FRUSTRATION:
            return (
                NudgePriority.HIGH,
                "Customer expressed frustration over delays. Acknowledge concern and clarify the next step.",
            )

        if t == SignalType.RISK:
            return (
                NudgePriority.HIGH,
                "Customer signaled payment difficulty. Inquire about grace period or restructuring options.",
            )

        if t == SignalType.BUYING_SIGNAL:
            return (
                NudgePriority.MEDIUM,
                "Customer indicated intent to proceed. Present enrollment agreement or closing steps.",
            )

        if t == SignalType.TOPIC_SHIFT:
            new_top = signal.metadata.get("new_topic", "")
            return (
                NudgePriority.LOW,
                f"Customer shifted focus to {new_top}. Address questions before returning to qualification.",
            )

        return (NudgePriority.LOW, f"Review customer statement: {signal.evidence_text}")

    @property
    def active_nudges(self) -> List[Nudge]:
        return list(self._active_nudges.values())

    @property
    def suppressed_count(self) -> int:
        return self._suppressed_count
