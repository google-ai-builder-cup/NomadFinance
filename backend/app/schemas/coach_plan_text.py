"""What the model writes for a plan: sentences only, never figures (NF-FC-012).

Every figure of a plan is worked out in code (`plan_figures.py`); the model returns this, and
`plan_validator.py` checks that the numbers in its sentences are numbers it was given. No
`extra="forbid"`: Gemini's response schema does not accept `additionalProperties`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WeekText(BaseModel):
    week: int = Field(description="1 to 13, in order.")
    title: str
    actions: list[str] = Field(description="One to four short actions for the week.")


class NoteText(BaseModel):
    id: str = Field(description="The id of the warning or checklist item this words.")
    text: str


class PlanText(BaseModel):
    summary: str = Field(description="Two or three sentences.")
    weeks: list[WeekText] = Field(description="Exactly 13 entries, weeks 1 to 13.")
    warnings: list[NoteText] = Field(description="One for each warning asked for, by id.")
    checklist: list[NoteText] = Field(description="One for each checklist item asked for, by id.")
