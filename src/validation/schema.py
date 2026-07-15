"""The validation *rules* (kept separate from the logic that applies them).

Putting the tunable numbers in one place means that when the interview panel
asks "why 90?", you can point at a single, clearly-labelled constant instead of
hunting through code. These are demonstration thresholds, not real Pennymac
business rules.
"""
from __future__ import annotations

# A pay stub must contain these before we can trust it downstream.
REQUIRED_FIELDS: tuple[str, ...] = ("employeeName", "employerName", "grossPay")

# Confidence routing (0-100 scale):
#   >= AUTO_ACCEPT_THRESHOLD -> trusted, marked PROCESSED
#   <  AUTO_ACCEPT_THRESHOLD -> not trusted, routed to a human (NEEDS_REVIEW)
AUTO_ACCEPT_THRESHOLD = 90

# Human-readable labels for building clear "why" messages.
FIELD_LABELS = {
    "employeeName": "Employee name",
    "employerName": "Employer name",
    "grossPay": "Gross pay",
}
