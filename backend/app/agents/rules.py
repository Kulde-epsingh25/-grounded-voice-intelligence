"""
Q1 Voice Agent — Deterministic Qualification Rule Engine.

Contains ZERO LLM reasoning:
- Factual policy rules loaded from configuration
- Strictly deterministic evaluation
- Comprehensive rule execution audit trail
- Clear categorization: ELIGIBLE, INELIGIBLE, NEEDS_MORE_INFORMATION, MANUAL_REVIEW
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.agents.schemas import (
    QualificationResult,
    QualificationState,
    QualificationStatus,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Default synthetic rules fallback if file is not found
_DEFAULT_RULES = {
    "products": {
        "Starter": {
            "min_monthly_revenue": 500000.0,
            "min_years_in_business": 2.0,
            "max_loan_amount": 2000000.0,
            "term_months": 12,
            "interest_rate": 12.5,
        },
        "Growth": {
            "min_monthly_revenue": 1000000.0,
            "min_years_in_business": 2.0,
            "max_loan_amount": 5000000.0,
            "term_months": 24,
            "interest_rate": 10.0,
        },
        "Premium": {
            "min_monthly_revenue": 2500000.0,
            "min_years_in_business": 3.0,
            "max_loan_amount": 15000000.0,
            "term_months": 60,
            "interest_rate": 8.5,
        },
        "Enterprise": {
            "min_monthly_revenue": 5000000.0,
            "min_years_in_business": 5.0,
            "max_loan_amount": 50000000.0,
            "term_months": 84,
            "interest_rate": 7.0,
        },
    },
    "mandatory_qualification_fields": [
        "business_type",
        "years_in_business",
        "monthly_revenue",
        "requested_amount",
    ],
    "policy_thresholds": {
        "min_years_in_business_absolute": 2.0,
        "min_monthly_revenue_absolute": 500000.0,
    },
}


def load_rules_config(filepath: Optional[Path | str] = None) -> dict[str, Any]:
    """Load business rules configuration."""
    path = Path(filepath or "data/eval/demo_business_rules.json")
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not read rules file, using fallback", extra={"extra_data": {"error": str(e)}})
    return _DEFAULT_RULES


class QualificationRuleEngine:
    """Deterministic business loan eligibility evaluator."""

    def __init__(self, rules_config: Optional[dict[str, Any]] = None):
        self.rules = rules_config or load_rules_config()
        self.products = self.rules.get("products", _DEFAULT_RULES["products"])
        self.mandatory_fields = self.rules.get(
            "mandatory_qualification_fields",
            _DEFAULT_RULES["mandatory_qualification_fields"],
        )
        self.thresholds = self.rules.get(
            "policy_thresholds",
            _DEFAULT_RULES["policy_thresholds"],
        )

    def evaluate(self, state: QualificationState) -> QualificationResult:
        """Evaluate application against deterministic business rules."""
        rules_checked: list[str] = []
        reasons: list[str] = []

        # 1. Check mandatory fields
        rules_checked.append("RULE_01_MANDATORY_FIELDS_CHECK")
        missing: list[str] = []
        for field_name in self.mandatory_fields:
            val = state.get_field_value(field_name)
            if val is None or val == "":
                missing.append(field_name)
            elif getattr(state, field_name).is_ambiguous:
                # Ambiguous values need clarification, cannot proceed
                missing.append(field_name)

        if missing:
            return QualificationResult(
                status=QualificationStatus.NEEDS_MORE_INFORMATION,
                rules_checked=rules_checked,
                missing_fields=missing,
                reasons=[f"Missing or unconfirmed required qualification fields: {', '.join(missing)}"],
                is_synthetic=True,
            )

        # 2. Extract and cast numeric inputs
        rules_checked.append("RULE_02_NUMERIC_SANITY_CHECK")
        try:
            years = float(state.get_field_value("years_in_business"))
            revenue = float(state.get_field_value("monthly_revenue"))
            requested = float(state.get_field_value("requested_amount"))
        except (ValueError, TypeError) as e:
            return QualificationResult(
                status=QualificationStatus.MANUAL_REVIEW,
                rules_checked=rules_checked,
                reasons=[f"Non-numeric or corrupted financial values: {str(e)}"],
                is_synthetic=True,
            )

        # 3. Sanity and impossible value validation
        if years < 0 or revenue < 0 or requested < 0:
            return QualificationResult(
                status=QualificationStatus.INELIGIBLE,
                rules_checked=rules_checked,
                reasons=["Financial values and operational years cannot be negative."],
                is_synthetic=True,
            )

        # Conflicting / suspicious values
        if revenue == 0 and requested > 0:
            return QualificationResult(
                status=QualificationStatus.MANUAL_REVIEW,
                rules_checked=rules_checked,
                reasons=["Zero monthly revenue with requested loan amount requires manual review."],
                is_synthetic=True,
            )

        # 4. Absolute minimum thresholds
        rules_checked.append("RULE_03_ABSOLUTE_MINIMUM_THRESHOLDS")
        min_years = self.thresholds.get("min_years_in_business_absolute", 2.0)
        min_revenue = self.thresholds.get("min_monthly_revenue_absolute", 500000.0)

        if years < min_years:
            reasons.append(
                f"Years in business ({years:.1f} yrs) is below policy minimum requirement of {min_years:.0f} years."
            )
        if revenue < min_revenue:
            reasons.append(
                f"Monthly revenue (${revenue:,.0f}) is below policy minimum requirement of ${min_revenue:,.0f}."
            )

        if reasons:
            return QualificationResult(
                status=QualificationStatus.INELIGIBLE,
                rules_checked=rules_checked,
                reasons=reasons,
                is_synthetic=True,
            )

        # 5. Product Tier Matching
        rules_checked.append("RULE_04_PRODUCT_TIER_SELECTION")
        # Evaluate highest qualified tier descending
        sorted_tiers = sorted(
            self.products.items(),
            key=lambda x: x[1]["min_monthly_revenue"],
            reverse=True,
        )

        matched_tier_name = None
        matched_tier_config = None

        for tier_name, config in sorted_tiers:
            if revenue >= config["min_monthly_revenue"] and years >= config["min_years_in_business"]:
                matched_tier_name = tier_name
                matched_tier_config = config
                break

        if not matched_tier_name or not matched_tier_config:
            return QualificationResult(
                status=QualificationStatus.INELIGIBLE,
                rules_checked=rules_checked,
                reasons=["Applicant profile does not qualify for any standard loan product tier."],
                is_synthetic=True,
            )

        # 6. Check requested amount against tier maximum
        rules_checked.append("RULE_05_MAX_AMOUNT_VALIDATION")
        max_allowed = matched_tier_config["max_loan_amount"]

        if requested > max_allowed:
            return QualificationResult(
                status=QualificationStatus.MANUAL_REVIEW,
                recommended_product=matched_tier_name,
                max_eligible_amount=max_allowed,
                interest_rate=matched_tier_config["interest_rate"],
                term_months=matched_tier_config["term_months"],
                rules_checked=rules_checked,
                reasons=[
                    f"Requested amount (${requested:,.0f}) exceeds the maximum limit for {matched_tier_name} tier "
                    f"(${max_allowed:,.0f}). Requires underwriter manual review or counter-offer."
                ],
                is_synthetic=True,
            )

        # Qualified!
        return QualificationResult(
            status=QualificationStatus.ELIGIBLE,
            recommended_product=matched_tier_name,
            max_eligible_amount=max_allowed,
            interest_rate=matched_tier_config["interest_rate"],
            term_months=matched_tier_config["term_months"],
            rules_checked=rules_checked,
            reasons=[
                f"Applicant meets all eligibility criteria for {matched_tier_name} loan tier.",
                f"Monthly revenue (${revenue:,.0f}) >= ${matched_tier_config['min_monthly_revenue']:,.0f}.",
                f"Years in business ({years:.1f}) >= {matched_tier_config['min_years_in_business']} years.",
                f"Requested amount (${requested:,.0f}) is within limit (${max_allowed:,.0f}).",
            ],
            is_synthetic=True,
        )


# Global helper instance
_engine = QualificationRuleEngine()


def evaluate_qualification(state: QualificationState) -> QualificationResult:
    """Evaluate application against deterministic business rules."""
    return _engine.evaluate(state)
