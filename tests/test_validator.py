"""Tests for the validator: completeness + confidence -> status + reasons."""
from shared.models import FailureCategory, ProcessingStatus
from validation.validator import validate


def _complete(**overrides):
    fields = {
        "employeeName": "Jamie Smith",
        "employerName": "Acme",
        "grossPay": 3250.0,
        "confidenceScore": 94,
    }
    fields.update(overrides)
    return fields


def test_complete_and_confident_is_processed():
    outcome = validate(_complete())
    assert outcome.status is ProcessingStatus.PROCESSED
    assert outcome.requires_human_review is False
    assert outcome.reasons == []


def test_missing_employer_needs_review():
    outcome = validate(_complete(employerName=None))
    assert outcome.status is ProcessingStatus.NEEDS_REVIEW
    assert outcome.requires_human_review is True
    assert any("Employer name missing" in r for r in outcome.reasons)
    assert FailureCategory.MISSING_REQUIRED_FIELD in outcome.categories


def test_low_confidence_needs_review():
    outcome = validate(_complete(confidenceScore=78))
    assert outcome.status is ProcessingStatus.NEEDS_REVIEW
    assert FailureCategory.LOW_CONFIDENCE in outcome.categories


def test_missing_confidence_needs_review():
    outcome = validate(_complete(confidenceScore=None))
    assert outcome.status is ProcessingStatus.NEEDS_REVIEW
    assert FailureCategory.LOW_CONFIDENCE in outcome.categories
