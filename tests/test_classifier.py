"""Tests for the incident classifier: failure category -> action."""
from incidents.classifier import action_for, classify_exception, is_retryable
from shared.exceptions import (
    InvalidDocumentError,
    PermanentProviderError,
    TemporaryProviderError,
)
from shared.models import FailureCategory, HandlingAction


def test_temporary_error_is_retryable():
    assert is_retryable(FailureCategory.TEMPORARY_PROVIDER_ERROR) is True
    assert action_for(FailureCategory.TEMPORARY_PROVIDER_ERROR) is HandlingAction.RETRY


def test_permanent_errors_dead_letter():
    assert action_for(FailureCategory.PERMANENT_PROVIDER_ERROR) is HandlingAction.DEAD_LETTER
    assert action_for(FailureCategory.INVALID_DOCUMENT) is HandlingAction.DEAD_LETTER
    assert is_retryable(FailureCategory.INVALID_DOCUMENT) is False


def test_uncertain_results_go_to_human_review():
    assert action_for(FailureCategory.LOW_CONFIDENCE) is HandlingAction.HUMAN_REVIEW
    assert action_for(FailureCategory.MISSING_REQUIRED_FIELD) is HandlingAction.HUMAN_REVIEW


def test_classify_known_exceptions():
    assert classify_exception(TemporaryProviderError()) is FailureCategory.TEMPORARY_PROVIDER_ERROR
    assert classify_exception(PermanentProviderError()) is FailureCategory.PERMANENT_PROVIDER_ERROR
    assert classify_exception(InvalidDocumentError()) is FailureCategory.INVALID_DOCUMENT


def test_unknown_exception_is_unknown_category():
    assert classify_exception(ValueError("surprise")) is FailureCategory.UNKNOWN_ERROR
