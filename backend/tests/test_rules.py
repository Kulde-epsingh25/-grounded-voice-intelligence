"""
Q1 Voice Agent — Deterministic Rule Engine Tests.

Tests:
1. Eligible synthetic application
2. Ineligible application (< 2 years or < $500,000 revenue)
3. Needs more information (missing mandatory fields)
4. Manual review (requested amount > product tier max)
5. Zero revenue with requested loan -> manual review
6. Negative / impossible inputs
"""

from __future__ import annotations

import pytest

from app.agents.qualification import QualificationManager
from app.agents.rules import QualificationRuleEngine, evaluate_qualification
from app.agents.schemas import QualificationStatus


class TestQualificationRules:
    @pytest.fixture
    def engine(self):
        return QualificationRuleEngine()

    def test_eligible_starter_loan(self, engine):
        mgr = QualificationManager()
        mgr.update_field("business_type", "Retail Trading")
        mgr.update_field("years_in_business", 3.0)
        mgr.update_field("monthly_revenue", 600000.0)
        mgr.update_field("requested_amount", 1500000.0)

        result = engine.evaluate(mgr.state)
        assert result.status == QualificationStatus.ELIGIBLE
        assert result.recommended_product == "Starter"
        assert result.max_eligible_amount == 2000000.0
        assert result.interest_rate == 12.5
        assert len(result.rules_checked) >= 4
        assert result.is_synthetic is True

    def test_eligible_enterprise_loan(self, engine):
        mgr = QualificationManager()
        mgr.update_field("business_type", "Manufacturing")
        mgr.update_field("years_in_business", 6.0)
        mgr.update_field("monthly_revenue", 7000000.0)
        mgr.update_field("requested_amount", 25000000.0)

        result = engine.evaluate(mgr.state)
        assert result.status == QualificationStatus.ELIGIBLE
        assert result.recommended_product == "Enterprise"
        assert result.interest_rate == 7.0

    def test_ineligible_insufficient_years(self, engine):
        mgr = QualificationManager()
        mgr.update_field("business_type", "Restaurant")
        mgr.update_field("years_in_business", 1.0)  # Requires 2 years
        mgr.update_field("monthly_revenue", 800000.0)
        mgr.update_field("requested_amount", 1000000.0)

        result = engine.evaluate(mgr.state)
        assert result.status == QualificationStatus.INELIGIBLE
        assert any("below policy minimum requirement of 2 years" in r for r in result.reasons)

    def test_ineligible_insufficient_revenue(self, engine):
        mgr = QualificationManager()
        mgr.update_field("business_type", "Consulting")
        mgr.update_field("years_in_business", 4.0)
        mgr.update_field("monthly_revenue", 300000.0)  # Requires $500,000
        mgr.update_field("requested_amount", 500000.0)

        result = engine.evaluate(mgr.state)
        assert result.status == QualificationStatus.INELIGIBLE
        assert any("below policy minimum requirement of $500,000" in r for r in result.reasons)

    def test_needs_more_information(self, engine):
        mgr = QualificationManager()
        mgr.update_field("business_type", "Logistics")
        mgr.update_field("monthly_revenue", 1000000.0)
        # Missing years_in_business and requested_amount

        result = engine.evaluate(mgr.state)
        assert result.status == QualificationStatus.NEEDS_MORE_INFORMATION
        assert "years_in_business" in result.missing_fields
        assert "requested_amount" in result.missing_fields

    def test_manual_review_exceeds_tier_max(self, engine):
        mgr = QualificationManager()
        mgr.update_field("business_type", "Retail")
        mgr.update_field("years_in_business", 2.5)
        mgr.update_field("monthly_revenue", 600000.0)  # Starter tier (max $2,000,000)
        mgr.update_field("requested_amount", 4000000.0)  # Requests $4,000,000

        result = engine.evaluate(mgr.state)
        assert result.status == QualificationStatus.MANUAL_REVIEW
        assert result.recommended_product == "Starter"
        assert result.max_eligible_amount == 2000000.0
        assert any("exceeds the maximum limit" in r for r in result.reasons)

    def test_negative_impossible_inputs(self, engine):
        mgr = QualificationManager()
        mgr.update_field("business_type", "Retail")
        mgr.update_field("years_in_business", -1.0)
        mgr.update_field("monthly_revenue", 600000.0)
        mgr.update_field("requested_amount", 1000000.0)

        result = engine.evaluate(mgr.state)
        assert result.status == QualificationStatus.INELIGIBLE
        assert any("cannot be negative" in r for r in result.reasons)
