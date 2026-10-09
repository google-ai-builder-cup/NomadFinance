"""The twelve Coach personas (NF-FC-007): shape, coverage, and the expected scores re-worked."""

from __future__ import annotations

import json
from datetime import date
from functools import cache
from typing import Any, cast

import pytest

from app.schemas.coach_profile import SLOT_NAMES, CoachProfile, Money, SlotName
from app.services.coach.question_bank import load_question_bank, range_issue
from tests.fixtures import coach_rubric_reference as rubric
from tests.fixtures.coach_personas import DATA_FILE, Persona, PersonaFile, load_personas

# A fixed day, so the leaving dates never make a test depend on the clock.
TODAY = date(2026, 10, 9)
CORRIDORS = ("SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH")
LANGUAGES = {"en", "hi", "tl", "id", "ne", "bn"}
HOME_CURRENCY = {"PH": "PHP", "IN": "INR", "ID": "IDR"}
HOST_CURRENCY = rubric.HOST_CURRENCY


@cache
def _file() -> PersonaFile:
    return load_personas()


def _persona(persona_id: str) -> Persona:
    return next(p for p in _file().personas if p.id == persona_id)


def _rates(persona: Persona) -> dict[str, float]:
    return {persona.expected_score.rate_pair.split("_")[1]: persona.expected_score.rate}


def _worked(persona: Persona) -> dict[str, Any]:
    return rubric.score(persona.expected_slots, _rates(persona))


def test_the_file_is_valid_and_has_twelve_personas() -> None:
    data = _file()

    assert data.version == 1 and data.rubric_version == 1
    assert len(data.personas) == 12
    assert len({p.id for p in data.personas}) == 12
    assert len({p.name for p in data.personas}) == 12


def test_two_personas_per_corridor_and_the_corridor_matches_the_countries() -> None:
    by_corridor: dict[str, list[str]] = {}
    for persona in _file().personas:
        by_corridor.setdefault(persona.corridor, []).append(persona.id)
        assert persona.corridor == f"{persona.host_country}-{persona.home_country}"
        assert persona.expected_slots.destination_country == persona.host_country

    assert set(by_corridor) == set(CORRIDORS)
    assert all(len(ids) == 2 for ids in by_corridor.values())


def test_the_languages_are_among_the_six_and_the_script_language_is_set_on_every_turn() -> None:
    for persona in _file().personas:
        assert persona.language in LANGUAGES
        assert persona.script[0].language == persona.language
        assert {turn.language for turn in persona.script} <= LANGUAGES


def test_the_scripts_cover_several_languages_and_one_switches_mid_session() -> None:
    personas = _file().personas

    assert {p.language for p in personas} == {"en", "hi", "tl", "id"}
    switching = [p.id for p in personas if len({t.language for t in p.script}) > 1]
    assert switching == ["p05_au_in_gurpreet"]


def test_two_personas_are_the_demo_users() -> None:
    demo = {p.name: p.corridor for p in _file().personas if p.demo}

    assert demo == {"Priya": "SG-IN", "Miguel": "JP-PH"}


def test_the_expected_slots_are_a_valid_profile_and_survive_a_round_trip() -> None:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    for persona, source in zip(_file().personas, raw["personas"], strict=True):
        again = CoachProfile.model_validate(persona.expected_slots.model_dump(exclude_none=True))
        assert again == persona.expected_slots
        assert persona.expected_slots.model_dump(mode="json", exclude_none=True) == (
            source["expected_slots"]
        )


def test_every_slot_is_answered_except_the_skipped_and_the_declined() -> None:
    for persona in _file().personas:
        filled = set(persona.expected_slots.model_dump(exclude_none=True))
        assert filled == set(SLOT_NAMES) - set(persona.skipped_slots) - set(persona.declined_slots)


def test_the_interest_question_is_skipped_exactly_when_there_is_no_debt() -> None:
    for persona in _file().personas:
        slots = persona.expected_slots
        assert slots.debt_outstanding is not None
        no_debt = slots.debt_outstanding.amount == 0
        assert (persona.skipped_slots == ["debt_interest"]) == no_debt
        assert (slots.debt_interest is None) == no_debt


