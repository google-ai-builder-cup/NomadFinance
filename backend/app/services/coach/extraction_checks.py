"""From what the extraction model read to what the interview keeps (NF-FC-010).

The model (`coach/extract.v1`) only proposes. Every proposal is checked here, with no model,
against the worker's own words before it becomes an answer or a question to ask again:

- the quoted evidence must really be in the message;
- a number must be a number the worker wrote (times thousands, lakh, million or crore);
- the money and the period must have been *named*, in this message or a recent one, and are
  never taken from the country or the language: a missing one is a follow-up, not a guess;
- an answer outside what workers usually say is kept but unconfirmed, and asked about;
- an answer the model is unsure of is kept unconfirmed and checked with the worker.

So no answer reaches the interview that the worker did not state.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, get_args

from pydantic import ValidationError

from app.schemas.coach_extraction import (
    ExtractedInterest,
    ExtractedMoney,
    SlotCandidate,
    SlotExtraction,
)
from app.schemas.coach_profile import (
    MAX_DEPENDENTS,
    CoachProfile,
    Currency,
    SlotName,
    parse_slot_value,
)
from app.schemas.coach_questions import FollowUpTrigger, QuestionBank
from app.services.coach.extraction_cues import (
    country_stated,
    currency_stated,
    has_digits,
    money_named,
    normal,
    number_stated,
    numbers_in,
    percent_stated,
    period_stated,
    zero_stated,
)
from app.services.coach.question_bank import is_applicable, range_issue
from app.services.coach.session_types import SlotUpdate
from app.services.coach.turn_types import Clarification, Understanding

logger = logging.getLogger(__name__)

# At or above this a plain, in-range answer is kept as confirmed.
CONFIRM_AT = 0.8
# Below this the reading is not used at all; between the two it is kept and checked.
ASK_AT = 0.5
FLOW_SLOTS = frozenset({"monthly_salary", "remittance_target"})
MONEY_SLOTS = frozenset(
    {"monthly_salary", "remittance_target", "recruitment_fee_paid", "debt_outstanding", "savings"}
)
CURRENCIES = frozenset(get_args(Currency))
HOST_CURRENCY = {"SG": "SGD", "KR": "KRW", "MY": "MYR", "JP": "JPY", "HK": "HKD", "AU": "AUD"}
# How many of the worker's earlier messages may carry a money or a period said a moment ago.
EARLIER_MESSAGES = 2


@dataclass(frozen=True)
class ReadingContext:
    """What the checks need to know about the session and the message."""

    bank: QuestionBank
    slots: Mapping[str, Mapping[str, Any]]  # the stored records: value, confirmed, ...
    declined: Collection[str]
    asking: SlotName | None  # the question the worker is answering
    message: str  # as the model saw it (already masked)
    earlier: Sequence[str]  # the worker's earlier messages, newest first
    today: date


@dataclass(frozen=True)
class _Built:
    value: Any = None
    problem: FollowUpTrigger | None = None
    # A figure with no digits or number words to check it against: kept, but asked about.
    unverified: bool = False


def _profile(values: Mapping[str, Any]) -> CoachProfile:
    return CoachProfile.model_validate(dict(values))


def _texts(ctx: ReadingContext) -> list[str]:
    return [ctx.message, *ctx.earlier[:EARLIER_MESSAGES]]


def _zero_currency(ctx: ReadingContext) -> str:
    """A zero needs no money, but a stored amount needs one: the worker's own, else the host's."""
    for record in ctx.slots.values():
        value = record.get("value")
        if record.get("confirmed") and isinstance(value, dict) and value.get("currency"):
            return str(value["currency"])
    destination = ctx.slots.get("destination_country", {}).get("value")
    return HOST_CURRENCY.get(str(destination), "")


def _figure(amount: float, evidence: str) -> _Built:
    """Whether `amount` is a figure the quoted words state: a number in them, or a word for none.

    Returns an empty `_Built` when it is, a refusal when the words hold another number, and an
    `unverified` one when the words hold no number to check it against (then it is only asked
    about, never kept as the worker's confirmed answer).
    """
    if amount == 0:
        return _Built() if zero_stated(evidence) else _Built(unverified=True)
    if not has_digits(evidence):
        return _Built(unverified=True)
    return _Built() if number_stated(amount, evidence) else _Built(problem="not_understood")


def _money(slot: str, money: ExtractedMoney | None, ctx: ReadingContext, evidence: str) -> _Built:
    if money is None or money.amount is None:
        return _Built(problem="not_understood")
    amount = money.amount
    figure = _figure(amount, evidence)
    if figure.problem is not None:
        return figure
    unverified = figure.unverified
    code = (money.currency or "").upper()
    if code not in CURRENCIES or not currency_stated(code, _texts(ctx)):
        code = _zero_currency(ctx) if amount == 0 else ""
    if not code:
        return _Built(problem="missing_currency")
    period = "once"
    if slot in FLOW_SLOTS:
        said = money.period
        if said not in ("month", "week", "year") or not period_stated(said, _texts(ctx)):
            return _Built(problem="unclear_period")
        period = said
    value = {"amount": amount, "currency": code, "period": period}
    return _checked(slot, value, unverified)


def _interest(interest: ExtractedInterest | None, ctx: ReadingContext, evidence: str) -> _Built:
    if interest is None or interest.rate_percent is None:
        return _Built(problem="not_understood")
    rate = interest.rate_percent
    figure = _figure(rate, evidence)
    if figure.problem is not None:
        return figure
    # A rate is a number beside a percent or an interest; any other number is not one.
    unverified = figure.unverified or not percent_stated(evidence)
    said = interest.period
    if said not in ("month", "year") or not period_stated(said, _texts(ctx)):
        return _Built(problem="unclear_period")
    return _checked("debt_interest", {"rate_percent": rate, "period": said}, unverified)


def _checked(slot: str, value: Any, unverified: bool = False) -> _Built:
    try:
        parse_slot_value(slot, value)
    except ValidationError:
        return _Built(problem="not_understood")
    return _Built(value=value, unverified=unverified)


def _count(candidate: SlotCandidate, evidence: str) -> _Built:
    count = candidate.count
    if count is None or not 0 <= count <= MAX_DEPENDENTS:
        return _Built(problem="not_understood")
    # "Two people depend on me" is a number word; a count the words never state (a list of
    # relatives) is only asked about.
    figure = _figure(float(count), evidence)
    if figure.problem is not None:
        return figure
    # A number beside a percent or an amount of money is not a number of people.
    beside = percent_stated(evidence) or money_named(evidence)
    return _checked("dependents", count, figure.unverified or beside)


def _date(candidate: SlotCandidate, evidence: str) -> _Built:
    if candidate.date is None:
        return _Built(problem="not_understood")
    try:
        day = date.fromisoformat(candidate.date)
    except ValueError:
        return _Built(problem="not_understood")
    written = numbers_in(evidence, words=False)
    if not written:
        # "next month": no digit to compare, so the date is asked about, not kept.
        return _checked("departure_date", day.isoformat(), True)
    if not {float(day.day), float(day.year), float(day.month)} & set(written):
        return _Built(problem="not_understood")
    years = {int(y) for y in _four_digit_years(evidence)}
    if years and day.year not in years:
        return _Built(problem="not_understood")
    # Only a year the worker wrote makes the whole date theirs; "20 January" is asked about.
    return _checked("departure_date", day.isoformat(), not years)


def _four_digit_years(text: str) -> list[str]:
    return re.findall(r"(?<!\d)(20\d{2})(?!\d)", normal(text))


def _value(slot: str, candidate: SlotCandidate, ctx: ReadingContext, evidence: str) -> _Built:
    if slot == "destination_country":
        # A country is only what the worker named, not what their language or route suggests.
        if candidate.country and country_stated(candidate.country, ctx.message):
            return _checked(slot, candidate.country)
        return _Built("", "not_understood")
    if slot == "job_type":
        return (
            _checked(slot, candidate.job_type)
            if candidate.job_type
            else _Built("", "not_understood")
        )
    if slot == "bank_or_wallet":
        return (
            _checked(slot, candidate.account) if candidate.account else _Built("", "not_understood")
        )
    if slot == "departure_date":
        return _date(candidate, evidence)
    if slot == "dependents":
        return _count(candidate, evidence)
    if slot == "debt_interest":
        return _interest(candidate.interest, ctx, evidence)
    return _money(slot, candidate.money, ctx, evidence)


def _has_value(candidate: SlotCandidate) -> bool:
    return any(
        part is not None
        for part in (
            candidate.country,
            candidate.job_type,
            candidate.date,
            candidate.count,
            candidate.money,
            candidate.interest,
            candidate.account,
        )
    )


def _range_issue(ctx: ReadingContext, slot: SlotName, value: Any) -> bool:
    try:
        return range_issue(ctx.bank, slot, parse_slot_value(slot, value), ctx.today) is not None
    except (KeyError, TypeError, ValueError):
        return False


def _trigger(bank: QuestionBank, slot: SlotName, wanted: FollowUpTrigger) -> FollowUpTrigger:
    """`wanted`, or `not_understood` when the bank has no such follow-up for this slot."""
    return wanted if wanted in bank.triggers_for(bank.question(slot)) else "not_understood"


@dataclass(frozen=True)
class _Outcome:
    update: SlotUpdate | None = None
    clarify: Clarification | None = None


def _read(
    candidate: SlotCandidate, slot: SlotName, record: Mapping[str, Any] | None, ctx: ReadingContext
) -> _Outcome:
    evidence = normal(candidate.evidence)
    if not evidence or evidence not in normal(ctx.message):
        # What the model quoted is not what the worker wrote: nothing is taken from it.
        logger.info("coach_extract_dropped slot=%s reason=evidence", slot)
        return _Outcome()
    if candidate.confidence < ASK_AT:
        return _Outcome(clarify=Clarification(slot, "not_understood"))
    if candidate.confirms_pending and record is not None and not _has_value(candidate):
        # The worker agrees to the value we asked them to check: that value, now confirmed.
        confidence = max(float(record.get("confidence", 0.0)), candidate.confidence)
        return _Outcome(update=SlotUpdate(slot, record["value"], confidence, True))
    built = _value(slot, candidate, ctx, candidate.evidence)
    if built.problem is not None:
        logger.info("coach_extract_followup slot=%s trigger=%s", slot, built.problem)
        return _Outcome(clarify=Clarification(slot, _trigger(ctx.bank, slot, built.problem)))
    outside = _range_issue(ctx, slot, built.value)
    confirmed = candidate.confidence >= CONFIRM_AT and not outside and not built.unverified
    update = SlotUpdate(slot, built.value, candidate.confidence, confirmed)
    if confirmed:
        return _Outcome(update=update)
    trigger: FollowUpTrigger = "out_of_range" if outside else "low_confidence"
    return _Outcome(update=update, clarify=Clarification(slot, _trigger(ctx.bank, slot, trigger)))


def _best(candidates: Sequence[SlotCandidate]) -> dict[str, SlotCandidate]:
    """One candidate per slot: the sure one, and one with a value over one that only agrees."""
    best: dict[str, SlotCandidate] = {}
    for candidate in candidates:
        held = best.get(candidate.slot)
        if held is None or (_has_value(candidate), candidate.confidence) > (
            _has_value(held),
            held.confidence,
        ):
            best[candidate.slot] = candidate
    return best


def _declined(ctx: ReadingContext) -> Understanding:
    """The worker will not or cannot answer. Only the optional question may be left unanswered."""
    if ctx.asking is None:
        return Understanding()
    if not ctx.bank.question(ctx.asking).required and ctx.asking not in ctx.declined:
        return Understanding(declined=[ctx.asking])
    return Understanding(clarify=Clarification(ctx.asking, "not_understood"))


def interpret(extraction: SlotExtraction, ctx: ReadingContext) -> Understanding:
    """The updates to store, the optional slot declined, and the follow-up to ask, if any."""
    if extraction.message_kind in ("question", "other"):
        return Understanding()
    if extraction.message_kind == "decline":
        return _declined(ctx)
    best = _best(extraction.candidates)
    working: dict[str, Any] = {name: record["value"] for name, record in ctx.slots.items()}
    updates: list[SlotUpdate] = []
    follow_ups: list[Clarification] = []
    # In the bank's order, so a skip rule sees this message's earlier answers (no debt, no
    # interest question).
    for question in ctx.bank.questions:
        candidate = best.get(question.slot)
        record = ctx.slots.get(question.slot)
        if candidate is None or (record is not None and record["confirmed"]):
            continue
        if not is_applicable(question, _profile(working)):
            continue
        outcome = _read(candidate, question.slot, record, ctx)
        if outcome.update is not None:
            updates.append(outcome.update)
            working[question.slot] = outcome.update.value
        if outcome.clarify is not None:
            follow_ups.append(outcome.clarify)
    asked = [f for f in follow_ups if f.slot == ctx.asking]
    clarify = asked[0] if asked else (follow_ups[0] if follow_ups else None)
    if clarify is None and not updates and ctx.asking is not None:
        clarify = Clarification(ctx.asking, "not_understood")
    return Understanding(updates=updates, clarify=clarify)
