"""Processing Lambda -- the single task invoked by the Step Functions workflow.

This reuses the EXACT building blocks proven in Phase 1 (mock extractor,
normalizer, validator, standardized model) but wires them for the cloud:

* Storage is DynamoDB instead of an in-memory dict.
* It does NOT retry internally. If the provider raises a transient error, this
  function lets it bubble up so **Step Functions** performs the retry/backoff.
  That is the idiomatic AWS pattern: retries live in the orchestration layer
  where they are visible in the execution history, not buried inside code.

Because the exception class name becomes the Step Functions "errorType", the
state machine can match on `TemporaryProviderError` (retry) vs everything else
(catch -> dead-letter). That mapping is the whole reliability story in one place.

Demo tip: the mock scenario is chosen from the file name, so you can trigger any
path just by uploading a differently-named file (e.g. `...lowconf.json`).
"""
from __future__ import annotations

import hashlib
import uuid

import boto3

from extraction.mock_provider import MockExtractor
from normalization.normalizer import normalize
from shared.logging_utils import get_logger, log_event
from shared.models import StandardizedDocument
from storage.repository import DynamoDbRepository
from validation.validator import validate

_log = get_logger("processing")
_s3 = boto3.client("s3")


def _scenario_from_key(key: str) -> str:
    """Pick a mock scenario from the filename so every path is demoable."""
    name = key.lower()
    if "timeout" in name:
        return "timeout"      # transient -> Step Functions retries, then DLQ
    if "corrupt" in name:
        return "corrupt"      # permanent -> caught -> DLQ
    if "lowconf" in name:
        return "low_confidence"
    if "missing" in name:
        return "missing_field"
    if "alt" in name:
        return "alt_schema"
    return "clean"


def handler(event, context):
    bucket = event["bucket"]
    key = event["key"]

    content = _s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    document_hash = hashlib.sha256(content).hexdigest()

    repo = DynamoDbRepository()

    # Idempotency: same content hash means we already processed this document.
    existing = repo.find_by_hash(document_hash)
    if existing is not None:
        log_event(_log, "duplicate_detected", documentHash=document_hash)
        return {
            "documentId": existing["documentId"],
            "processingStatus": existing["processingStatus"],
            "requiresHumanReview": existing.get("requiresHumanReview", False),
            "deduplicated": True,
        }

    # Extract. This may raise TemporaryProviderError / PermanentProviderError /
    # InvalidDocumentError -- we intentionally DO NOT catch them so Step Functions
    # can retry or dead-letter based on the error type.
    extractor = MockExtractor(scenario=_scenario_from_key(key))
    raw = extractor.extract(content)

    fields = normalize(raw)
    outcome = validate(fields)

    doc = StandardizedDocument(
        documentId=f"doc-{uuid.uuid4().hex[:8]}",
        documentHash=document_hash,
        processingStatus=outcome.status,
        requiresHumanReview=outcome.requires_human_review,
        reviewReasons=outcome.reasons,
        failureCategories=outcome.categories,
        provider=extractor.provider,
        **fields,
    )
    record = doc.to_record()
    repo.save(record)

    log_event(
        _log,
        "document_stored",
        documentId=doc.documentId,
        status=outcome.status.value,
    )

    # Returned to Step Functions, which uses processingStatus in a Choice state
    # to decide whether to publish an SNS human-review alert.
    return {
        "documentId": doc.documentId,
        "processingStatus": outcome.status.value,
        "requiresHumanReview": outcome.requires_human_review,
        "reviewReasons": outcome.reasons,
        "deduplicated": False,
    }