def test_the_values_are_ones_the_question_bank_would_keep_without_asking_again() -> None:
    bank = load_question_bank()
    for persona in _file().personas:
        for slot in persona.expected_slots.model_fields_set:
            value = getattr(persona.expected_slots, slot)
            assert range_issue(bank, cast(SlotName, slot), value, TODAY) is None, (persona.id, slot)


def test_the_script_fills_each_slot_once_in_the_order_the_bank_asks() -> None:
    order = [question.slot for question in load_question_bank().questions]
    for persona in _file().personas:
        filled = [slot for turn in persona.script for slot in turn.fills]
        assert len(filled) == len(set(filled)), persona.id
        assert set(filled) == set(persona.expected_slots.model_dump(exclude_none=True))
        assert filled == [slot for slot in order if slot in filled], persona.id


def test_the_last_message_confirms_the_review_and_fills_nothing() -> None:
    for persona in _file().personas:
        last = persona.script[-1]
        assert last.fills == [] and last.coach_follow_up is None


def test_a_message_with_a_follow_up_fills_nothing_and_the_next_one_answers_it() -> None:
    triggers = set()
    for persona in _file().personas:
        assert persona.expected_turn_count == len(persona.script)
        for index, turn in enumerate(persona.script[:-1]):
            if turn.coach_follow_up:
                assert turn.fills == []
                assert persona.script[index + 1].fills, (persona.id, index)
                triggers.add(turn.coach_follow_up)

    assert triggers == {"unclear_period", "missing_currency", "out_of_range"}


def test_the_stated_numbers_are_in_the_message_that_fills_the_slot() -> None:
    for persona in _file().personas:
        for turn in persona.script:
            for slot in turn.fills:
                value = getattr(persona.expected_slots, slot)
                if not isinstance(value, Money):
                    continue
                digits = turn.say.replace(",", "").replace(".", "").replace(" ", "")
                millions = f"{value.amount / 1_000_000:g} juta"
                assert f"{value.amount:g}" in digits or (
                    value.amount % 1_000_000 == 0 and millions in turn.say
                ), (persona.id, slot, turn.say)


def test_the_rubric_reference_matches_the_three_worked_examples_of_the_rubric_page() -> None:
    def case(host: str, job: str, slots: dict[str, Any], rate: float) -> dict[str, Any]:
        profile = CoachProfile.model_validate(
            {"destination_country": host, "job_type": job, **slots}
        )
        return rubric.score(profile, {"INR": rate} if rate != 1 else {})

    mid = case(
        "AU",
        "care_worker",
        {
            "monthly_salary": {"amount": 4200, "currency": "AUD", "period": "month"},
            "remittance_target": {"amount": 900, "currency": "AUD", "period": "month"},
            "recruitment_fee_paid": {"amount": 150000, "currency": "INR", "period": "once"},
            "debt_outstanding": {"amount": 120000, "currency": "INR", "period": "once"},
            "debt_interest": {"rate_percent": 3, "period": "month"},
            "savings": {"amount": 25000, "currency": "INR", "period": "once"},
            "bank_or_wallet": "bank_account",
        },
        54.0,
    )
    low = case(
        "SG",
        "domestic_worker",
        {
            "monthly_salary": {"amount": 650, "currency": "SGD", "period": "month"},
            "remittance_target": {"amount": 400, "currency": "SGD", "period": "month"},
            "recruitment_fee_paid": {"amount": 3000, "currency": "SGD", "period": "once"},
            "debt_outstanding": {"amount": 2400, "currency": "SGD", "period": "once"},
            "debt_interest": {"rate_percent": 5, "period": "month"},
            "savings": {"amount": 0, "currency": "SGD", "period": "once"},
            "bank_or_wallet": "none",
        },
        1.0,
    )
    high = case(
        "KR",
        "manufacturing_worker",
        {
            "monthly_salary": {"amount": 2400000, "currency": "KRW", "period": "month"},
            "remittance_target": {"amount": 600000, "currency": "KRW", "period": "month"},
            "recruitment_fee_paid": {"amount": 0, "currency": "KRW", "period": "once"},
            "debt_outstanding": {"amount": 0, "currency": "KRW", "period": "once"},
            "savings": {"amount": 3000000, "currency": "KRW", "period": "once"},
            "bank_or_wallet": "both",
        },
        1.0,
    )

    def points(result: dict[str, Any]) -> list[int]:
        return [pts for _, pts in result["factors"].values()]

    assert (mid["total"], mid["band"], points(mid)) == (59, "getting_ready", [82, 5, 100, 47, 90])
    assert (low["total"], low["band"], points(low)) == (17, "needs_work", [33, 0, 47, 0, 0])
    assert (high["total"], high["band"], points(high)) == (
        91,
        "well_prepared",
        [100, 62, 100, 100, 100],
    )


