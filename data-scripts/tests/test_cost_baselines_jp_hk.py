from __future__ import annotations

import copy
from datetime import date
from typing import Any

import pytest

from src.validators.cost_baselines import (
    CATEGORIES,
    HOST_CURRENCY,
    JOB_TYPES,
    CostBaseline,
    load_baselines,
)
from tests.test_cost_baselines_loader import _FakeClient, _load

HOSTS = ("JP", "HK")


def _both() -> dict[str, CostBaseline]:
    return load_baselines(only=list(HOSTS))


def _figures(baseline: CostBaseline) -> list[Any]:
    return [*baseline.categories.values(), *baseline.setup_costs.values()]


def test_committed_files_pass_for_japan_and_hong_kong() -> None:
    baselines = _both()

    assert set(baselines) == set(HOSTS)
    assert baselines["JP"].currency == "JPY" and baselines["HK"].currency == "HKD"
    for baseline in baselines.values():
        assert set(baseline.categories) == set(CATEGORIES)
        assert baseline.setup_costs


def test_all_six_hosts_now_have_a_baseline_in_their_own_currency() -> None:
    baselines = load_baselines()

    assert set(baselines) == set(HOST_CURRENCY)
    assert all(b.currency == HOST_CURRENCY[host] for host, b in baselines.items())


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


def test_zero_figures_say_why() -> None:
    for baseline in _both().values():
        for figure in _figures(baseline):
            if figure.high == 0:
                assert figure.notes


def test_a_live_in_helper_in_hong_kong_pays_nothing_for_housing_or_mpf() -> None:
    hk = _both()["HK"]

    assert hk.categories["accommodation"].high == 0
    assert hk.categories["mandatory_deductions"].high == 0
    assert hk.categories["food"].low == 0 and hk.categories["food"].typical == 1236


def test_the_agency_commission_is_ten_percent_of_the_minimum_allowable_wage() -> None:
    commission = _both()["HK"].setup_costs["agency_commission"]

    assert commission.high == pytest.approx(5100 * 0.10)


def test_hong_kong_transport_is_eight_journeys_at_the_fares_in_the_note() -> None:
    transport = _both()["HK"].categories["transport"]

    assert transport.low == pytest.approx(8 * 4.0, abs=0.5)
    assert transport.typical == pytest.approx(8 * 15.7, abs=0.5)
    assert transport.high == pytest.approx(8 * 30.0, abs=0.5)


def test_japanese_deductions_add_up_the_workers_half_of_each_premium() -> None:
    pension, support_levy, employment = 18.3 / 2, 0.23 / 2, 0.5
    deductions = _both()["JP"].categories["mandatory_deductions"]

    def total(health_rate: float) -> float:
        return pension + health_rate / 2 + support_levy + employment

    assert deductions.unit == "pct_of_wage"
    assert deductions.low == pytest.approx(total(9.44), abs=0.005)
    assert deductions.typical == pytest.approx(total(9.85), abs=0.005)
    assert deductions.high == pytest.approx(total(10.55), abs=0.005)


def test_japanese_housing_tops_out_at_the_tokyo_student_average() -> None:
    housing = _both()["JP"].categories["accommodation"]

    assert housing.high == 57000 and housing.low < housing.typical < housing.high


def test_loader_writes_japan_and_hong_kong_then_leaves_them_alone() -> None:
    client = _FakeClient()

    first = _load(client, _both())
    before = copy.deepcopy(client.store)
    second = _load(client, _both())

    assert {(r.host, r.version, r.status) for r in first} == {("JP", 1, "new"), ("HK", 1, "new")}
    assert {(r.version, r.status) for r in second} == {(1, "unchanged")}
    assert client.store == before
    assert client.store["cost_baselines/JP"]["currency"] == "JPY"
