"""The contract every AI extraction provider must satisfy.

This is the single most important design decision for "future-proofing": the
pipeline talks to `DocumentExtractor`, never to a specific vendor. Swapping the
mock for Bedrock, Textract, or Vertex AI later means writing ONE new class that
fits this plug -- zero changes to the rest of the system.

Beginner note: an "abstract base class" (ABC) is a template. It says "any real
provider MUST have an `extract` method that works like this," but it doesn't do
the work itself. It is the shape of the plug, not the appliance.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from shared.models import Provider


class DocumentExtractor(ABC):
    """Every provider adapter implements this one method."""

    #: Which provider this adapter represents (stamped onto each result).
    provider: Provider = Provider.MOCK

    @abstractmethod
    def extract(self, document_content: bytes) -> dict:
        """Read a document's bytes and return the provider's RAW field guesses.

        The return value is intentionally *not* standardized -- different
        providers return different shapes on purpose, and the normalizer's job
        is to clean that up. Implementations may raise TemporaryProviderError,
        PermanentProviderError, or InvalidAiOutputError from shared.exceptions.
        """
        raise NotImplementedError
