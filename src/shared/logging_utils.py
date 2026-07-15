"""Logging that never leaks sensitive values.

A mortgage pay stub contains personal data. If we logged the raw record, that
personal data would end up in CloudWatch logs in plain text -- a security
problem. So every log goes through `sanitize()`, which masks the sensitive
fields while keeping the operational fields (id, status, category) we actually
need for debugging and metrics.

Beginner note: "sanitize" here means "scrub out the private bits before writing
it down." We keep *that* it happened, not *whose* data it was.
"""
from __future__ import annotations

import json
import logging
import sys

# Fields that identify or expose a real person / their finances. Masked in logs.
SENSITIVE_FIELDS = {
    "employeeName",
    "employerName",
    "grossPay",
    "payPeriodStart",
    "payPeriodEnd",
}

_MASK = "***REDACTED***"


def sanitize(record: dict) -> dict:
    """Return a copy of `record` with sensitive fields masked.

    Non-destructive: the original record is untouched, so business logic still
    sees real values -- only the log copy is scrubbed.
    """
    safe = {}
    for key, value in record.items():
        if key in SENSITIVE_FIELDS and value not in (None, ""):
            safe[key] = _MASK
        else:
            safe[key] = value
    return safe


def get_logger(name: str) -> logging.Logger:
    """A logger that emits one JSON object per line (easy to search in CloudWatch)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, **fields) -> None:
    """Log a structured, sanitized event.

    Example: log_event(log, "document_processed", documentId="doc-1", status="PROCESSED")
    """
    payload = {"event": event, **sanitize(fields)}
    logger.info(json.dumps(payload))