@pytest.mark.parametrize("persona", load_personas().personas, ids=lambda p: p.id)
def test_the_stored_score_is_the_rubric_applied_to_the_answers(persona: Persona) -> None:
    worked = _worked(persona)
    stored = persona.expected_score

    assert stored.total == worked["total"]
    assert stored.band == worked["band"]
    assert [f.id for f in stored.factors] == list(rubric.WEIGHTS)
    for factor in stored.factors:
        value, points = worked["factors"][factor.id]
        assert factor.points == points, factor.id
        assert factor.value == pytest.approx(value, abs=0.006), factor.id
        assert factor.weight == rubric.WEIGHTS[factor.id]
    for name, amount in stored.amounts_in_host_currency.items():
        assert amount == pytest.approx(worked["amounts"][name], abs=0.006), name


def test_the_weights_add_up_to_one_and_the_total_is_the_half_up_weighted_sum() -> None:
    for persona in _file().personas:
        factors = persona.expected_score.factors
        assert sum(f.weight for f in factors) == pytest.approx(1.0)
        weighted = sum(f.weight * f.points for f in factors)
        assert persona.expected_score.total == int(weighted + 0.5 + 1e-9), persona.id


def test_the_rates_are_the_ones_of_the_corridor_and_the_currencies_fit() -> None:
    data = _file()
    for persona in data.personas:
        expected_pair = (
            f"{HOST_CURRENCY[persona.host_country]}_{HOME_CURRENCY[persona.home_country]}"
        )
        assert persona.expected_score.rate_pair == expected_pair
        assert data.rates[expected_pair] == persona.expected_score.rate
        for slot in ("recruitment_fee_paid", "debt_outstanding", "savings"):
            currency = getattr(persona.expected_slots, slot).currency
            assert currency in {
                HOST_CURRENCY[persona.host_country],
                HOME_CURRENCY[persona.home_country],
            }
    assert set(data.rates) == {
        "SGD_PHP",
        "SGD_INR",
        "AUD_INR",
        "MYR_IDR",
        "JPY_PHP",
        "AUD_PHP",
    }


def test_the_personas_reach_every_band_and_the_hard_cases_of_the_rubric() -> None:
    personas = _file().personas
    bands = {p.id: p.expected_score.band for p in personas}

    assert set(bands.values()) == {"needs_work", "getting_ready", "well_prepared"}
    floor = [p for p in personas if p.expected_score.total >= 70 and bands[p.id] != "well_prepared"]
    assert [p.id for p in floor] == ["p05_au_in_gurpreet"]
    capped = [
        p.id
        for p in personas
        if next(f for f in p.expected_score.factors if f.id == "remittance_ratio").points == 25
    ]
    assert capped == ["p12_au_ph_ricardo"]
    over_cap = {
        p.id
        for p in personas
        if next(f for f in p.expected_score.factors if f.id == "recruitment_fee_vs_cap").points
        < 100
    }
    assert {"p01_sg_ph_maricel", "p07_my_id_slamet", "p09_jp_ph_mark"} <= over_cap
    weekly = _persona("p02_sg_ph_jun").expected_slots.monthly_salary
    yearly = _persona("p06_au_in_anil").expected_slots.monthly_salary
    assert weekly and weekly.period == "week" and yearly and yearly.period == "year"
    assert _persona("p06_au_in_anil").declined_slots == ["departure_date"]
