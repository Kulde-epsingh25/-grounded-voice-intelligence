"""
Q1 Voice Agent — Conversation State Machine.

Maintains explicit conversation states:
GREETING -> UNDERSTAND_INTENT -> QUALIFICATION -> REVIEW -> LEAD_CONFIRMATION -> END
Interruptible by:
- KNOWLEDGE_QUESTION (answers grounded from Q2 then resumes)
- OBJECTION (answers grounded from Q2 then resumes)
- ESCALATION (transfers to human on request, conflict, or low confidence)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.agents.schemas import ConversationState
from app.core.logging import get_logger

logger = get_logger(__name__)


# Valid state transitions
_VALID_TRANSITIONS: dict[ConversationState, set[ConversationState]] = {
    ConversationState.GREETING: {
        ConversationState.UNDERSTAND_INTENT,
        ConversationState.QUALIFICATION,
        ConversationState.KNOWLEDGE_QUESTION,
        ConversationState.OBJECTION,
        ConversationState.ESCALATION,
        ConversationState.END,
    },
    ConversationState.UNDERSTAND_INTENT: {
        ConversationState.QUALIFICATION,
        ConversationState.KNOWLEDGE_QUESTION,
        ConversationState.OBJECTION,
        ConversationState.ESCALATION,
        ConversationState.END,
    },
    ConversationState.QUALIFICATION: {
        ConversationState.KNOWLEDGE_QUESTION,
        ConversationState.OBJECTION,
        ConversationState.REVIEW,
        ConversationState.ESCALATION,
        ConversationState.END,
    },
    ConversationState.KNOWLEDGE_QUESTION: {
        ConversationState.QUALIFICATION,
        ConversationState.OBJECTION,
        ConversationState.REVIEW,
        ConversationState.ESCALATION,
        ConversationState.END,
    },
    ConversationState.OBJECTION: {
        ConversationState.QUALIFICATION,
        ConversationState.KNOWLEDGE_QUESTION,
        ConversationState.REVIEW,
        ConversationState.ESCALATION,
        ConversationState.END,
    },
    ConversationState.REVIEW: {
        ConversationState.LEAD_CONFIRMATION,
        ConversationState.QUALIFICATION,
        ConversationState.ESCALATION,
        ConversationState.END,
    },
    ConversationState.LEAD_CONFIRMATION: {
        ConversationState.END,
        ConversationState.ESCALATION,
    },
    ConversationState.ESCALATION: {
        ConversationState.END,
    },
    ConversationState.END: set(),
}


class ConversationStateMachine:
    """Manages explicit conversation state and history."""

    def __init__(self, initial_state: ConversationState = ConversationState.GREETING):
        self.current_state = initial_state
        self.previous_qualification_state: Optional[ConversationState] = None
        self.history: list[tuple[ConversationState, ConversationState, str, str]] = []

    def can_transition(self, to_state: ConversationState) -> bool:
        """Check if transition from current state to target state is permissible."""
        allowed = _VALID_TRANSITIONS.get(self.current_state, set())
        return to_state in allowed

    def transition(self, to_state: ConversationState, reason: str = "") -> ConversationState:
        """Perform transition and record history."""
        if not self.can_transition(to_state):
            logger.warning(
                "Invalid state transition attempted",
                extra={
                    "extra_data": {
                        "from": self.current_state.value,
                        "to": to_state.value,
                        "reason": reason,
                    }
                },
            )
            # Safe recovery: if stuck or ending, allow transition to END or ESCALATION
            if to_state in (ConversationState.END, ConversationState.ESCALATION):
                pass
            else:
                return self.current_state

        from_state = self.current_state
        if from_state == ConversationState.QUALIFICATION and to_state in (
            ConversationState.KNOWLEDGE_QUESTION,
            ConversationState.OBJECTION,
        ):
            self.previous_qualification_state = from_state

        self.current_state = to_state
        now_iso = datetime.now(timezone.utc).isoformat()
        self.history.append((from_state, to_state, reason, now_iso))

        logger.info(
            "State transition",
            extra={
                "extra_data": {
                    "from": from_state.value,
                    "to": to_state.value,
                    "reason": reason,
                }
            },
        )
        return self.current_state

    def resume_qualification_if_interrupted(self) -> ConversationState:
        """Resume qualification state after a knowledge or objection detour."""
        if self.current_state in (
            ConversationState.KNOWLEDGE_QUESTION,
            ConversationState.OBJECTION,
        ):
            return self.transition(ConversationState.QUALIFICATION, reason="Resuming qualification flow")
        return self.current_state
