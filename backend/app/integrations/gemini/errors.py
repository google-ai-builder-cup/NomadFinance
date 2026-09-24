from __future__ import annotations


class GeminiError(Exception):
    """Base class for every failure raised by the Gemini client.

    Callers catch these instead of google-genai's own exceptions, so the SDK can
    change without touching services or endpoints.
    """


class GeminiRequestError(GeminiError):
    """Gemini rejected the request (bad argument, unknown model, auth). Not retried."""


class GeminiRateLimitError(GeminiError):
    """Quota or rate limit hit (HTTP 429) and still hit after all retries."""


class GeminiUnavailableError(GeminiError):
    """Gemini server or network error that persisted after all retries."""


class GeminiTimeoutError(GeminiError):
    """Every attempt exceeded the per-call timeout."""


class GeminiResponseError(GeminiError):
    """Gemini answered, but with no content, a blocked prompt, or output that fails the schema."""
