"""Ingestion Lambda -- the entry point into the AWS workflow.

Trigger: a message on the SQS processing queue. That message was placed there by
S3 itself when a file landed in the bucket (S3 -> SQS event notification). So
this function's job is:

    1. read which S3 object was uploaded,
    2. do cheap gatekeeping (allowed file type, size limit),
    3. start a Step Functions execution to process it.

Keeping validation here means bad files are rejected *before* we spend any AI or
compute effort on them. Anything this function can't handle (throws on) is
retried by SQS and, after enough failures, parked in the SQS dead-letter queue.
"""
from __future__ import annotations

import json
import os
import urllib.parse

import boto3

from shared.logging_utils import get_logger, log_event

_log = get_logger("ingestion")

# Configured via Terraform environment variables.
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")
ALLOWED_EXTENSIONS = set(
    os.environ.get("ALLOWED_EXTENSIONS", "pdf,png,jpg,jpeg,json").split(",")
)
MAX_FILE_BYTES = int(os.environ.get("MAX_FILE_MB", "10")) * 1024 * 1024

_sfn = boto3.client("stepfunctions")


def _is_allowed(key: str, size: int) -> tuple[bool, str]:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"extension '{ext}' not allowed"
    if size > MAX_FILE_BYTES:
        return False, f"file size {size} exceeds limit {MAX_FILE_BYTES}"
    return True, "ok"


def handler(event, context):
    """SQS batch handler. Each record wraps an S3 event notification."""
    started = 0
    for record in event.get("Records", []):
        body = json.loads(record["body"])

        # S3 sends a test event on setup; it has no "Records" -- skip it.
        for s3_event in body.get("Records", []):
            bucket = s3_event["s3"]["bucket"]["name"]
            key = urllib.parse.unquote_plus(s3_event["s3"]["object"]["key"])
            size = s3_event["s3"]["object"].get("size", 0)

            ok, reason = _is_allowed(key, size)
            if not ok:
                # Rejected files are logged and dropped, not processed.
                log_event(_log, "upload_rejected", key=key, reason=reason)
                continue

            _sfn.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                input=json.dumps({"bucket": bucket, "key": key}),
            )
            started += 1
            log_event(_log, "execution_started", bucket=bucket, key=key)

    return {"executionsStarted": started}
