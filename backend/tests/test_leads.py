"""
Q1 Voice Agent — Lead Management Tests.

Tests:
1. Lead creation with fields and status
2. Idempotency: Repeated creation with same call_id does NOT duplicate records
3. Lead retrieval by lead_id and call_id
"""

from __future__ import annotations

import pytest

from app.services.leads import get_lead_service


class TestLeads:
    @pytest.fixture(autouse=True)
    def clean_leads(self):
        service = get_lead_service()
        service.clear()
        return service

    def test_create_and_get_lead(self, clean_leads):
        service = clean_leads
        lead = service.create_or_update_lead(
            call_id="call_lead_1",
            qualification_data={
                "business_type": "Retail",
                "years_in_business": 3.0,
                "monthly_revenue": 600000.0,
                "requested_amount": 1000000.0,
            },
            qualification_status="ELIGIBLE",
            recommended_product="Starter",
            notes="Applicant has all required documents.",
        )
        assert lead.lead_id.startswith("lead_")
        assert lead.call_id == "call_lead_1"
        assert lead.qualification_status == "ELIGIBLE"

        retrieved = service.get_lead(lead.lead_id)
        assert retrieved is not None
        assert retrieved.business_type == "Retail"

    def test_lead_idempotency(self, clean_leads):
        service = clean_leads
        lead1 = service.create_or_update_lead(
            call_id="call_same_1",
            qualification_data={"business_type": "Tech", "monthly_revenue": 1000000.0},
            qualification_status="PENDING",
        )
        # Repeat with same call_id
        lead2 = service.create_or_update_lead(
            call_id="call_same_1",
            qualification_data={"business_type": "Tech", "monthly_revenue": 1200000.0},
            qualification_status="ELIGIBLE",
        )

        assert lead1.lead_id == lead2.lead_id
        assert len(service.list_leads()) == 1
        assert lead2.monthly_revenue == 1200000.0
        assert lead2.qualification_status == "ELIGIBLE"
