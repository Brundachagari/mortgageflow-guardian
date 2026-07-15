"""Convert a provider's raw, inconsistent output into canonical fields.

Two different AI providers (or two versions of one) describe the same fact in
different ways:

    {"worker": "Jamie Smith", "gross_income": "$3,250.00", "confidence": 0.94}
    {"employee": "Jamie Smith", "grossPay": 3250, "confidence": 94}

Downstream code should never have to know about those differences. This module
absorbs them, so everything after it sees ONE predictable shape with real types
(a float for money, an int 0-100 for confidence).
"""
from __future__ import annotations

import re
from typing import Any

# Canonical field -> the raw keys a provider might use for it. First hit wins.
_ALIASES: dict[str, tuple[str, ...]] = {
    "employeeName": ("employeeName", "employee_name", "employee", "worker", "name"),
    "employerName": ("employerName", "employer_name", "employer", "company"),
    "grossPay": ("grossPay", "gross_pay", "gross_income", "gross", "pay"),
    "payPeriodStart": ("payPeriodStart", "pay_period_start", "period_start"),
    "payPeriodEnd": ("payPeriodEnd", "pay_period_end", "period_end"),
    "confidence": ("confidenceScore", "confidence_score", "confidence", "score"),
}

# Strips anything that isn't a digit, dot, or minus sign -> "$3,250.00" -> "3250.00"
_NON_NUMERIC = re.compile(r"[^0-9.\-]")


def _first_present(raw: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
    return None


def _to_money(value: Any) -> float | None:
    """Coerce "$3,250.00" or 4250 into 3250.0. Returns None if unparseable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    cleaned = _NON_NUMERIC.sub("", str(value))
    if cleaned in ("", ".", "-", "-."):
        return None
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _to_confidence(value: Any) -> int | None:
    """Normalize confidence to an int 0-100.

    Providers report EITHER a 0-1 fraction (0.94) OR a percentage (94). We treat
    anything <= 1 as a fraction so both land on the same 0-100 scale.
    """
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num <= 1.0:
        num *= 100
    return max(0, min(100, round(num)))


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize(raw: dict) -> dict:
    """Return canonical fields extracted from any provider's raw payload."""
    return {
        "employeeName": _clean_text(_first_present(raw, _ALIASES["employeeName"])),
        "employerName": _clean_text(_first_present(raw, _ALIASES["employerName"])),
        "grossPay": _to_money(_first_present(raw, _ALIASES["grossPay"])),
        "currency": "USD",
        "payPeriodStart": _clean_text(_first_present(raw, _ALIASES["payPeriodStart"])),
        "payPeriodEnd": _clean_text(_first_present(raw, _ALIASES["payPeriodEnd"])),
        "confidenceScore": _to_confidence(_first_present(raw, _ALIASES["confidence"])),
    }
