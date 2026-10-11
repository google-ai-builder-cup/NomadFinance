from __future__ import annotations

from typing import Literal


class GeminiError(Exception):
    """Base class for every failure raised by the Gemini client.

    Callers catch these instead of google-genai's own exceptions, so the SDK can
    change without touching services or endpoints.
    """


class GeminiRequestError(GeminiError):
    """Gemini rejected the request (bad argument, unknown model, auth). Not retried."""


class GeminiRateLimitError(GeminiError):
    """Quota or rate limit hit (HTTP 429) and still hit after all retries.

    `daily` is True when the exhausted quota is a per-day one (it comes back tomorrow, not
    in a minute), read from the quota id Google sends with the 429.
    """

    def __init__(self, message: str, *, daily: bool = False) -> None:
        super().__init__(message)
        self.daily = daily


class GeminiBudgetExhaustedError(GeminiRateLimitError):
    """The call was refused here, before it reached Google, because today's quota is gone.

    Two causes, in `source`: `budget` (this feature has used its share of the model's daily
    requests, so the other features keep theirs) and `google` (Google already answered a
    per-day 429 for the model, so asking again would only waste requests). A subclass of the
    rate-limit error on purpose: every place that already degrades on a full quota (the scam
    explainer's fallback tier, the API's 503) handles this one too. `retry_after_seconds` is
    the time to the next daily reset.
    """

    def __init__(
        self,
        message: str,
        *,
        source: Literal["budget", "google"],
        retry_after_seconds: int,
    ) -> None:
        super().__init__(message, daily=True)
        self.source = source
        self.retry_after_seconds = retry_after_seconds


class GeminiUnavailableError(GeminiError):
    """Gemini server or network error that persisted after all retries."""


class GeminiTimeoutError(GeminiError):
    """Every attempt exceeded the per-call timeout."""


class GeminiResponseError(GeminiError):
    """Gemini answered, but with no content, a blocked prompt, or output that fails the schema."""


def is_retryable(exc: BaseException) -> bool:
    """Whether another attempt could succeed: a busy or slow Gemini, but not a spent day.

    A per-day quota does not come back in a few seconds, so retrying it only spends three
    requests of the quota that is already gone.
    """
    if isinstance(exc, GeminiRateLimitError):
        return not exc.daily
    return isinstance(exc, GeminiUnavailableError | GeminiTimeoutError)
