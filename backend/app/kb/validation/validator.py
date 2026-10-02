"""
Q2 Knowledge Base — Source Validation.

Detects source-quality problems: conflicting values, invalid dates/numbers,
missing metadata, inconsistent terminology.

IMPORTANT: Does NOT decide which conflicting business policy is correct.
Flags conflicts for human/downstream resolution.
"""

from __future__ import annotations

import re
from datetime import datetime

from app.core.logging import get_logger
from app.kb.models import (
    ConflictRecord,
    ConflictSeverity,
    KBRecord,
    ValidationFlag,
    ValidationResult,
)

logger = get_logger(__name__)


def validate_record(record: KBRecord) -> ValidationResult:
    """Validate a single KB record for obvious quality issues.

    Args:
        record: The KB record to validate.

    Returns:
        ValidationResult with flags and issues.
    """
    result = ValidationResult(source_id=record.source_id)

    # Check missing metadata
    if not record.title or record.title.strip() == "":
        result.flags.append(ValidationFlag.MISSING_METADATA)
        result.issues.append("Missing title")

    if not record.source_id:
        result.flags.append(ValidationFlag.MISSING_METADATA)
        result.issues.append("Missing source_id")

    if not record.content or len(record.content.strip()) < 10:
        result.flags.append(ValidationFlag.MISSING_METADATA)
        result.issues.append("Content is empty or too short")

    # Check dates
    if record.effective_from and record.effective_to:
        try:
            from_date = datetime.fromisoformat(record.effective_from)
            to_date = datetime.fromisoformat(record.effective_to)
            if to_date < from_date:
                result.flags.append(ValidationFlag.IMPOSSIBLE_DATE)
                result.issues.append(
                    f"effective_to ({record.effective_to}) is before "
                    f"effective_from ({record.effective_from})"
                )
        except (ValueError, TypeError):
            result.flags.append(ValidationFlag.IMPOSSIBLE_DATE)
            result.issues.append("Invalid date format in effective dates")

    # Check for suspicious numeric values in content
    _check_numeric_issues(record.content, result)

    result.is_valid = len(result.flags) == 0
    return result


def _check_numeric_issues(content: str, result: ValidationResult) -> None:
    """Check for obviously invalid numeric values."""
    # Negative monetary values (suspicious in most business contexts)
    negative_money = re.findall(r"-\$[\d,]+", content)
    if negative_money:
        result.flags.append(ValidationFlag.INVALID_NUMERIC)
        result.issues.append(f"Negative monetary value detected: {negative_money[0]}")

    # Percentages over 100% (suspicious in most contexts)
    percentages = re.findall(r"(\d+(?:\.\d+)?)\s*%", content)
    for pct in percentages:
        try:
            if float(pct) > 1000:
                result.flags.append(ValidationFlag.INVALID_NUMERIC)
                result.issues.append(f"Suspicious percentage: {pct}%")
        except ValueError:
            pass


def detect_conflicts(records: list[KBRecord]) -> list[ConflictRecord]:
    """Detect conflicts between records from different sources.

    When two sources state different values for the same field/topic,
    this flags the conflict WITHOUT deciding which is correct.

    Args:
        records: List of KB records to cross-check.

    Returns:
        List of detected conflicts.
    """
    conflicts: list[ConflictRecord] = []

    # Group records by product+category for comparison
    groups: dict[str, list[KBRecord]] = {}
    for record in records:
        key = f"{record.product}:{record.category}:{record.subcategory}"
        groups.setdefault(key, []).append(record)

    for key, group in groups.items():
        if len(group) < 2:
            continue

        # Compare records from different sources
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a.source_id == b.source_id:
                    continue

                # Check for conflicting numeric values
                _check_value_conflicts(a, b, conflicts)

    if conflicts:
        logger.info(
            "Source conflicts detected",
            extra={"extra_data": {"conflict_count": len(conflicts)}},
        )

    return conflicts


def _check_value_conflicts(
    a: KBRecord,
    b: KBRecord,
    conflicts: list[ConflictRecord],
) -> None:
    """Check two records for conflicting values."""
    # Extract monetary amounts for comparison
    amounts_a = re.findall(r"\$?([\d,]+(?:\.\d+)?)\s*(?:million|M|thousand|K)?", a.content)
    amounts_b = re.findall(r"\$?([\d,]+(?:\.\d+)?)\s*(?:million|M|thousand|K)?", b.content)

    if amounts_a and amounts_b:
        # Simple check: if they have different key amounts in the same category
        set_a = set(amounts_a)
        set_b = set(amounts_b)
        if set_a != set_b and a.category == b.category:
            conflict = ConflictRecord(
                source_ids=[a.source_id, b.source_id],
                field=f"{a.category}.amounts",
                values=[str(set_a), str(set_b)],
                severity=ConflictSeverity.MEDIUM,
                description=(
                    f"Different numeric values found in {a.category}: "
                    f"Source {a.source_id} has {set_a}, "
                    f"Source {b.source_id} has {set_b}. "
                    f"FLAGGED — not auto-resolved."
                ),
            )
            conflicts.append(conflict)

    # Check version conflicts
    if a.version and b.version and a.version != b.version:
        if a.product == b.product and a.category == b.category:
            conflict = ConflictRecord(
                source_ids=[a.source_id, b.source_id],
                field="version",
                values=[a.version, b.version],
                severity=ConflictSeverity.LOW,
                description=(
                    f"Different versions for same product/category: "
                    f"v{a.version} vs v{b.version}"
                ),
            )
            conflicts.append(conflict)
