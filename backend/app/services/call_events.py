"""
Q1 Voice Agent — Call Event Logging Service.

Captures structured, audit-ready call events:
call_started, user_message, assistant_message, kb_search, kb_result,
qualification_update, qualification_evaluation, lead_created,
escalation_requested, call_ended, error.

Raw sensitive customer data is sanitized before recording.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


def _sanitize_data(data: Any) -> Any:
    """Mask emails and phone numbers in logged event payloads."""
    if isinstance(data, dict):
        return {k: _sanitize_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_data(x) for x in data]
    if isinstance(data, str):
        # Mask email
        s = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[EMAIL_PROTECTED]", data)
        # Mask phone numbers
        s = re.sub(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "[PHONE_PROTECTED]", s)
        return s
    return data


class CallEvent(BaseModel):
    """A single structured call event."""
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:8]}")
    call_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


class CallEventService:
    """In-memory call event registry with query by call_id."""

    def __init__(self):
        self._events: list[CallEvent] = []
        self._by_call: dict[str, list[CallEvent]] = {}

    def log_event(
        self,
        call_id: str,
        event_type: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> CallEvent:
        """Sanitize and record a call event."""
        clean_payload = _sanitize_data(payload or {})

        event = CallEvent(
            call_id=call_id,
            event_type=event_type,
            payload=clean_payload,
        )
        self._events.append(event)
        if call_id not in self._by_call:
            self._by_call[call_id] = []
        self._by_call[call_id].append(event)

        logger.info(
            f"Call event: {event_type}",
            extra={"extra_data": {"call_id": call_id, "event_type": event_type}},
        )
        return event

    def get_call_events(self, call_id: str) -> list[CallEvent]:
        """Get all events for a given call in chronological order."""
        return self._by_call.get(call_id, [])

    def get_all_events(self) -> list[CallEvent]:
        return self._events

    def clear(self) -> None:
        self._events.clear()
        self._by_call.clear()


_call_event_service = CallEventService()


def get_call_event_service() -> CallEventService:
    return _call_event_service
