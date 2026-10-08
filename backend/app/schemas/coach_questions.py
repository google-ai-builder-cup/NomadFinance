"""The Financial Coach's question bank file (NF-FC-001): `app/services/coach/question_bank.json`.

A person edits that file, so these models check everything a slip could break: a missing or
duplicated slot, a question in the wrong order, a skip rule that points at an answer not yet
known, a follow-up that is missing. `app.services.coach.question_bank` loads it and applies the
rules; the interview itself is NF-FC-008 to -010.
"""

from __future__ import annotations

from typing import Annotated, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from app.schemas.coach_profile import (
    SLOT_NAMES,
    Currency,
    Interest,
    Money,
    SlotName,
    parse_slot_value,
)

QuestionStage = Literal["intro", "income", "obligations", "debt", "savings"]
# The order the interview walks through them (design 4.3); `review` and `plan` hold no questions.
STAGES: tuple[str, ...] = get_args(QuestionStage)

# Why the coach asks again. "not_understood": the answer held nothing usable. "low_confidence":
# the extraction was unsure, so read it back. "out_of_range": outside the expected range, so
# check it. "missing_currency" and "unclear_period" are the two gaps in an amount or a rate.
FollowUpTrigger = Literal[
    "not_understood", "low_confidence", "out_of_range", "missing_currency", "unclear_period"
]
SlotKind = Literal["choice", "date_window", "count", "money", "rate"]

# One line of plain words, written for a worker who may read the language as a second one.
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=300)]

