from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """One rejected field of a request (422 only)."""

    field: str = Field(description="Dotted path to the field, e.g. `body.amount`.")
    issue: str = Field(description="Why it was rejected. Never the value that was sent.")


class ErrorEnvelope(BaseModel):
    """Body of every error response under `/api/v2` (docs/api/v2-conventions.md)."""

    code: str = Field(
        description="Stable snake_case identifier; clients branch and translate on it."
    )
    message: str = Field(description="English fallback text for logs and unknown codes.")
    request_id: str = Field(description="Same value as the `X-Request-ID` response header.")
    details: list[ErrorDetail] | None = Field(
        default=None, description="Present only on `validation_failed`."
    )
