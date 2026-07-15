"""A fake AI extractor used for safe, free, repeatable testing.

Real AI providers cost money, need credentials, and give slightly different
answers every time -- terrible for automated tests. This mock returns canned
data and can be told to act out any scenario the pipeline needs to handle:

    clean          -> a perfect pay stub (becomes PROCESSED)
    alt_schema     -> correct data but DIFFERENT field names (tests normalizer)
    low_confidence -> confidence below the trust threshold (NEEDS_REVIEW)
    missing_field  -> employer missing (NEEDS_REVIEW)
    timeout        -> raises a temporary error every time (tests retry -> DLQ)
    corrupt        -> raises a permanent error (tests immediate DLQ)

`fail_times` makes it fail transiently a set number of times and THEN succeed --
that is how we prove "retry, then recover" works.
"""
from __future__ import annotations

from extraction.interface import DocumentExtractor
from shared.exceptions import (
    InvalidDocumentError,
    TemporaryProviderError,
)
from shared.models import Provider

# Deliberately messy raw outputs. Note the inconsistent keys ("worker" vs
# "employee") and formats ("$3,250.00" vs 4250) -- exactly what the normalizer
# has to tidy up.
_SCENARIOS: dict[str, dict] = {
    "clean": {
        "worker": "Jamie Smith",
        "company": "Example Corporation",
        "gross_income": "$3,250.00",
        "pay_period_start": "2026-06-01",
        "pay_period_end": "2026-06-15",
        "confidence": 0.94,
    },
    "alt_schema": {
        "employee": "Alex Rivera",
        "employer": "Globex LLC",
        "grossPay": 4250,
        "payPeriodStart": "2026-06-01",
        "payPeriodEnd": "2026-06-15",
        "confidence": 0.91,
    },
    "low_confidence": {
        "worker": "Morgan Lee",
        "company": "Initech",
        "gross_income": "$2,900.00",
        "pay_period_start": "2026-06-01",
        "pay_period_end": "2026-06-15",
        "confidence": 0.78,
    },
    "missing_field": {
        "worker": "Casey Doe",
        "gross_income": "$3,100.00",
        "pay_period_start": "2026-06-01",
        "pay_period_end": "2026-06-15",
        "confidence": 0.93,
    },
}


class MockExtractor(DocumentExtractor):
    provider = Provider.MOCK

    def __init__(self, scenario: str = "clean", fail_times: int = 0) -> None:
        """
        scenario:   which canned situation to act out (see module docstring).
        fail_times: raise a transient error this many times, then behave per
                    `scenario`. Used to test retry-then-succeed.
        """
        self.scenario = scenario
        self.fail_times = fail_times
        self.calls = 0  # lets tests assert how many attempts happened

    def extract(self, document_content: bytes) -> dict:
        self.calls += 1

        # Transient failures for the first `fail_times` attempts, then recover.
        if self.calls <= self.fail_times:
            raise TemporaryProviderError(
                f"simulated timeout on attempt {self.calls}"
            )

        # Scenarios that always fail.
        if self.scenario == "timeout":
            raise TemporaryProviderError("provider timed out")
        if self.scenario == "corrupt":
            raise InvalidDocumentError("document is corrupt or unreadable")

        if self.scenario not in _SCENARIOS:
            raise InvalidDocumentError(f"unknown scenario: {self.scenario}")

        # Return a fresh copy so callers can't mutate our canned data.
        return dict(_SCENARIOS[self.scenario])
