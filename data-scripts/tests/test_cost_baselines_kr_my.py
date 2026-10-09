from __future__ import annotations

import copy
from datetime import date
from typing import Any

import pytest

from src.validators.cost_baselines import CATEGORIES, JOB_TYPES, CostBaseline, load_baselines
from tests.test_cost_baselines_loader import _FakeClient, _load

HOSTS = ("KR", "MY")


def _both() -> dict[str, CostBaseline]:
    return load_baselines(only=list(HOSTS))


def _figures(baseline: CostBaseline) -> list[Any]:
    return [*baseline.categories.values(), *baseline.setup_costs.values()]


def test_committed_files_pass_for_korea_and_malaysia() -> None:
    baselines = _both()

    assert set(baselines) == set(HOSTS)
    assert baselines["KR"].currency == "KRW" and baselines["MY"].currency == "MYR"
    for baseline in baselines.values():
        assert set(baseline.categories) == set(CATEGORIES)
        assert baseline.setup_costs


def test_every_figure_names_its_page_its_day_and_its_curator() -> None:
    for baseline in _both().values():
        for figure in _figures(baseline):
            sources = [figure.source, *(figure.other_sources or [])]
            assert all(s.url.startswith("https://") and s.publisher for s in sources)
            assert all(s.retrieved_on <= date.today() for s in sources)
            assert figure.curator


def test_job_type_overrides_use_the_job_types_of_the_users_collection() -> None:
    for baseline in _both().values():
        for figure in _figures(baseline):
            assert set(figure.by_job_type or {}) <= set(JOB_TYPES)


def test_korean_housing_is_the_old_guideline_range_on_the_2026_minimum_wage() -> None:
    monthly_minimum = 10_320 * 209
    housing = _both()["KR"].categories["accommodation"]

    assert housing.low == pytest.approx(monthly_minimum * 0.08, abs=1)
    assert housing.typical == pytest.approx(monthly_minimum * 0.14, abs=1)
    assert housing.high == pytest.approx(monthly_minimum * 0.20, abs=1)


def test_korean_deductions_add_up_the_workers_share_of_each_insurance() -> None:
    pension, health, care, employment = 4.75, 7.19 / 2, 0.9448 / 2, 0.9
    deductions = _both()["KR"].categories["mandatory_deductions"]

    assert deductions.unit == "pct_of_wage"
    assert deductions.low == pytest.approx(health + care + employment, abs=0.005)
    assert (
        deductions.typical
        == deductions.high
        == pytest.approx(pension + health + care + employment, abs=0.005)
    )


def test_malaysian_deductions_are_epf_plus_the_workers_socso_share() -> None:
    epf, invalidity, non_employment_injury, later_phase = 2.0, 0.5, 0.75, 1.0
    deductions = _both()["MY"].categories["mandatory_deductions"]

    assert deductions.low == deductions.typical == epf + invalidity + non_employment_injury
    assert deductions.high == epf + invalidity + later_phase


def test_malaysian_housing_never_passes_the_rent_cap() -> None:
    assert _both()["MY"].categories["accommodation"].high == 150


def test_zero_figures_say_why() -> None:
    for baseline in _both().values():
        for figure in _figures(baseline):
            if figure.high == 0:
                assert figure.notes


def test_loader_writes_korea_and_malaysia_then_leaves_them_alone() -> None:
    client = _FakeClient()

    first = _load(client, _both())
    before = copy.deepcopy(client.store)
    second = _load(client, _both())

    assert {(r.host, r.version, r.status) for r in first} == {("KR", 1, "new"), ("MY", 1, "new")}
    assert {(r.version, r.status) for r in second} == {(1, "unchanged")}
    assert client.store == before
    assert client.store["cost_baselines/KR"]["currency"] == "KRW"
