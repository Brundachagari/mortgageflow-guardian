"""Run a fictional pay stub through the REAL Claude LLM extractor.

This proves the "AI & Automation" requirement literally: a genuine LLM extracts
the fields, then the SAME normalize -> validate -> standardize pipeline you
already tested turns that output into a trusted record.

Requires an Anthropic API key:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python llm_demo.py

Uses synthetic data only. Costs a fraction of a cent per run.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from extraction.claude_provider import ClaudeExtractor  # noqa: E402
from normalization.normalizer import normalize  # noqa: E402
from shared.models import StandardizedDocument, ProcessingStatus  # noqa: E402
from validation.validator import validate  # noqa: E402

# A fictional, synthetic pay stub (plain text, as if OCR'd from a document).
SAMPLE = """
    EXAMPLE CORPORATION — Earnings Statement
    Employee: Jamie Smith
    Pay period: 2026-06-01 through 2026-06-15
    Gross pay: $3,250.00
    Net pay:   $2,610.00
"""


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY first:  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
    print(f"Extracting with real Claude ({model}) — synthetic data only...\n")

    # 1) REAL LLM extraction.
    extractor = ClaudeExtractor(model=model)
    raw = extractor.extract(SAMPLE.encode("utf-8"))
    print("Raw LLM output:")
    print(json.dumps(raw, indent=2))

    # 2) Same pipeline steps as the mock path: normalize + validate + standardize.
    fields = normalize(raw)
    outcome = validate(fields)
    doc = StandardizedDocument(
        documentId="doc-llm-0001",
        documentHash="(demo)",
        processingStatus=outcome.status,
        requiresHumanReview=outcome.requires_human_review,
        reviewReasons=outcome.reasons,
        provider=extractor.provider,
        **fields,
    )

    print("\nStandardized record:")
    print(json.dumps(doc.to_record(), indent=2))
    icon = "✅" if doc.processingStatus == ProcessingStatus.PROCESSED else "🟡"
    print(f"\n{icon} Outcome: {doc.processingStatus.value}")


if __name__ == "__main__":
    main()
