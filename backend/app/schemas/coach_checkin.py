from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Milestone = Literal["d30", "d60", "d90"]
# One word for "how is it going" shared by the two money questions; the pay question has its own.
PaceAnswer = Literal["on_track", "behind", "not_yet"]
PayAnswer = Literal["full_on_time", "late_or_less", "not_paid"]


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


class CheckinAnswers(BaseModel):
    """The three questions of a check-in (NF-FC-022).

    Fixed choices only, so nothing a worker typed is stored and the screen can translate every
    answer. The wording of each question is the screen's; the API keeps only the choice.
    """

    model_config = ConfigDict(extra="forbid")

    remittance: PaceAnswer = Field(description="Money sent home, compared with the plan.")
    savings: PaceAnswer = Field(description="Money saved, compared with the plan.")
    pay: PayAnswer = Field(description="Whether the employer pays in full and on time.")


class CheckinAnswerRequest(BaseModel):
    """Body of `PUT /api/v2/coach/plans/{id}/checkins/{milestone}`."""

    model_config = ConfigDict(extra="forbid")

    answers: CheckinAnswers


class CheckinAnswerResponse(BaseModel):
    """What is stored for the milestone: the worker's first answers, even when they sent more."""

    plan_id: str
    milestone: Milestone
    answers: CheckinAnswers
    answered_at: datetime
    already_answered: bool = Field(
        description="True when the milestone was answered before; the stored answers are returned."
    )
