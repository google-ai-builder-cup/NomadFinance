from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NarrativeAnswer(BaseModel):
    """Gemini's report text (NF-P3-013); also its `response_schema`."""

    text: str = Field(
        description="The whole report as plain text, paragraphs separated by a blank line."
    )
    activity_text: str = Field(
        default="",
        description=(
            "One short paragraph about the activity the worker shared (Coach check-ins, scam "
            "checks), or an empty string when the profile has none (NF-HR-001)."
        ),
    )


class RecomputeResponse(BaseModel):
    """Response of `POST /api/v1/internal/recompute-fib-profiles`."""

    users_seen: int = Field(description="Users with a document in `users`.")
    recomputed: int = Field(description="Profiles written.")
    skipped_no_data: int = Field(
        description="Users with no activity in the period, or none a metric could use."
    )
    failed: int = Field(description="Users whose previous profile was kept because a step failed.")
    completed_at: datetime


class RefreshProfileResponse(BaseModel):
    """Response of `POST /api/v1/fib/profile/refresh`: one worker's score, on request."""

    status: Literal["recomputed", "fresh", "no_data"] = Field(
        description=(
            "`recomputed`: the profile was just worked out; `fresh`: it was computed within the "
            "last hour, so it was left as it is; `no_data`: nothing logged yet gives a score."
        )
    )
    computed_at: datetime | None = Field(
        default=None, description="When the profile now stored was computed; null for `no_data`."
    )
