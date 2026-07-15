"""Turn a failure category into a decision: retry, review, or dead-letter.

This is the "incident automation" brain. It centralizes the policy so the
pipeline never has to reason about individual error types inline -- it just asks
the classifier "what should I do about this?" and follows the answer. Changing
policy (e.g. making a new error retryable) is a one-line edit here.
"""
from __future__ import annotations

from shared.exceptions import MortgageFlowError
from shared.models import FailureCategory, HandlingAction

# The policy table. Each failure category maps to exactly one action.
_ACTION_BY_CATEGORY: dict[FailureCategory, HandlingAction] = {
    # Transient -> try again with backoff.
    FailureCategory.TEMPORARY_PROVIDER_ERROR: HandlingAction.RETRY,
    # Won't get better on retry -> preserve in the dead-letter queue.
    FailureCategory.PERMANENT_PROVIDER_ERROR: HandlingAction.DEAD_LETTER,
    FailureCategory.INVALID_DOCUMENT: HandlingAction.DEAD_LETTER,
    FailureCategory.DATABASE_ERROR: HandlingAction.DEAD_LETTER,
    FailureCategory.UNKNOWN_ERROR: HandlingAction.DEAD_LETTER,
    # Uncertain / business-sensitive -> a human decides, never auto-accepted.
    FailureCategory.INVALID_AI_OUTPUT: HandlingAction.HUMAN_REVIEW,
    FailureCategory.LOW_CONFIDENCE: HandlingAction.HUMAN_REVIEW,
    FailureCategory.MISSING_REQUIRED_FIELD: HandlingAction.HUMAN_REVIEW,
    # Already handled -> do nothing new.
    FailureCategory.DUPLICATE_DOCUMENT: HandlingAction.SKIP_DUPLICATE,
}


def action_for(category: FailureCategory) -> HandlingAction:
    """Return the configured action for a failure category."""
    return _ACTION_BY_CATEGORY.get(category, HandlingAction.DEAD_LETTER)


def is_retryable(category: FailureCategory) -> bool:
    """Convenience check the pipeline uses to decide whether to loop."""
    return action_for(category) is HandlingAction.RETRY


def classify_exception(exc: Exception) -> FailureCategory:
    """Map any raised exception to a failure category.

    Our own errors carry their category; anything unexpected is UNKNOWN_ERROR so
    it is still handled safely (dead-lettered) rather than crashing the pipeline.
    """
    if isinstance(exc, MortgageFlowError):
        return exc.category
    return FailureCategory.UNKNOWN_ERROR
