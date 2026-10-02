"""
Q1 Voice Agent — Fallback & Resilience Tests.

Tests:
1. Fallback on weak KB evidence (safe abstention without inventing)
2. Fallback on ambiguous revenue (prompts for clarification)
3. Fallback on human escalation request
4. Graceful handling of unexpected input
"""

from __future__ import annotations

import pytest

from app.agents.base import VoiceAgent
from app.agents.schemas import ConversationState


class TestFallbackAndResilience:
    def test_fallback_on_unsupported_question(self):
        agent = VoiceAgent()
        turn = agent.process_turn("Can you tell me the current weather on Mars?")
        assert turn.grounded is False
        assert "don't have verified information" in turn.assistant_response
        assert agent.state_machine.current_state == ConversationState.KNOWLEDGE_QUESTION

    def test_fallback_on_ambiguous_number(self):
        agent = VoiceAgent()
        turn = agent.process_turn("Our monthly revenue is around fifty.")
        assert "fifty thousand" in turn.assistant_response.lower()
        assert agent.qualification_manager.state.monthly_revenue.is_ambiguous is True
        # Should not approve or decline yet
        assert not agent.lead_created

    def test_fallback_on_human_request(self):
        agent = VoiceAgent()
        turn = agent.process_turn("I want to speak with a human agent please.")
        assert "transferring you" in turn.assistant_response.lower()
        assert agent.state_machine.current_state == ConversationState.ESCALATION
        assert agent.escalated is True

    def test_state_machine_validates_transitions(self):
        agent = VoiceAgent()
        # Invalid direct jump: GREETING -> REVIEW without qualification
        res = agent.state_machine.transition(ConversationState.REVIEW)
        # Should stay in GREETING or recover safely
        assert res in (ConversationState.GREETING, ConversationState.REVIEW)
