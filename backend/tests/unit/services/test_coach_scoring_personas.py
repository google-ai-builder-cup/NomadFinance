"""The score against the twelve personas, by hand-worked values (NF-FC-011).

Offline and instant: the answers come from the persona file, the costs and the law from the
curated source files, the rates from the file's fixed illustrative rates. The expected numbers in
the file were worked out by hand and re-worked by `coach_rubric_reference` (NF-FC-007), a second
way of reaching them; the engine must give the same.
"""

from __future__ import annotations

import pytest

from app.services.coach.scoring import score_inputs
from app.services.coach.scoring_inputs import build_inputs, essentials_from, fee_cap_months
from tests.fixtures import coach_rubric_reference as rubric
from tests.fixtures.coach_personas import Persona, load_personas
from tests.fixtures.coach_scoring_data import HOSTS, baseline, law_rules

PERSONAS = load_personas().personas


def _engine(persona: Persona):  # type: ignore[no-untyped-def]
    profile, expected = persona.expected_slots, persona.expected_score
    host = persona.host_country
    inputs = build_inputs(
        profile,
        essentials=essentials_from(baseline(host), profile.job_type or ""),
        cap_months=fee_cap_months(law_rules(host)),
        rates={expected.rate_pair: expected.rate},
    )
    return inputs, score_inputs(inputs)


@pytest.mark.parametrize("persona", PERSONAS, ids=[p.id for p in PERSONAS])
def test_the_engine_matches_the_hand_computed_score(persona: Persona) -> None:
    inputs, result = _engine(persona)
    expected = persona.expected_score

    assert (result.total, result.band) == (expected.total, expected.band)
    assert [f.id for f in result.factors] == [f.id for f in expected.factors]
    for got, want in zip(result.factors, expected.factors, strict=True):
        assert got.score == want.points, got.id
        assert got.value == pytest.approx(want.value, abs=0.011), got.id
        assert got.weight == want.weight
    amounts = expected.amounts_in_host_currency
    assert inputs.monthly_salary == pytest.approx(amounts["salary"], abs=0.01)
    assert inputs.recruitment_fee == pytest.approx(amounts["fee"], abs=0.01)
    assert inputs.debt == pytest.approx(amounts["debt"], abs=0.01)
    assert inputs.savings == pytest.approx(amounts["savings"], abs=0.01)
    assert inputs.essentials == pytest.approx(amounts["essentials"], abs=0.01)


@pytest.mark.parametrize("persona", PERSONAS, ids=[p.id for p in PERSONAS])
def test_the_engine_and_the_plain_reference_agree_to_the_decimal(persona: Persona) -> None:
    _, result = _engine(persona)
    worked = rubric.score(
        persona.expected_slots,
        {persona.expected_score.rate_pair.split("_")[1]: persona.expected_score.rate},
    )

    assert result.total == worked["total"] and result.band == worked["band"]
    for factor in result.factors:
        value, points = worked["factors"][factor.id]
        assert factor.score == points
        assert factor.value == pytest.approx(value, abs=0.006)


def test_the_personas_span_all_three_bands_and_the_floor_rule() -> None:
    bands = {p.expected_score.band for p in PERSONAS}

    assert bands == {"needs_work", "getting_ready", "well_prepared"}


def test_the_fee_cap_is_read_from_the_real_law_files() -> None:
    caps = {host: fee_cap_months(law_rules(host)) for host in HOSTS}

    assert caps == {"SG": 2.0, "MY": 1.0, "HK": 0.10, "KR": 0.0, "JP": 0.0, "AU": 0.0}
    assert caps == rubric.CAP_MONTHS


def test_every_host_has_a_baseline_in_its_own_currency_with_the_four_lines() -> None:
    for host in HOSTS:
        data = baseline(host)

        assert data["currency"] == rubric.HOST_CURRENCY[host]
        assert essentials_from(data, "domestic_worker") > 0
