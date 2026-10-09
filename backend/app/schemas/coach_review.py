"""What the review-step model returns for one worker message (NF-FC-020).

At the `review` stage the coach has listed what it understood and asked whether it is right. The
worker's reply is read into one of three things: a yes, a wish to change an answer (and which),
or something else. Like the slot reading, this is the model's raw opinion, checked by
`app/services/coach/review_reader.py` before anything moves. No `extra="forbid"`: Gemini's response
schema does not accept `additionalProperties`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.coach_profile import SlotName

ReviewAction = Literal["confirm", "change", "other"]


class ReviewReading(BaseModel):
    action: ReviewAction = Field(
        description="confirm: the worker says every answer listed is right and wants to go on. "
        "change: the worker wants to change something. other: a question, small talk, or "
        "anything that is neither."
    )
    slot: SlotName | None = Field(
        default=None,
        description="With action change: the one answer the worker wants to change, if the "
        "message says which. None if it does not say which, or for any other action.",
    )
    evidence: str = Field(
        default="",
        description="The exact words of the worker's message that show the action, copied "
        "unchanged. Empty for other.",
    )
    confidence: float = Field(default=0.0, ge=0, le=1)
