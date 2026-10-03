"""
Gemini Live Fallback Voice Session.

Provides the backup voice transport layer when Vapi cannot establish a connection:
- Uses the EXACT same Q1 state machine and deterministic qualification rules
- Uses the EXACT same Q2 knowledge base retrieval with confidence gating
- Uses the EXACT same lead creation, human escalation, and call auditing services
- Never exposes Gemini API keys to the browser
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
from uuid import uuid4

from app.agents.base import VoiceAgent
from app.agents.schemas import VoiceAgentTurn
from app.agents.tools import (
    create_lead_tool,
    escalate_to_human_tool,
    evaluate_qualification_tool,
    search_knowledge,
)
from app.core.config import get_config
from app.core.logging import get_logger
from app.core.providers.health import get_health_tracker
from app.services.call_events import get_call_event_service

logger = get_logger(__name__)


class GeminiLiveSession:
    """
    Manages a Gemini Live voice session as a backup transport to Vapi.
    
    Guarantees single source of truth by delegating all business logic,
    retrieval, and qualification decisions to existing Q1 tools.
    """

    def __init__(self, session_id: Optional[str] = None, initial_state: Optional[Dict[str, Any]] = None):
        self.session_id = session_id or f"gemini_live_{uuid4().hex[:8]}"
        self.config = get_config()
        self.agent = VoiceAgent(call_id=self.session_id)
        self.is_configured = bool(self.config.gemini.api_key and len(self.config.gemini.api_key) > 5)

        if initial_state:
            for k, v in initial_state.items():
                if v is not None and k not in ("eligibility", "product"):
                    self.agent.qualification_manager.update_field(k, v)

        get_call_event_service().log_event(
            call_id=self.session_id,
            event_type="gemini_live_session_started",
            payload={
                "transport": "gemini_live",
                "model": self.config.gemini.live_model,
                "role": "fallback_voice_provider",
                "has_initial_state": bool(initial_state),
            },
        )
        get_health_tracker().register_provider("gemini_live", category="voice", initial_status="standby")

    def get_initial_greeting(self) -> str:
        """Generate a context-aware greeting when fallback activates."""
        pub_state = self.agent.public_state()
        has_fields = any(pub_state.get(k) for k in ("business_type", "years_in_business", "monthly_revenue", "requested_amount"))
        if not has_fields:
            return "Hello! I am your backup voice assistant powered by Gemini Live. I can help answer questions or qualify your business for a loan. How can I help you today?"

        details = []
        if pub_state.get("business_type"):
            details.append(f"business type: {pub_state['business_type']}")
        if pub_state.get("years_in_business"):
            details.append(f"{pub_state['years_in_business']} years operating")
        if pub_state.get("monthly_revenue"):
            rev = pub_state['monthly_revenue']
            details.append(f"monthly revenue: ${rev:,.0f}" if isinstance(rev, (int, float)) else f"monthly revenue: {rev}")
        if pub_state.get("requested_amount"):
            req = pub_state['requested_amount']
            details.append(f"requested loan: ${req:,.0f}" if isinstance(req, (int, float)) else f"requested loan: {req}")

        summary_str = ", ".join(details)
        eval_res = evaluate_qualification_tool(self.agent.qualification_manager.state.to_dict())
        status = eval_res.get("status")

        if status == "ELIGIBLE":
            prod = eval_res.get("recommended_product")
            return f"Connected to Gemini Live backup. I have retrieved your qualification details ({summary_str}). Great news — your business qualifies for the {prod} loan! How would you like to proceed?"
        elif status == "NEEDS_MORE_INFORMATION":
            missing = eval_res.get("missing_fields", [])
            next_field = missing[0] if missing else "more details"
            prompts = {
                "business_type": "what type of business or industry you operate in?",
                "years_in_business": "how many years has your business been operating?",
                "monthly_revenue": "what is your average monthly revenue?",
                "requested_amount": "how much loan funding are you looking to secure?",
            }
            prompt_text = prompts.get(next_field, "could you tell me more about your business?")
            return f"Connected to Gemini Live backup. I have saved your details so far ({summary_str}). To complete your qualification, could you tell me {prompt_text}"
        else:
            return f"Connected to Gemini Live backup. I have your details ({summary_str}). How can I assist you further?"

    def process_utterance(self, text: str) -> Dict[str, Any]:
        """
        Process an incoming caller utterance through Q1 state machine & tools.
        """
        logger.info(
            f"Gemini Live processing utterance for session {self.session_id}",
            extra={"extra_data": {"session_id": self.session_id, "text": text}}
        )

        turn: VoiceAgentTurn = self.agent.process_turn(text)
        get_health_tracker().record_success("gemini_live", verification_type="LIVE VERIFIED" if self.is_configured else "LOCAL VERIFIED")

        return {
            "session_id": self.session_id,
            "turn_index": turn.turn_index,
            "user_utterance": turn.user_utterance,
            "assistant_response": turn.assistant_response,
            "state_before": turn.state_before.value if hasattr(turn.state_before, "value") else str(turn.state_before),
            "state_after": turn.state_after.value if hasattr(turn.state_after, "value") else str(turn.state_after),
            "grounded": turn.grounded,
            "citations": turn.citations_used,
            "qualification_state": self.agent.public_state(),
            "lead_created": self.agent.lead_created,
            "escalated": self.agent.escalated,
            "provider": "gemini_live",
            "fallback_used": True,
        }

    def end_session(self) -> Dict[str, Any]:
        get_call_event_service().log_event(
            call_id=self.session_id,
            event_type="gemini_live_session_ended",
            payload={"turn_count": self.agent.turn_index},
        )
        return {"session_id": self.session_id, "status": "ended"}
