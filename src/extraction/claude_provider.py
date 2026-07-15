"""A REAL AI extractor powered by Claude (the Anthropic API).

This is the proof that the provider abstraction works: it implements the exact
same `DocumentExtractor` interface as the mock, so the pipeline uses it with zero
changes. Swap `MockExtractor(...)` for `ClaudeExtractor()` and the same
normalize -> validate -> store flow runs on genuine LLM output.

Requires an Anthropic API key at runtime (environment variable
ANTHROPIC_API_KEY). No key is needed to import this module or run the tests --
the client is created lazily and can be injected for testing.

Failure mapping is deliberate: Anthropic's transient errors (rate limits, 5xx,
connection drops) become TemporaryProviderError so Step Functions retries them,
and permanent errors (auth, bad request) become PermanentProviderError so they
dead-letter. That is what lets a real provider slot into the same reliability
model as the mock.
"""
from __future__ import annotations

import json

from extraction.interface import DocumentExtractor
from shared.exceptions import (
    InvalidAiOutputError,
    PermanentProviderError,
    TemporaryProviderError,
)
from shared.models import Provider

# Ask for strict JSON so the same normalizer that cleans the mock's output can
# clean Claude's. Keys match the aliases the normalizer already understands.
_SYSTEM = (
    "You extract fields from US pay stubs. Reply with ONLY a compact JSON object "
    "and nothing else -- no prose, no markdown fences."
)
_PROMPT = (
    "Extract these fields from the pay stub below. Use null for anything you "
    "cannot find. Return JSON with exactly these keys: employeeName (string), "
    "employerName (string), grossPay (number, no currency symbol), "
    "payPeriodStart (YYYY-MM-DD), payPeriodEnd (YYYY-MM-DD), and confidence "
    "(a number 0-1 for how sure you are overall).\n\nPay stub:\n{text}"
)


class ClaudeExtractor(DocumentExtractor):
    provider = Provider.ANTHROPIC

    def __init__(self, model: str = "claude-opus-4-8", client=None) -> None:
        """
        model:  Anthropic model id. Defaults to Claude Opus 4.8. Pass
                "claude-haiku-4-5" for a cheaper/faster run if you prefer.
        client: inject a pre-built Anthropic client (used by tests); if omitted,
                one is created lazily from ANTHROPIC_API_KEY.
        """
        self.model = model
        self._client = client

    def _get_client(self):
        if self._client is None:
            import anthropic  # imported lazily so local/offline runs don't need it

            self._client = anthropic.Anthropic()
        return self._client

    def extract(self, document_content: bytes) -> dict:
        import anthropic

        text = document_content.decode("utf-8", errors="ignore")

        try:
            response = self._get_client().messages.create(
                model=self.model,
                max_tokens=1024,
                system=_SYSTEM,
                messages=[{"role": "user", "content": _PROMPT.format(text=text)}],
            )
        except (
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            anthropic.APIConnectionError,
        ) as exc:
            # Transient -> worth retrying (Step Functions handles the backoff).
            raise TemporaryProviderError(str(exc)) from exc
        except (
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
            anthropic.BadRequestError,
            anthropic.NotFoundError,
        ) as exc:
            # Permanent -> retrying won't help; dead-letter it.
            raise PermanentProviderError(str(exc)) from exc
        except anthropic.APIStatusError as exc:
            # Anything else: 5xx is transient, the rest permanent.
            if exc.status_code >= 500:
                raise TemporaryProviderError(str(exc)) from exc
            raise PermanentProviderError(str(exc)) from exc

        # A safety refusal means the model declined -- treat as a bad extraction.
        if getattr(response, "stop_reason", None) == "refusal":
            raise PermanentProviderError("model refused the request")

        raw_text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        return _parse_json(raw_text)


def _parse_json(text: str) -> dict:
    """Parse the model's JSON reply, tolerating stray text around it."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} span in case the model added prose.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise InvalidAiOutputError("Claude did not return parseable JSON")
