"""Core data shapes for MortgageFlow Guardian.

Everything the rest of the system passes around is defined here:

* Enums for the fixed vocabularies (statuses, failure categories, actions) so we
  never sprinkle magic strings like "PROCESSED" through the code.
* `StandardizedDocument` -- the single, trusted output schema. It is a Pydantic
  model, which means it *validates itself*: if code tries to build a record with
  the wrong types, Pydantic raises an error instead of letting bad data through.

Beginner note: an "enum" is just a fixed list of allowed values with names, like
a dropdown menu. Using one stops typos (e.g. "PROCESED") from becoming bugs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    """Where a document is in its journey through the pipeline."""

    UPLOADED = "UPLOADED"        # file has landed, nothing done yet
    QUEUED = "QUEUED"            # waiting in the processing queue
    PROCESSING = "PROCESSING"    # actively being extracted/validated
    RETRYING = "RETRYING"        # a transient error happened; trying again
    PROCESSED = "PROCESSED"      # success, data is trusted
    NEEDS_REVIEW = "NEEDS_REVIEW"  # a human must look at it
    FAILED = "FAILED"            # gave up; message preserved in the DLQ


class FailureCategory(str, Enum):
    """A precise label for *why* something went wrong.

    Precise labels are what make failures actionable (retry? review? give up?)
    and what feed clean metrics later in CloudWatch.
    """

    TEMPORARY_PROVIDER_ERROR = "TEMPORARY_PROVIDER_ERROR"  # timeout/throttle -> retry
    PERMANENT_PROVIDER_ERROR = "PERMANENT_PROVIDER_ERROR"  # won't recover -> DLQ
    INVALID_DOCUMENT = "INVALID_DOCUMENT"                  # corrupt/unsupported file
    INVALID_AI_OUTPUT = "INVALID_AI_OUTPUT"                # AI returned non-JSON/junk
    LOW_CONFIDENCE = "LOW_CONFIDENCE"                      # below trust threshold
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"      # incomplete extraction
    DATABASE_ERROR = "DATABASE_ERROR"                      # storage failed
    DUPLICATE_DOCUMENT = "DUPLICATE_DOCUMENT"              # already processed
    UNKNOWN_ERROR = "UNKNOWN_ERROR"                        # anything unclassified


class HandlingAction(str, Enum):
    """What the system should DO about a given failure category."""

    RETRY = "RETRY"                    # transient -> try again with backoff
    HUMAN_REVIEW = "HUMAN_REVIEW"      # uncertain -> route to a person
    DEAD_LETTER = "DEAD_LETTER"        # permanent -> preserve, stop processing
    SKIP_DUPLICATE = "SKIP_DUPLICATE"  # already handled -> do nothing new


class Provider(str, Enum):
    """Which extraction provider produced a result."""

    MOCK = "MOCK"
    ANTHROPIC = "ANTHROPIC"
    BEDROCK = "BEDROCK"
    TEXTRACT = "TEXTRACT"
    VERTEX_AI = "VERTEX_AI"


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string (audit-friendly, timezone-aware)."""
    return datetime.now(timezone.utc).isoformat()


class StandardizedDocument(BaseModel):
    """The one output shape every downstream consumer can rely on.

    Building AI results into this model is the whole point of the platform: no
    matter how messy the provider's raw output was, what comes out here is
    consistent, typed, and audit-stamped.
    """

    documentId: str
    documentHash: str
    documentType: str = "PAY_STUB"

    employeeName: Optional[str] = None
    employerName: Optional[str] = None
    grossPay: Optional[float] = None
    currency: Optional[str] = "USD"
    payPeriodStart: Optional[str] = None
    payPeriodEnd: Optional[str] = None
    confidenceScore: Optional[int] = None

    processingStatus: ProcessingStatus
    requiresHumanReview: bool = False
    reviewReasons: list[str] = Field(default_factory=list)
    failureCategories: list[FailureCategory] = Field(default_factory=list)

    attemptCount: int = 1
    provider: Provider = Provider.MOCK

    createdAt: str = Field(default_factory=_now_iso)
    updatedAt: str = Field(default_factory=_now_iso)

    def touch(self) -> None:
        """Refresh updatedAt whenever the record changes."""
        self.updatedAt = _now_iso()

    def to_record(self) -> dict:
        """Plain dict for storage / JSON output (enums become their string values)."""
        return self.model_dump(mode="json")
