"""End-to-end pipeline tests covering the four required scenarios + duplicates.

A no-op `sleep` is injected everywhere so backoff waits don't slow the suite.
"""
from extraction.mock_provider import MockExtractor
from notifications.notifier import CollectingNotifier
from pipeline import Pipeline
from shared.models import ProcessingStatus
from storage.repository import InMemoryRepository

NO_WAIT = lambda _seconds: None  # noqa: E731


def make_pipeline(extractor, repo=None, notifier=None):
    return Pipeline(
        extractor=extractor,
        repository=repo or InMemoryRepository(),
        notifier=notifier or CollectingNotifier(),
        sleep=NO_WAIT,
    )


# --- Scenario 1: success ----------------------------------------------------
def test_successful_document_is_processed():
    result = make_pipeline(MockExtractor(scenario="clean")).process(b"doc-1")
    assert result.status is ProcessingStatus.PROCESSED
    assert result.record["employeeName"] == "Jamie Smith"
    assert result.record["grossPay"] == 3250.0
    assert result.record["attemptCount"] == 1
    assert result.record["requiresHumanReview"] is False


# --- Scenario 2: temporary timeout, recovers --------------------------------
def test_temporary_timeout_retries_then_succeeds():
    extractor = MockExtractor(scenario="clean", fail_times=2)
    result = make_pipeline(extractor).process(b"doc-2")
    assert result.status is ProcessingStatus.PROCESSED
    assert extractor.calls == 3          # failed twice, succeeded on the 3rd
    assert result.record["attemptCount"] == 3


# --- Scenario 3: missing / low-confidence -> human review -------------------
def test_missing_field_needs_review_and_alerts():
    notifier = CollectingNotifier()
    result = make_pipeline(MockExtractor(scenario="missing_field"),
                           notifier=notifier).process(b"doc-3")
    assert result.status is ProcessingStatus.NEEDS_REVIEW
    assert result.record["requiresHumanReview"] is True
    assert len(notifier.sent) == 1       # a reviewer alert was raised


def test_low_confidence_needs_review():
    result = make_pipeline(MockExtractor(scenario="low_confidence")).process(b"doc-3b")
    assert result.status is ProcessingStatus.NEEDS_REVIEW


# --- Scenario 4: permanent failure -> dead-letter ---------------------------
def test_permanent_failure_is_dead_lettered():
    pipeline = make_pipeline(MockExtractor(scenario="corrupt"))
    result = pipeline.process(b"doc-4")
    assert result.status is ProcessingStatus.FAILED
    assert result.dead_lettered is True
    assert len(pipeline.dead_letter_queue) == 1
    # A permanent failure must NOT pretend it retried -- it fails on attempt 1.
    assert result.dead_letter.attempts == 1


def test_exhausted_retries_are_dead_lettered():
    extractor = MockExtractor(scenario="timeout")   # times out forever
    pipeline = make_pipeline(extractor)
    result = pipeline.process(b"doc-4b")
    assert result.dead_lettered is True
    assert extractor.calls == 3          # tried the max number of times


# --- Duplicate detection ----------------------------------------------------
def test_duplicate_document_is_detected():
    repo = InMemoryRepository()
    first = make_pipeline(MockExtractor(scenario="clean"), repo=repo).process(b"same-bytes")
    second = make_pipeline(MockExtractor(scenario="clean"), repo=repo).process(b"same-bytes")
    assert first.deduplicated is False
    assert second.deduplicated is True
    assert second.record["documentId"] == first.record["documentId"]
    assert len(repo.all()) == 1          # stored only once
