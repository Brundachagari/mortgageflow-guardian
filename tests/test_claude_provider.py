"""Tests for ClaudeExtractor's response handling.

These inject a fake Anthropic client, so they run with no API key and make no
network calls. They cover the logic we own -- JSON parsing, refusal handling,
and that the output flows through the normalizer -- not the SDK itself.
"""
from types import SimpleNamespace

import pytest

from extraction.claude_provider import ClaudeExtractor
from normalization.normalizer import normalize
from shared.exceptions import InvalidAiOutputError, PermanentProviderError
from shared.models import Provider


def _fake_client(text, stop_reason="end_turn"):
    """A stand-in Anthropic client whose messages.create returns canned content."""
    response = SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
    )
    messages = SimpleNamespace(create=lambda **kwargs: response)
    return SimpleNamespace(messages=messages)


def test_parses_clean_json():
    client = _fake_client(
        '{"employeeName": "Jamie Smith", "employerName": "Example Corp", '
        '"grossPay": 3250, "confidence": 0.95}'
    )
    raw = ClaudeExtractor(client=client).extract(b"paystub")
    assert raw["employeeName"] == "Jamie Smith"
    assert raw["grossPay"] == 3250


def test_tolerates_prose_around_json():
    client = _fake_client('Sure! Here is the data:\n{"grossPay": 4250}\nHope that helps.')
    raw = ClaudeExtractor(client=client).extract(b"paystub")
    assert raw["grossPay"] == 4250


def test_non_json_raises_invalid_ai_output():
    client = _fake_client("I could not read this document.")
    with pytest.raises(InvalidAiOutputError):
        ClaudeExtractor(client=client).extract(b"paystub")


def test_refusal_is_permanent_failure():
    client = _fake_client("", stop_reason="refusal")
    with pytest.raises(PermanentProviderError):
        ClaudeExtractor(client=client).extract(b"paystub")


def test_output_flows_through_normalizer():
    # The whole point: real-LLM output uses the SAME normalizer as the mock.
    client = _fake_client(
        '{"employeeName": "Alex Rivera", "employerName": "Globex", '
        '"grossPay": "$4,250.00", "confidence": 0.91}'
    )
    raw = ClaudeExtractor(client=client).extract(b"paystub")
    fields = normalize(raw)
    assert fields["grossPay"] == 4250.0
    assert fields["confidenceScore"] == 91


def test_provider_is_anthropic():
    assert ClaudeExtractor().provider is Provider.ANTHROPIC
