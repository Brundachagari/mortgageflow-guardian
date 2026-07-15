"""Local demonstration of MortgageFlow Guardian -- runs with NO AWS, NO cost.

Run it with:   python demo.py

It pushes a fictional pay stub through the pipeline five times, each time acting
out a different real-world situation, and prints the outcome of each path:

    1. Successful document        -> PROCESSED
    2. Missing / low confidence   -> NEEDS_REVIEW (+ reviewer alert)
    3. Temporary timeout, recovers-> retries, then PROCESSED
    4. Permanent failure          -> FAILED (message preserved in dead-letter queue)
    5. Duplicate document         -> detected and skipped
"""
import sys
from pathlib import Path

# Make the code in src/ importable when running this file directly.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from extraction.mock_provider import MockExtractor          # noqa: E402
from notifications.notifier import CollectingNotifier        # noqa: E402
from pipeline import Pipeline                                # noqa: E402
from storage.repository import InMemoryRepository            # noqa: E402

# --- pretty printing helpers ------------------------------------------------
LINE = "=" * 68


def header(n, title):
    print(f"\n{LINE}\nSCENARIO {n}: {title}\n{LINE}")


def show(result):
    if result.deduplicated:
        print("  Outcome        : DUPLICATE — skipped re-processing")
        print(f"  Reused record  : {result.record['documentId']}")
        return
    if result.dead_lettered:
        dl = result.dead_letter
        print("  Outcome        : FAILED — sent to dead-letter queue")
        print(f"  Category       : {dl.category.value}")
        print(f"  Reason         : {dl.reason}")
        print(f"  Attempts made  : {dl.attempts}")
        return
    r = result.record
    print(f"  Outcome        : {r['processingStatus']}")
    print(f"  Document ID    : {r['documentId']}")
    print(f"  Employee       : {r.get('employeeName')}")
    print(f"  Employer       : {r.get('employerName')}")
    print(f"  Gross pay      : {r.get('grossPay')} {r.get('currency')}")
    print(f"  Confidence     : {r.get('confidenceScore')}")
    print(f"  Attempts made  : {r['attemptCount']}")
    if r.get("requiresHumanReview"):
        print(f"  Review reasons : {', '.join(r.get('reviewReasons', []))}")


def main():
    # One synthetic document's bytes; content is what we hash for dedup.
    sample = Path(__file__).parent / "sample_documents" / "fictional_pay_stub.json"
    content = sample.read_bytes()

    # Shared repository + notifier so duplicate detection and alerts persist
    # across scenarios, just like a real deployment would.
    repo = InMemoryRepository()
    notifier = CollectingNotifier()

    def make_pipeline(extractor):
        # sleep is a no-op here so the demo doesn't actually wait during backoff.
        return Pipeline(
            extractor=extractor,
            repository=repo,
            notifier=notifier,
            sleep=lambda _seconds: None,
        )

    print("\nMortgageFlow Guardian — local demonstration")
    print("Fictional / synthetic data only. No AWS resources are used.")

    # 1) Clean, high-confidence document.
    header(1, "Successful document")
    show(make_pipeline(MockExtractor(scenario="clean")).process(content))

    # 2) Missing employer field -> human review.
    header(2, "Missing / low-confidence data (human review)")
    show(make_pipeline(MockExtractor(scenario="missing_field")).process(b"different-doc-2"))

    # 3) Times out twice, then succeeds on the 3rd attempt.
    header(3, "Temporary timeout, recovers after retries")
    show(make_pipeline(MockExtractor(scenario="clean", fail_times=2)).process(b"different-doc-3"))

    # 4) Corrupt file -> permanent failure -> dead-letter queue.
    header(4, "Permanent failure (dead-letter queue)")
    show(make_pipeline(MockExtractor(scenario="corrupt")).process(b"different-doc-4"))

    # 5) Re-submit scenario 1's exact content -> duplicate detected.
    header(5, "Duplicate document detection")
    show(make_pipeline(MockExtractor(scenario="clean")).process(content))

    # --- summary ------------------------------------------------------------
    print(f"\n{LINE}\nSUMMARY\n{LINE}")
    print(f"  Stored records          : {len(repo.all())}")
    print(f"  Awaiting human review   : {len(repo.list_by_status('NEEDS_REVIEW'))}")
    print(f"  Reviewer alerts sent    : {len(notifier.sent)}")
    print("  Dead-letter queue depth : 1 (the corrupt document)\n")


if __name__ == "__main__":
    main()
