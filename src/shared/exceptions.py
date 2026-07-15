"""Custom exception types, each tagged with a FailureCategory.

Why bother with custom exceptions instead of plain `raise Exception(...)`?
Because the *type* of error decides the *response*. A timeout should be retried;
a corrupt file should not. By attaching a `category` to each exception, the
incident classifier can make that decision mechanically instead of guessing from
error text.

Beginner note: an "exception" is Python's way of signalling "something went
wrong here." Making our own lets us carry extra meaning with the error.
"""
from __future__ import annotations

from shared.models import FailureCategory


class MortgageFlowError(Exception):
    """Base class for every error this system raises on purpose."""

    category: FailureCategory = FailureCategory.UNKNOWN_ERROR


class TemporaryProviderError(MortgageFlowError):
    """A transient AI-provider problem (timeout, throttling). Safe to retry."""

    category = FailureCategory.TEMPORARY_PROVIDER_ERROR


class PermanentProviderError(MortgageFlowError):
    """A provider problem that will not improve on retry (auth, bad request)."""

    category = FailureCategory.PERMANENT_PROVIDER_ERROR


class InvalidDocumentError(MortgageFlowError):
    """The uploaded file is corrupt, empty, wrong type, or too large."""

    category = FailureCategory.INVALID_DOCUMENT


class InvalidAiOutputError(MortgageFlowError):
    """The provider returned something we cannot parse into fields."""

    category = FailureCategory.INVALID_AI_OUTPUT


class DatabaseError(MortgageFlowError):
    """Persisting or reading a record failed."""

    category = FailureCategory.DATABASE_ERROR


class DuplicateDocumentError(MortgageFlowError):
    """This exact document (by content hash) was already processed."""

    category = FailureCategory.DUPLICATE_DOCUMENT
