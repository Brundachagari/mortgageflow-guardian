"""Reviewer notifications.

When a document is routed to a human, someone has to be told. Phase 1 uses a
CollectingNotifier that just remembers the alerts in memory, so the local demo
and tests can prove "yes, an alert was raised" without sending real email. In
Phase 2 an SNS-backed version implements the same interface and publishes for
real.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from shared.logging_utils import get_logger, log_event


class Notifier(ABC):
    @abstractmethod
    def notify_review_needed(self, record: dict) -> None: ...


class CollectingNotifier(Notifier):
    """Records notifications in a list instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self._log = get_logger("notifications")

    def notify_review_needed(self, record: dict) -> None:
        self.sent.append(record)
        # Logged through the sanitizer, so the reviewer alert never leaks PII.
        log_event(
            self._log,
            "human_review_requested",
            documentId=record.get("documentId"),
            reasons=record.get("reviewReasons"),
        )


class SnsNotifier(Notifier):
    """Publishes reviewer alerts to an SNS topic (used in AWS).

    Same interface as CollectingNotifier. The message deliberately contains only
    the documentId and the review reasons -- never the extracted personal data --
    so the notification itself carries no sensitive information.
    """

    def __init__(self, topic_arn: str | None = None, region: str | None = None):
        import os

        import boto3

        self._topic_arn = topic_arn or os.environ["REVIEW_TOPIC_ARN"]
        self._sns = boto3.client(
            "sns", region_name=region or os.environ.get("AWS_REGION")
        )

    def notify_review_needed(self, record: dict) -> None:
        reasons = ", ".join(record.get("reviewReasons", [])) or "manual check"
        self._sns.publish(
            TopicArn=self._topic_arn,
            Subject=f"Document {record['documentId']} needs review",
            Message=(
                f"Document {record['documentId']} "
                f"({record.get('documentType')}) was routed for human review.\n"
                f"Reasons: {reasons}"
            ),
        )
