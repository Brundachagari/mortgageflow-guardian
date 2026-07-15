"""The orchestrator: runs one document through every step, start to finish.

In Phase 2 this exact sequence becomes an AWS Step Functions state machine (one
state per step, each independently retryable and visible). Keeping it as plain,
ordered Python here means the whole flow is testable and demoable on a laptop --
and the step boundaries already exist, which is what makes the later
"Step Functions instead of one giant Lambda" decision easy to defend.

Flow:
    hash + dedupe -> extract (with retry/backoff) -> normalize -> validate
    -> persist -> notify (if review) / dead-letter (if permanent failure)
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

from extraction.interface import DocumentExtractor
from incidents.classifier import classify_exception, is_retryable
from notifications.notifier import CollectingNotifier, Notifier
from normalization.normalizer import normalize
from shared.exceptions import MortgageFlowError
from shared.logging_utils import get_logger, log_event
from shared.models import (
    FailureCategory,
    ProcessingStatus,
    StandardizedDocument,
)
from storage.repository import DocumentRepository, InMemoryRepository
from validation.validator import validate

# Retry policy. The AWS deployment mirrors these values in the Step Functions
# definition (infrastructure/state_machine.asl.json). 3 attempts, backing off
# 2s, 4s, 8s. `sleep` is injectable so tests run instantly.
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 2


@dataclass
class DeadLetter:
    """A message that could not be processed -- preserved, never dropped."""

    documentHash: str
    category: FailureCategory
    reason: str
    attempts: int


@dataclass
class PipelineResult:
    """Everything the caller (demo/tests) needs to see what happened."""

    record: Optional[dict] = None
    status: Optional[ProcessingStatus] = None
    deduplicated: bool = False
    dead_lettered: bool = False
    dead_letter: Optional[DeadLetter] = None
    attempts: int = 0


@dataclass
class Pipeline:
    extractor: DocumentExtractor
    repository: DocumentRepository = field(default_factory=InMemoryRepository)
    notifier: Notifier = field(default_factory=CollectingNotifier)
    dead_letter_queue: list[DeadLetter] = field(default_factory=list)
    #: Injectable sleep so tests don't actually wait during backoff.
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        self._log = get_logger("pipeline")

    # -- public entry point --------------------------------------------------
    def process(self, document_content: bytes) -> PipelineResult:
        document_hash = self._hash(document_content)

        # STEP 1: Duplicate detection. Same content = same SHA-256 = skip re-work.
        existing = self.repository.find_by_hash(document_hash)
        if existing is not None:
            log_event(self._log, "duplicate_detected", documentHash=document_hash)
            return PipelineResult(
                record=existing,
                status=ProcessingStatus(existing["processingStatus"]),
                deduplicated=True,
            )

        document_id = f"doc-{uuid.uuid4().hex[:8]}"

        # STEP 2: Extract with retry/backoff. Returns raw output + attempt count,
        # or dead-letters on permanent failure / exhausted retries.
        try:
            raw, attempts = self._extract_with_retry(document_content)
        except MortgageFlowError as exc:
            category = classify_exception(exc)
            # attempts is stamped on the exception by _extract_with_retry, so a
            # permanent failure reports 1 and an exhausted transient reports 3.
            attempts = getattr(exc, "attempts", 1)
            return self._dead_letter(document_hash, category, str(exc), attempts)
        except Exception as exc:  # defensive: unexpected errors are still handled
            attempts = getattr(exc, "attempts", 1)
            return self._dead_letter(
                document_hash, FailureCategory.UNKNOWN_ERROR, str(exc), attempts
            )

        # STEP 3: Normalize messy raw output into canonical fields.
        fields = normalize(raw)

        # STEP 4: Validate completeness + confidence.
        outcome = validate(fields)

        # STEP 5: Build and persist the standardized record.
        doc = StandardizedDocument(
            documentId=document_id,
            documentHash=document_hash,
            processingStatus=outcome.status,
            requiresHumanReview=outcome.requires_human_review,
            reviewReasons=outcome.reasons,
            failureCategories=outcome.categories,
            attemptCount=attempts,
            provider=self.extractor.provider,
            **fields,
        )
        record = doc.to_record()
        self.repository.save(record)
        log_event(
            self._log,
            "document_stored",
            documentId=document_id,
            status=outcome.status.value,
            attemptCount=attempts,
        )

        # STEP 6: Route. NEEDS_REVIEW -> alert a human (never auto-accept).
        if outcome.requires_human_review:
            self.notifier.notify_review_needed(record)

        return PipelineResult(record=record, status=outcome.status, attempts=attempts)

    # -- internal steps ------------------------------------------------------
    def _extract_with_retry(self, content: bytes) -> tuple[dict, int]:
        """Call the provider, retrying transient failures with exponential backoff.

        Returns (raw_output, attempt_count). Re-raises on permanent failures
        (immediately) or once transient retries are exhausted.
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                raw = self.extractor.extract(content)
                return raw, attempt
            except Exception as exc:
                category = classify_exception(exc)
                # Record how many attempts we actually made, so the caller can
                # report it truthfully (1 for permanent, MAX for exhausted).
                exc.attempts = attempt
                # Permanent failures never retry -- bail out right away.
                if not is_retryable(category):
                    raise
                # Transient: retry until we hit the attempt ceiling.
                if attempt >= MAX_ATTEMPTS:
                    log_event(
                        self._log,
                        "retries_exhausted",
                        category=category.value,
                        attempts=attempt,
                    )
                    raise
                wait = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))  # 2s, 4s, 8s...
                log_event(
                    self._log,
                    "transient_error_retrying",
                    category=category.value,
                    attempt=attempt,
                    waitSeconds=wait,
                )
                self.sleep(wait)

    def _dead_letter(
        self, document_hash: str, category: FailureCategory, reason: str, attempts: int
    ) -> PipelineResult:
        dl = DeadLetter(
            documentHash=document_hash,
            category=category,
            reason=reason,
            attempts=attempts,
        )
        self.dead_letter_queue.append(dl)
        log_event(
            self._log,
            "dead_lettered",
            documentHash=document_hash,
            category=category.value,
            reason=reason,
        )
        return PipelineResult(
            status=ProcessingStatus.FAILED,
            dead_lettered=True,
            dead_letter=dl,
            attempts=attempts,
        )

    @staticmethod
    def _hash(content: bytes) -> str:
        """SHA-256 of the file bytes -- the fingerprint used for deduplication."""
        return hashlib.sha256(content).hexdigest()
