"""The Coach's question bank: load it, and apply its skip and range rules (NF-FC-001).

Which question comes next, and what to do with an answer, belong to the session and the turn
(NF-FC-008 to -010). They call these functions so the rules live in one place, next to the data.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal, TypeVar

from app.schemas.coach_profile import CoachProfile, Interest, Money, SlotName
from app.schemas.coach_questions import (
    Bounds,
    ChoiceRange,
    CountRange,
    DateWindow,
    MoneyRange,
    Question,
    QuestionBank,
)

_DATA_FILE = Path(__file__).with_name("question_bank.json")

RangeIssue = Literal["too_low", "too_high"]
_T = TypeVar("_T")


@lru_cache(maxsize=1)
def load_question_bank() -> QuestionBank:
    """Read and check `question_bank.json`. Read once; the result is shared, so do not edit it.

    Raises:
        OSError: The file cannot be read.
        pydantic.ValidationError: The file breaks a rule of `QuestionBank`.
    """
    return QuestionBank.model_validate_json(_DATA_FILE.read_text(encoding="utf-8"))


def is_applicable(question: Question, profile: CoachProfile) -> bool:
    """Whether to ask `question`: false when one of its skip rules matches the answers so far.

    An answer not given yet never skips a question. Asking costs a turn, assuming costs a wrong
    plan.
    """
    for rule in question.skip_if:
        answer: object = getattr(profile, rule.slot)
        if answer is not None and rule.field is not None:
            answer = getattr(answer, rule.field)
        if answer is not None and answer == rule.equals:
            return False
    return True


def range_issue(
    bank: QuestionBank, slot: SlotName, value: object, today: date
) -> RangeIssue | None:
    """Whether a valid answer is outside what a worker would usually say.

    A value outside the range is not wrong, only worth checking: the caller asks the
    `out_of_range` follow-up and keeps the value only when the worker confirms it. `value` is
    what `CoachProfile` holds for the slot; `today` is passed in so the result never depends on
    the clock.

    Raises:
        KeyError: `slot` has no question.
        TypeError: `value` is not the kind of value the slot holds.
    """
    expected = bank.question(slot).expected
    if isinstance(expected, ChoiceRange):
        return None
    if isinstance(expected, CountRange):
        return _compare(_as_number(slot, value), expected.bounds)
    if isinstance(expected, DateWindow):
        days = (date.fromisoformat(_as(slot, str, value)) - today).days
        return _compare(days, expected.days)
    if isinstance(expected, MoneyRange):
        money = _as(slot, Money, value)
        amount = money.amount if money.period == "once" else money.per_month()
        scale = bank.monthly_pay_scale[money.currency]
        return _compare(
            amount,
            Bounds(
                low=expected.scale_multiple.low * scale, high=expected.scale_multiple.high * scale
            ),
        )
    interest = _as(slot, Interest, value)
    return _compare(
        interest.rate_percent, expected.month if interest.period == "month" else expected.year
    )


def _compare(number: float, bounds: Bounds) -> RangeIssue | None:
    if number < bounds.low:
        return "too_low"
    if number > bounds.high:
        return "too_high"
    return None


def _as_number(slot: str, value: object) -> int:
    # A bool is an int to Python, but never a head count.
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{slot} holds a whole number, not {type(value).__name__}")
    return value


def _as(slot: str, kind: type[_T], value: object) -> _T:
    if not isinstance(value, kind):
        raise TypeError(f"{slot} holds a {kind.__name__}, not {type(value).__name__}")
    return value
