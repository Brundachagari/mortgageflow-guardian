"""Decide whether normalized data is trustworthy -- and explain the decision.

The output is deliberately rich: not just "good/bad", but a status, a
human-review flag, a list of plain-English reasons, and machine-readable failure
categories. The reasons are what a human reviewer reads; the categories are what
CloudWatch metrics count later.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from shared.models import FailureCategory, ProcessingStatus
from validation.schema import AUTO_ACCEPT_THRESHOLD, FIELD_LABELS, REQUIRED_FIELDS


@dataclass
class ValidationOutcome:
    status: ProcessingStatus
    requires_human_review: bool
    reasons: list[str] = field(default_factory=list)
    categories: list[FailureCategory] = field(default_factory=list)


def validate(fields: dict) -> ValidationOutcome:
    """Check completeness and confidence; return a fully-explained outcome."""
    reasons: list[str] = []
    categories: list[FailureCategory] = []

    # 1) Completeness -- every required field must be present.
    for name in REQUIRED_FIELDS:
        if fields.get(name) in (None, ""):
            label = FIELD_LABELS.get(name, name)
            reasons.append(f"{label} missing")
            categories.append(FailureCategory.MISSING_REQUIRED_FIELD)

    # 2) Confidence -- is the provider sure enough for us to trust it unattended?
    confidence = fields.get("confidenceScore")
    if confidence is None:
        reasons.append("No confidence score returned by provider")
        categories.append(FailureCategory.LOW_CONFIDENCE)
    elif confidence < AUTO_ACCEPT_THRESHOLD:
        reasons.append(
            f"Confidence {confidence} below auto-accept threshold "
            f"{AUTO_ACCEPT_THRESHOLD}"
        )
        categories.append(FailureCategory.LOW_CONFIDENCE)

    # Any reason at all means a human should look before this data is trusted.
    if reasons:
        return ValidationOutcome(
            status=ProcessingStatus.NEEDS_REVIEW,
            requires_human_review=True,
            reasons=reasons,
            categories=categories,
        )

    return ValidationOutcome(
        status=ProcessingStatus.PROCESSED,
        requires_human_review=False,
    )
