"""The checks between the extraction model and the interview (NF-FC-010).

The model is a hand-written answer in every test: what is tested is what the code does with a
reading, including a reading that is wrong, unsure or invented.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.coach_extraction import (
    ExtractedInterest,
    ExtractedMoney,
    SlotCandidate,
    SlotExtraction,
)
from app.services.coach.extraction_checks import ReadingContext, interpret
from app.services.coach.question_bank import load_question_bank

BANK = load_question_bank()
TODAY = date(2026, 10, 1)


def ctx(
    message: str,
    *,
    asking: str | None = None,
    slots: dict[str, dict[str, Any]] | None = None,
    declined: list[str] | None = None,
    earlier: list[str] | None = None,
) -> ReadingContext:
    return ReadingContext(
        bank=BANK,
        slots=slots or {},
        declined=declined or [],
        asking=asking,  # type: ignore[arg-type]
        message=message,
        earlier=earlier or [],
        today=TODAY,
    )


def money(amount: float | None, currency: str | None, period: str | None) -> ExtractedMoney:
    return ExtractedMoney(amount=amount, currency=currency, period=period)  # type: ignore[arg-type]


def cand(slot: str, evidence: str, confidence: float = 0.95, **fields: Any) -> SlotCandidate:
    return SlotCandidate(slot=slot, evidence=evidence, confidence=confidence, **fields)  # type: ignore[arg-type]


def read(kind: str, *candidates: SlotCandidate) -> SlotExtraction:
    return SlotExtraction(message_kind=kind, candidates=list(candidates))  # type: ignore[arg-type]


def stored(value: Any, *, confirmed: bool, confidence: float = 0.9) -> dict[str, Any]:
    return {"value": value, "confirmed": confirmed, "confidence": confidence}


SALARY = {"amount": 2400.0, "currency": "SGD", "period": "month"}
MSG = "I will earn 2,400 Singapore dollars a month."


def salary(**changes: Any) -> SlotCandidate:
    return cand(
        "monthly_salary",
        "2,400 Singapore dollars a month",
        money=money(2400, "SGD", "month"),
        **changes,
    )


# --- a plain answer ----------------------------------------------------------------------------


def test_a_plain_sure_answer_is_kept_as_confirmed_with_no_follow_up() -> None:
    result = interpret(read("answer", salary()), ctx(MSG, asking="monthly_salary"))

    assert [(u.slot, u.value, u.confirmed) for u in result.updates] == [
        ("monthly_salary", SALARY, True)
    ]
    assert result.clarify is None and list(result.declined) == []


def test_a_message_can_answer_several_slots_at_once() -> None:
    message = "I am going to Singapore to work in construction."
    result = interpret(
        read(
            "answer",
            cand("destination_country", "going to Singapore", country="SG"),
            cand("job_type", "work in construction", job_type="construction_worker"),
        ),
        ctx(message, asking="destination_country"),
    )

    assert {u.slot: u.value for u in result.updates} == {
        "destination_country": "SG",
        "job_type": "construction_worker",
    }
    assert all(u.confirmed for u in result.updates)


# --- nothing is taken that the worker did not write -------------------------------------------


def test_evidence_that_is_not_in_the_message_drops_the_answer() -> None:
    reading = read(
        "answer", cand("monthly_salary", "3,000 dollars a month", money=money(3000, "SGD", "month"))
    )

    result = interpret(reading, ctx(MSG, asking="monthly_salary"))

    assert result.updates == []
    assert result.clarify is not None and result.clarify.trigger == "not_understood"


def test_a_number_the_worker_did_not_write_is_refused() -> None:
    reading = read(
        "answer",
        cand(
            "monthly_salary", "2,400 Singapore dollars a month", money=money(2600, "SGD", "month")
        ),
    )

    result = interpret(reading, ctx(MSG, asking="monthly_salary"))

    assert result.updates == []
    assert result.clarify is not None and result.clarify.slot == "monthly_salary"


@pytest.mark.parametrize(
    ("message", "amount", "currency", "slot", "evidence"),
    [
        (
            "Gaji saya 1.700 ringgit per bulan.",
            1700,
            "MYR",
            "monthly_salary",
            "1.700 ringgit per bulan",
        ),
        (
            "Saya bayar 12 juta rupiah ke calo.",
            12_000_000,
            "IDR",
            "recruitment_fee_paid",
            "12 juta rupiah",
        ),
        ("He owes 1.5 lakh rupees.", 150_000, "INR", "debt_outstanding", "1.5 lakh rupees"),
        ("मेरे पास ६२,००० रुपये की बचत है।", 62_000, "INR", "savings", "६२,००० रुपये"),
        ("I have 50k yen saved.", 50_000, "JPY", "savings", "50k yen"),
    ],
)
def test_a_number_is_read_in_the_ways_workers_write_it(
    message: str, amount: float, currency: str, slot: str, evidence: str
) -> None:
    period = "month" if slot == "monthly_salary" else "once"
    candidate = cand(slot, evidence, money=money(amount, currency, period))
    if slot == "monthly_salary":
        message_with_period = message
    else:
        message_with_period = message

    result = interpret(read("answer", candidate), ctx(message_with_period, asking=slot))

    assert [u.slot for u in result.updates] == [slot], result
    assert result.updates[0].value["amount"] == amount


def test_a_figure_with_no_digit_to_check_it_against_is_kept_but_asked_about() -> None:
    message = "I owe about doscientos mil pesos."
    reading = read(
        "answer",
        cand("debt_outstanding", "doscientos mil pesos", money=money(200_000, "PHP", "once")),
    )

    result = interpret(reading, ctx(message, asking="debt_outstanding"))

    assert [(u.slot, u.confirmed) for u in result.updates] == [("debt_outstanding", False)]
    assert result.clarify is not None and result.clarify.trigger == "low_confidence"


def test_a_number_word_is_enough_for_a_small_count_but_a_wrong_digit_is_not() -> None:
    word = interpret(
        read("answer", cand("dependents", "Two people depend on me", count=2)),
        ctx("Two people depend on me: my wife and my mother.", asking="dependents"),
    )
    wrong = interpret(
        read("answer", cand("dependents", "3 months", count=3)),
        ctx("I have 5 months before I leave.", asking="dependents"),
    )

    assert [(u.slot, u.value) for u in word.updates] == [("dependents", 2)]
    assert wrong.updates == []


def test_a_word_number_is_a_number_for_a_percent() -> None:
    reading = read(
        "answer",
        cand(
            "debt_interest",
            "Five percent po kada buwan",
            interest=ExtractedInterest(rate_percent=5, period="month"),
        ),
    )

    result = interpret(reading, ctx("Five percent po kada buwan ang tubo.", asking="debt_interest"))

    assert [u.value for u in result.updates] == [{"rate_percent": 5.0, "period": "month"}]


# --- the money and the period are never guessed -----------------------------------------------


def test_a_money_the_worker_did_not_name_is_a_follow_up_not_a_guess() -> None:
    message = "168,000 po ang sahod ko kada buwan."
    reading = read(
        "answer",
        cand(
            "monthly_salary",
            "168,000 po ang sahod ko kada buwan",
            money=money(168000, "JPY", "month"),
        ),
    )

    result = interpret(reading, ctx(message, asking="monthly_salary"))

    assert result.updates == []
    assert (result.clarify.slot, result.clarify.trigger) == ("monthly_salary", "missing_currency")  # type: ignore[union-attr]


def test_dollars_alone_are_not_a_money_but_dollars_named_earlier_are() -> None:
    message = "Sorry, that is 450 dollars every week."
    reading = read(
        "answer", cand("monthly_salary", "450 dollars every week", money=money(450, "SGD", "week"))
    )

    alone = interpret(reading, ctx(message, asking="monthly_salary"))
    carried = interpret(
        reading,
        ctx(message, asking="monthly_salary", earlier=["I will earn 450 Singapore dollars."]),
    )

    assert alone.clarify is not None and alone.clarify.trigger == "missing_currency"
    assert [u.value for u in carried.updates] == [
        {"amount": 450.0, "currency": "SGD", "period": "week"}
    ]


def test_a_period_the_worker_did_not_say_is_a_follow_up() -> None:
    message = "I will earn 450 Singapore dollars."
    reading = read(
        "answer", cand("monthly_salary", "450 Singapore dollars", money=money(450, "SGD", "month"))
    )

    result = interpret(reading, ctx(message, asking="monthly_salary"))

    assert result.updates == []
    assert result.clarify is not None and result.clarify.trigger == "unclear_period"


def test_an_interest_with_no_period_is_a_follow_up() -> None:
    reading = read(
        "answer",
        cand(
            "debt_interest", "3 percent", interest=ExtractedInterest(rate_percent=3, period="year")
        ),
    )

    result = interpret(reading, ctx("It is 3 percent.", asking="debt_interest"))

    assert result.updates == [] and result.clarify.trigger == "unclear_period"  # type: ignore[union-attr]


def test_a_total_is_always_once_whatever_the_model_says_of_its_period() -> None:
    reading = read("answer", cand("savings", "20,000 rupees", money=money(20000, "INR", "month")))

    result = interpret(reading, ctx("I have 20,000 rupees.", asking="savings"))

    assert result.updates[0].value == {"amount": 20000.0, "currency": "INR", "period": "once"}


def test_a_zero_needs_no_money_and_takes_the_hosts_when_none_is_known() -> None:
    reading = read("answer", cand("debt_outstanding", "No debt", money=money(0, None, None)))

    bare = interpret(reading, ctx("No debt.", asking="debt_outstanding"))
    known = interpret(
        reading,
        ctx(
            "No debt.",
            asking="debt_outstanding",
            slots={"destination_country": stored("SG", confirmed=True)},
        ),
    )

    assert bare.clarify is not None and bare.clarify.trigger == "missing_currency"
    assert known.updates[0].value == {"amount": 0.0, "currency": "SGD", "period": "once"}


def test_a_country_the_worker_did_not_name_is_refused() -> None:
    reading = read("answer", cand("destination_country", "I will work hard", country="SG"))

    result = interpret(reading, ctx("I will work hard.", asking="destination_country"))

    assert result.updates == []


# --- ranges, confidence and agreement ----------------------------------------------------------


def test_an_amount_outside_what_workers_say_is_kept_unconfirmed_and_asked_about() -> None:
    message = "Nagbayad po ako ng 800,000 pesos sa recruiter."
    reading = read(
        "answer", cand("recruitment_fee_paid", "800,000 pesos", money=money(800000, "PHP", "once"))
    )

    result = interpret(reading, ctx(message, asking="recruitment_fee_paid"))

    assert [(u.slot, u.confirmed) for u in result.updates] == [("recruitment_fee_paid", False)]
    assert result.clarify.trigger == "out_of_range"  # type: ignore[union-attr]


def test_a_reading_the_model_is_unsure_of_is_kept_unconfirmed_and_checked() -> None:
    result = interpret(read("answer", salary(confidence=0.6)), ctx(MSG, asking="monthly_salary"))

    assert [(u.slot, u.confirmed) for u in result.updates] == [("monthly_salary", False)]
    assert result.clarify.trigger == "low_confidence"  # type: ignore[union-attr]


def test_a_reading_the_model_hardly_believes_is_not_used() -> None:
    result = interpret(read("answer", salary(confidence=0.3)), ctx(MSG, asking="monthly_salary"))

    assert result.updates == []
    assert result.clarify.trigger == "not_understood"  # type: ignore[union-attr]


def test_a_yes_confirms_the_value_that_was_asked_about() -> None:
    pending = {
        "recruitment_fee_paid": stored(
            {"amount": 800000.0, "currency": "PHP", "period": "once"}, confirmed=False
        )
    }
    reading = read("answer", cand("recruitment_fee_paid", "Yes", confirms_pending=True))

    result = interpret(
        reading, ctx("Yes, that is right.", asking="recruitment_fee_paid", slots=pending)
    )

    assert [(u.slot, u.confirmed) for u in result.updates] == [("recruitment_fee_paid", True)]
    assert result.updates[0].value == pending["recruitment_fee_paid"]["value"]


def test_a_yes_to_a_salary_offered_from_a_contract_keeps_its_source() -> None:
    offered = {
        "monthly_salary": {
            **stored(SALARY, confirmed=False),
            "source": "contract_prefill",
        }
    }
    reading = read("answer", cand("monthly_salary", "Yes", confirms_pending=True))

    result = interpret(reading, ctx("Yes.", asking="monthly_salary", slots=offered))

    assert [(u.slot, u.confirmed, u.source) for u in result.updates] == [
        ("monthly_salary", True, "contract_prefill")
    ]


def test_a_yes_with_nothing_to_confirm_confirms_nothing() -> None:
    reading = read("answer", cand("recruitment_fee_paid", "Yes", confirms_pending=True))

    result = interpret(reading, ctx("Yes.", asking="recruitment_fee_paid"))

    assert result.updates == []


def test_a_slot_already_confirmed_is_not_changed_by_a_later_message() -> None:
    done = {"monthly_salary": stored(SALARY, confirmed=True)}
    reading = read(
        "answer",
        cand(
            "monthly_salary", "3,000 Singapore dollars a month", money=money(3000, "SGD", "month")
        ),
    )

    result = interpret(reading, ctx("Maybe 3,000 Singapore dollars a month.", slots=done))

    assert result.updates == []


# --- declining, questions and skip rules -------------------------------------------------------


def test_only_the_optional_question_can_be_declined() -> None:
    optional = interpret(
        read("decline"), ctx("I do not know the date yet.", asking="departure_date")
    )
    required = interpret(read("decline"), ctx("I do not know.", asking="monthly_salary"))

    assert list(optional.declined) == ["departure_date"] and optional.clarify is None
    assert list(required.declined) == [] and required.clarify.trigger == "not_understood"  # type: ignore[union-attr]


@pytest.mark.parametrize("kind", ["question", "other"])
def test_a_question_or_small_talk_understands_nothing_and_asks_nothing(kind: str) -> None:
    result = interpret(read(kind), ctx("Why do you ask?", asking="monthly_salary"))

    assert (list(result.updates), list(result.declined), result.clarify) == ([], [], None)


def test_an_answer_that_is_no_answer_asks_the_question_again() -> None:
    result = interpret(read("answer"), ctx("hmm ok", asking="monthly_salary"))

    assert (result.clarify.slot, result.clarify.trigger) == ("monthly_salary", "not_understood")  # type: ignore[union-attr]


def test_the_interest_is_not_taken_when_the_same_message_says_there_is_no_debt() -> None:
    message = "No debt, 0 rupees. The interest is 12 percent a year."
    reading = read(
        "answer",
        cand("debt_outstanding", "No debt, 0 rupees", money=money(0, "INR", "once")),
        cand(
            "debt_interest",
            "12 percent a year",
            interest=ExtractedInterest(rate_percent=12, period="year"),
        ),
    )

    result = interpret(reading, ctx(message, asking="debt_outstanding"))

    assert [u.slot for u in result.updates] == ["debt_outstanding"]


# --- dates ------------------------------------------------------------------------------------


def test_a_date_is_kept_only_if_its_year_is_the_one_written() -> None:
    message = "Aalis po ako sa January 20, 2027."
    good = interpret(
        read("answer", cand("departure_date", "January 20, 2027", date="2027-01-20")),
        ctx(message, asking="departure_date"),
    )
    wrong = interpret(
        read("answer", cand("departure_date", "January 20, 2027", date="2028-01-20")),
        ctx(message, asking="departure_date"),
    )
    invalid = interpret(
        read("answer", cand("departure_date", "January 20, 2027", date="2027-02-31")),
        ctx(message, asking="departure_date"),
    )

    assert [u.value for u in good.updates] == ["2027-01-20"]
    assert wrong.updates == [] and invalid.updates == []


# --- the model cannot make up a slot, and cannot make everything up ----------------------------


def test_a_slot_that_is_not_one_of_the_eleven_cannot_even_be_read() -> None:
    with pytest.raises(ValidationError):
        SlotCandidate.model_validate({"slot": "credit_score", "evidence": "x", "confidence": 1})


# --- the finer rules (found by the model that invents everything) ------------------------------


@pytest.mark.parametrize(
    ("value", "text", "stated"),
    [
        (1_000_000, "Tabungan saya cuma 1 juta rupiah.", True),
        (1_000_000, "Saya masih berutang 10 juta rupiah.", False),  # 10 juta is 10 million
        (150_000, "1.5 lakh rupees", True),
        (10_000_000, "10 lakh rupees", False),  # 10 lakh is a million, not ten million
        (50_000, "50k yen", True),
        (50_000, "I have 50 yen", False),  # no word for thousands, so no thousands
        (1700, "Gaji saya 1.700 ringgit", True),
    ],
)
def test_a_magnitude_counts_only_when_its_word_is_written(
    value: float, text: str, stated: bool
) -> None:
    from app.services.coach.extraction_cues import number_stated

    assert number_stated(value, text) is stated


@pytest.mark.parametrize(
    ("message", "count"),
    [
        ("Apat po ang umaasa sa akin: dalawang anak, nanay at tatay ko.", 4),
        ("मेरे ऊपर तीन लोग निर्भर हैं: दो बच्चे और मेरी माँ।", 3),
        ("Ada tiga orang yang bergantung pada saya.", 3),
    ],
)
def test_a_count_in_words_of_the_other_languages_is_a_stated_count(
    message: str, count: int
) -> None:
    result = interpret(
        read("answer", cand("dependents", message, count=count)), ctx(message, asking="dependents")
    )

    assert [(u.slot, u.value, u.confirmed) for u in result.updates] == [("dependents", count, True)]


def test_a_number_beside_a_percent_or_money_is_not_a_count_of_people() -> None:
    message = "2 percent po kada buwan."

    result = interpret(
        read("answer", cand("dependents", message, count=2)), ctx(message, asking="dependents")
    )

    assert [(u.slot, u.confirmed) for u in result.updates] == [("dependents", False)]


def test_a_number_that_is_no_percent_is_not_a_rate_that_is_kept_as_confirmed() -> None:
    message = "Gaji saya 1.500 ringgit sebulan."
    reading = read(
        "answer",
        cand(
            "debt_interest", message, interest=ExtractedInterest(rate_percent=1.5, period="month")
        ),
    )

    result = interpret(reading, ctx(message, asking="debt_interest"))

    assert all(not u.confirmed for u in result.updates)


def test_a_date_is_the_workers_own_only_with_the_year_they_wrote() -> None:
    with_year = interpret(
        read("answer", cand("departure_date", "20 January 2027", date="2027-01-20")),
        ctx("I leave on 20 January 2027.", asking="departure_date"),
    )
    without = interpret(
        read("answer", cand("departure_date", "20 January", date="2027-01-20")),
        ctx("I leave on 20 January.", asking="departure_date"),
    )
    other_digits = interpret(
        read("answer", cand("departure_date", "5 children", date="2027-03-20")),
        ctx("I have 5 children.", asking="departure_date"),
    )

    assert [u.confirmed for u in with_year.updates] == [True]
    assert [u.confirmed for u in without.updates] == [False]
    assert other_digits.updates == []
