from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class SendCheckinsResponse(BaseModel):
    """Result of `POST /api/v1/internal/send-coach-checkins` (NF-FC-016). Counts only: no worker."""

    day: date = Field(description="The day the run was for (UTC).")
    plans_found: int = Field(description="Plans in a day 30, 60 or 90 window, before any rule.")
    notified: int = Field(description="Reminders written by this run.")
    already_sent: int = Field(
        description="Found with a reminder already written by an earlier run."
    )
    skipped: int = Field(description="Flag off, reminders off, an older plan, or a bad date.")
    failed: int = Field(description="Left for the retry: a read or write failed.")
    completed_at: datetime
