"""
Q1 Voice Agent — Call Event Logging Tests.

Tests:
1. Recording structured call events
2. PII sanitization (phone and email masked)
3. Event retrieval by call_id
"""

from __future__ import annotations

import pytest

from app.services.call_events import get_call_event_service


class TestCallEvents:
    @pytest.fixture(autouse=True)
    def clean_events(self):
        service = get_call_event_service()
        service.clear()
        return service

    def test_log_event_and_retrieve(self, clean_events):
        service = clean_events
        evt = service.log_event(
            call_id="call_evt_1",
            event_type="call_started",
            payload={"source": "browser"},
        )
        assert evt.call_id == "call_evt_1"
        assert evt.event_type == "call_started"

        events = service.get_call_events("call_evt_1")
        assert len(events) == 1
        assert events[0].event_id == evt.event_id

    def test_pii_sanitization_in_events(self, clean_events):
        service = clean_events
        service.log_event(
            call_id="call_pii_1",
            event_type="user_message",
            payload={
                "email": "customer@example.com",
                "phone": "+1 (555) 123-4567",
                "note": "Contact me at admin@corp.org or 555-888-9999",
            },
        )

        events = service.get_call_events("call_pii_1")
        payload = events[0].payload
        assert "[EMAIL_PROTECTED]" in payload["email"]
        assert "[PHONE_PROTECTED]" in payload["phone"]
        assert "customer@example.com" not in str(payload)
        assert "555-888-9999" not in str(payload)
