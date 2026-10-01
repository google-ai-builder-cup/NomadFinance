from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NarrativeAnswer(BaseModel):
    """Gemini's report text (NF-P3-013); also its `response_schema`."""

    text: str = Field(
        description="The whole report as plain text, paragraphs separated by a blank line."
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
