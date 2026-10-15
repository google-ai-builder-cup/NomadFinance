from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PublicStatsResponse(BaseModel):
    """`GET /api/v1/public/stats`: totals across the whole platform, counts only.

    A field is `null` when that total could not be read, so the landing page leaves the figure
    out instead of showing a zero that means "unknown".
    """

    workers: int | None = Field(None, ge=0, description="Signed-up workers.")
    contracts_checked: int | None = Field(None, ge=0, description="Contracts analysed.")
    radar_reports: int | None = Field(
        None, ge=0, description="Radar reports, hidden ones left out."
    )
    alerts_generated: int | None = Field(None, ge=0, description="Corridor alerts raised so far.")
    scam_messages_checked: int | None = Field(None, ge=0, description="Messages checked.")
    scams_flagged: int | None = Field(None, ge=0, description="Of those, judged to be scams.")
    generated_at: datetime