# Which kind of answer each slot holds, and which money slots are a flow (an amount for a
# period). The file must agree, so a copy-paste slip cannot give a count a currency range.
_KIND: dict[str, SlotKind] = {
    "destination_country": "choice",
    "job_type": "choice",
    "departure_date": "date_window",
    "monthly_salary": "money",
    "dependents": "count",
    "remittance_target": "money",
    "recruitment_fee_paid": "money",
    "debt_outstanding": "money",
    "debt_interest": "rate",
    "savings": "money",
    "bank_or_wallet": "choice",
}
_FLOW_SLOTS = frozenset({"monthly_salary", "remittance_target"})
_TRIGGERS: dict[SlotKind, tuple[FollowUpTrigger, ...]] = {
    "choice": ("not_understood", "low_confidence"),
    "date_window": ("not_understood", "low_confidence", "out_of_range"),
    "count": ("not_understood", "low_confidence", "out_of_range"),
    "money": ("not_understood", "low_confidence", "out_of_range", "missing_currency"),
    "rate": ("not_understood", "low_confidence", "out_of_range", "unclear_period"),
}
_SKIP_FIELDS: dict[SlotKind, frozenset[str]] = {
    "money": frozenset(Money.model_fields),
    "rate": frozenset(Interest.model_fields),
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Bounds(_Strict):
    """Both ends are inside the expected range."""

    low: float
    high: float

    @model_validator(mode="after")
    def _low_is_below_high(self) -> Bounds:
        if self.low >= self.high:
            raise ValueError("`low` must be below `high`.")
        return self


class ChoiceRange(_Strict):
    kind: Literal["choice"]
    options: list[str] = Field(min_length=2)


class CountRange(_Strict):
    kind: Literal["count"]
    bounds: Bounds


class DateWindow(_Strict):
    kind: Literal["date_window"]
    # Days from today: negative is the past. A date outside the window is checked, not refused.
    days: Bounds


class MoneyRange(_Strict):
    kind: Literal["money"]
    # An amount for a period (pay, a monthly target) is compared per month; a total as it is.
    flow: bool
    # Multiples of `monthly_pay_scale` for the currency, so one table serves every money slot.
    scale_multiple: Bounds

    @model_validator(mode="after")
    def _is_not_negative(self) -> MoneyRange:
        if self.scale_multiple.low < 0:
            raise ValueError("An amount cannot be below zero.")
        return self


class RateRange(_Strict):
    kind: Literal["rate"]
    month: Bounds
    year: Bounds


ExpectedRange = Annotated[
    ChoiceRange | CountRange | DateWindow | MoneyRange | RateRange, Field(discriminator="kind")
]


class FollowUp(_Strict):
    trigger: FollowUpTrigger
    prompt_en: Text


class SkipRule(_Strict):
    """Skip the question when the named answer equals `equals` (`field` picks a part of it).

    A question whose answer is not known yet is never skipped: asking is the safe side.
    """

    slot: SlotName
    field: str | None = None
    equals: bool | int | float | str


class Question(_Strict):
    slot: SlotName
    stage: QuestionStage
    prompt_en: Text
    why_en: Text
    # Only the departure date can be left out: without it there are no check-in reminders.
    required: bool = True
    expected: ExpectedRange
    # Any one matching rule skips the question.
    skip_if: list[SkipRule] = Field(default_factory=list)
    # Wording specific to this question; anything not listed here uses the bank's default.
    follow_ups: list[FollowUp] = Field(default_factory=list)


class QuestionBank(_Strict):
    version: int = Field(ge=1)
    curator: str = Field(min_length=2)
    # What the scale numbers mean and what they are not; it travels with the numbers.
    scale_note: Text
    monthly_pay_scale: dict[Currency, float]
    follow_up_defaults: dict[SlotKind, list[FollowUp]]
    questions: list[Question]

    def question(self, slot: str) -> Question:
        """The question that fills `slot`.

        Raises:
            KeyError: `slot` has no question.
        """
        for question in self.questions:
            if question.slot == slot:
                return question
        raise KeyError(slot)

    def follow_up(self, slot: str, trigger: FollowUpTrigger) -> FollowUp:
        """The follow-up for `slot`: its own wording, or else the default for its kind.

        Raises:
            KeyError: `slot` has no question, or the trigger does not apply to it.
        """
        question = self.question(slot)
        for candidate in [*question.follow_ups, *self.follow_up_defaults[question.expected.kind]]:
            if candidate.trigger == trigger and trigger in self.triggers_for(question):
                return candidate
        raise KeyError((slot, trigger))

    def triggers_for(self, question: Question) -> tuple[FollowUpTrigger, ...]:
        """The reasons the coach may have to ask `question` again."""
        triggers = _TRIGGERS[question.expected.kind]
        flow = isinstance(question.expected, MoneyRange) and question.expected.flow
        return (*triggers, "unclear_period") if flow else triggers

    @model_validator(mode="after")
    def _covers_every_slot_once_in_order(self) -> QuestionBank:
        slots = [question.slot for question in self.questions]
        if sorted(slots) != sorted(SLOT_NAMES):
            raise ValueError(f"The bank must ask each of {sorted(SLOT_NAMES)} exactly once.")
        stage_order = [STAGES.index(question.stage) for question in self.questions]
        if stage_order != sorted(stage_order) or set(stage_order) != set(range(len(STAGES))):
            raise ValueError(f"Questions must follow the stages {list(STAGES)}, none left empty.")
        if set(self.monthly_pay_scale) != set(get_args(Currency)):
            raise ValueError("`monthly_pay_scale` needs exactly one entry per currency.")
        if any(scale <= 0 for scale in self.monthly_pay_scale.values()):
            raise ValueError("Every scale number must be above zero.")
        return self

    @model_validator(mode="after")
    def _each_question_fits_its_slot(self) -> QuestionBank:
        for question in self.questions:
            expected = question.expected
            if expected.kind != _KIND[question.slot]:
                raise ValueError(f"{question.slot}: expected a `{_KIND[question.slot]}` range.")
            if isinstance(expected, MoneyRange) and expected.flow != (question.slot in _FLOW_SLOTS):
                raise ValueError(f"{question.slot}: `flow` is wrong for this slot.")
            if isinstance(expected, ChoiceRange):
                self._options_are_real(question.slot, expected.options)
            self._follow_ups_are_complete(question)
        return self

    @staticmethod
    def _options_are_real(slot: str, options: list[str]) -> None:
        for option in options:
            try:
                parse_slot_value(slot, option)
            except ValidationError:
                raise ValueError(f"{slot}: {option!r} is not a value of this slot.") from None

    def _follow_ups_are_complete(self, question: Question) -> None:
        kind = question.expected.kind
        wanted = set(self.triggers_for(question))
        for source in (question.follow_ups, self.follow_up_defaults.get(kind, [])):
            triggers = [follow_up.trigger for follow_up in source]
            if len(triggers) != len(set(triggers)):
                raise ValueError(f"{question.slot}: a follow-up is listed twice.")
        own = {follow_up.trigger for follow_up in question.follow_ups}
        default = {follow_up.trigger for follow_up in self.follow_up_defaults.get(kind, [])}
        if own - wanted:
            raise ValueError(f"{question.slot}: {sorted(own - wanted)} do not apply here.")
        if wanted - own - default:
            raise ValueError(f"{question.slot}: no follow-up for {sorted(wanted - own - default)}.")

    @model_validator(mode="after")
    def _skip_rules_point_at_known_answers(self) -> QuestionBank:
        position = {question.slot: index for index, question in enumerate(self.questions)}
        for index, question in enumerate(self.questions):
            for rule in question.skip_if:
                if position[rule.slot] >= index:
                    raise ValueError(f"{question.slot}: skips on {rule.slot}, asked later.")
                self._skip_rule_fits(question.slot, rule)
        return self

    @staticmethod
    def _skip_rule_fits(slot: str, rule: SkipRule) -> None:
        kind = _KIND[rule.slot]
        allowed = _SKIP_FIELDS.get(kind)
        if allowed is None and rule.field is not None:
            raise ValueError(f"{slot}: {rule.slot} has no parts to name.")
        if allowed is not None and rule.field not in allowed:
            raise ValueError(f"{slot}: `field` must be one of {sorted(allowed)}.")
