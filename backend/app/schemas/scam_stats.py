from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AggregateScamStatsResponse(BaseModel):
    """Result of `POST /api/v1/internal/aggregate-scam-stats` (NF-SA-022)."""

    weeks: list[str]
    checks_counted: int
    documents_written: int
    completed_at: datetime
