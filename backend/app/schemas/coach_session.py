"""Session, turn and overview models of the Financial Coach API (NF-FC-002).

These are the contract in `docs/api/v2-coach.md`: the endpoints (NF-FC-008, -009, -010) import
them, and `tests/unit/test_coach_mocks.py` checks that every mock in `docs/mocks/coach/` parses as
one of them. The score and plan models are in `coach_plan.py`; the slots in `coach_profile.py`.
Where a session is stored and for how long: `docs/data-model/collections/coach.md`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, field_validator, model_serializer, model_validator

from app.schemas.coach_plan import CoachScore, PlanId, SnakeId
from app.schemas.coach_profile import CoachProfile, DepartureDate, SlotName, SlotSource
from app.schemas.contract import ReportLanguage

Stage = Literal["intro", "income", "obligations", "debt", "savings", "review", "plan"]
SessionStatus = Literal["active", "completed", "abandoned"]
MessageRole = Literal["user", "coach"]
STAGES: tuple[str, ...] = get_args(Stage)
# From `review` on every question is answered: no next slot, and a score exists.
SCORED_STAGES = ("review", "plan")

MAX_TURN_TEXT_CHARS = 1000
MAX_TRANSCRIPT_MESSAGES = 200


class CoachSessionCreateRequest(BaseModel):
    """Body of `POST /api/v2/coach/sessions`."""

    language: ReportLanguage = Field(
        description="The language a new session starts in. A resumed session keeps its own."
    )
    restart: bool = Field(
        default=False,
        description="Close the active session (as `abandoned`) and start a new one.",
    )


class CoachMessage(BaseModel):
    id: str
    role: MessageRole
    text: str = Field(description="Phone numbers, emails, IDs, accounts and URLs masked.")
    language: ReportLanguage
    at: datetime


class CoachSlot(BaseModel):
    """One answer as the worker sees it: its value, whether they confirmed it, and its source."""

    value: Any = Field(description="Shaped as the slot's field of `CoachProfile`.")
    confirmed: bool
    source: SlotSource


KnownSource = Literal["profile", "contract", "income", "savings", "transfers"]


class CoachKnownItem(BaseModel):
    """One answer the Coach could already fill in, and where it came from."""

    slot: SlotName
    value: Any = Field(description="Shaped as the slot's field of `CoachProfile`.")
    source: KnownSource = Field(
        description="`profile` (sign-up), `contract` (latest analysed contract), `income`, "
        "`savings`, `transfers` (Financial Identity entries)."
    )
    as_of: DepartureDate | None = Field(
        default=None,
        description="The date of the newest entry the figure was worked out from; `null` for the "
        "profile and the contract.",
    )


class CoachKnown(BaseModel):
    """What the Coach already knows about the worker, waiting for them to agree (NF-FC-023)."""

    items: list[CoachKnownItem] = Field(min_length=1, max_length=len(get_args(SlotName)))

    @model_validator(mode="after")
    def _each_value_fits_its_slot(self) -> CoachKnown:
        for item in self.items:
            CoachProfile.model_validate({item.slot: item.value})
        if len({item.slot for item in self.items}) != len(self.items):
            raise ValueError("A slot is offered once.")
        return self


class CoachKnownRequest(BaseModel):
    """Body of `POST /api/v2/coach/sessions/{id}/known`: the offered answers the worker keeps."""

    keep: list[SlotName] = Field(
        max_length=len(get_args(SlotName)),
        description="Slots of `known.items` the worker agrees with. Every other offered answer "
        "is dropped and the coach asks that question as usual. May be empty.",
    )


class CoachSession(BaseModel):
    """One interview (`GET /coach/sessions/{id}`)."""

    id: str
    status: SessionStatus
    stage: Stage
    language: ReportLanguage = Field(description="The language the coach replies in now.")
    slots: dict[SlotName, CoachSlot] = Field(description="Answered slots only.")
    messages: list[CoachMessage] = Field(max_length=MAX_TRANSCRIPT_MESSAGES)
    next_slot: SlotName | None = Field(
        description="The slot the coach asks for next; `null` once the questions are done."
    )
    turn_count: int = Field(ge=0, description="Answers the worker has given.")
    score: CoachScore | None = Field(
        description="From `review` on; `null` before, and when it cannot be worked out yet."
    )
    plan_id: PlanId | None = Field(description="Set exactly when the session is completed.")
    known: CoachKnown | None = Field(
        default=None,
        description="Only while the worker has not yet agreed to what the Coach already knows "
        "(NF-FC-023); left out of the answer otherwise.",
    )
    created_at: datetime
    last_active: datetime

    @model_serializer(mode="wrap")
    def _leave_out_known_when_there_is_none(self, handler: Any) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if data.get("known") is None:
            data.pop("known", None)
        return data

    @model_validator(mode="after")
    def _the_parts_agree(self) -> CoachSession:
        CoachProfile.model_validate({name: slot.value for name, slot in self.slots.items()})
        if (self.next_slot is None) != (self.stage in SCORED_STAGES):
            raise ValueError("`next_slot` is null exactly in the `review` and `plan` stages.")
        if self.score is not None and self.stage not in SCORED_STAGES:
            raise ValueError("The score appears from the `review` stage.")
        if (self.status == "completed") != (self.plan_id is not None):
            raise ValueError("`plan_id` is set exactly when the session is completed.")
        if self.status == "completed" and self.stage != "plan":
            raise ValueError("A completed session is at the `plan` stage.")
        return self


class CoachSessionCreateResponse(CoachSession):
    """Answer of `POST /coach/sessions`: the session, and whether it already existed."""

    resumed: bool = Field(description="True when the worker already had an active session.")


class CoachTurnRequest(BaseModel):
    """Body of `POST /api/v2/coach/sessions/{id}/messages`."""

    text: str | None = Field(
        default=None,
        description="The worker's answer. Omit it to let the coach speak first: the opening "
        "question of a new session, or the current question again after a change of language.",
    )
    language: ReportLanguage

    @field_validator("text")
    @classmethod
    def _text_has_content_and_fits(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("The message is empty.")
        if len(stripped) > MAX_TURN_TEXT_CHARS:
            raise ValueError(f"String should have at most {MAX_TURN_TEXT_CHARS} characters")
        return stripped


class CoachTokenEvent(BaseModel):
    """`data` of an SSE `token` event."""

    text: str = Field(min_length=1)


class CoachSlotUpdateEvent(BaseModel):
    """`data` of an SSE `slot_update` event: a fact the server understood. Final only at `done`."""

    slot: SlotName
    value: Any
    confirmed: bool

    @model_validator(mode="after")
    def _the_value_fits_the_slot(self) -> CoachSlotUpdateEvent:
        CoachProfile.model_validate({self.slot: self.value})
        return self


class CoachDoneEvent(BaseModel):
    """`data` of the SSE `done` event: the turn is complete and saved."""

    message_id: str = Field(description="The coach message that was just stored.")
    stage: Stage
    next_slot: SlotName | None
    turn_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _next_slot_follows_the_stage(self) -> CoachDoneEvent:
        if (self.next_slot is None) != (self.stage in SCORED_STAGES):
            raise ValueError("`next_slot` is null exactly in the `review` and `plan` stages.")
        return self


class CoachPlanRequest(BaseModel):
    """Body of `POST /api/v2/coach/sessions/{id}/plan`."""

    language: ReportLanguage = Field(description="The language of the plan and its PDF.")


class OverviewSession(BaseModel):
    id: str
    stage: Stage
    language: ReportLanguage
    turn_count: int = Field(ge=0)
    last_active: datetime


class OverviewPlan(BaseModel):
    id: PlanId
    created_at: datetime
    score_total: int = Field(ge=0, le=100)
    band: SnakeId
    departure_date: DepartureDate | None = None


class CoachOverview(BaseModel):
    """What the dashboard card needs (`GET /coach/overview`): start, resume or view the plan."""

    session: OverviewSession | None = Field(description="The active session, if there is one.")
    plan: OverviewPlan | None = Field(description="The newest plan, if there is one.")
