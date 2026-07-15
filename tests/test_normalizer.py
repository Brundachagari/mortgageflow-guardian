"""Tests for the normalizer: messy provider output -> one clean shape."""
from normalization.normalizer import normalize


def test_handles_different_field_names():
    # Two providers, different keys, SAME underlying facts -> identical output.
    a = normalize({"worker": "Jamie Smith", "company": "Acme", "gross_income": "$3,250.00",
                   "confidence": 0.94})
    b = normalize({"employee": "Jamie Smith", "employer": "Acme", "grossPay": 3250,
                   "confidence": 94})
    assert a["employeeName"] == b["employeeName"] == "Jamie Smith"
    assert a["employerName"] == b["employerName"] == "Acme"
    assert a["grossPay"] == b["grossPay"] == 3250.0


def test_parses_currency_string_to_float():
    assert normalize({"gross_income": "$3,250.00"})["grossPay"] == 3250.0
    assert normalize({"grossPay": 4250})["grossPay"] == 4250.0


def test_confidence_fraction_and_percent_converge():
    assert normalize({"confidence": 0.94})["confidenceScore"] == 94
    assert normalize({"confidence": 94})["confidenceScore"] == 94


def test_missing_values_become_none():
    fields = normalize({"confidence": 0.9})
    assert fields["employeeName"] is None
    assert fields["employerName"] is None
    assert fields["grossPay"] is None


def test_unparseable_money_is_none_not_crash():
    assert normalize({"gross_income": "N/A"})["grossPay"] is None
