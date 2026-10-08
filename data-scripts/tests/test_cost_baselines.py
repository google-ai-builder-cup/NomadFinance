from __future__ import annotations

import copy
import json
import shutil
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.config import COST_BASELINES_DIR
from src.validators.cost_baselines import (
    CATEGORIES,
    HOST_CURRENCY,
    JOB_TYPES,
    CostBaseline,
    load_baseline,
    load_baselines,
    main,
)

Edit = Callable[[dict[str, Any]], None]


def _copy(tmp_path: Path) -> Path:
    """The SG and AU files only, so a test never depends on what other tasks have added."""
    target = tmp_path / "cost-baselines"
    target.mkdir()
    for host in ("SG", "AU"):
        shutil.copy(COST_BASELINES_DIR / f"{host}.json", target / f"{host}.json")
    return target


def _edit(directory: Path, host: str, change: Edit) -> None:
    path = directory / f"{host}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def _figures(baseline: CostBaseline) -> list[Any]:
    return [*baseline.categories.values(), *baseline.setup_costs.values()]


def test_committed_files_pass_for_singapore_and_australia() -> None:
    baselines = load_baselines(only=["SG", "AU"])

    assert set(baselines) == {"SG", "AU"}
    assert baselines["SG"].currency == "SGD" and baselines["AU"].currency == "AUD"


def test_every_committed_file_is_one_of_the_six_hosts_in_its_own_currency() -> None:
    for host, baseline in load_baselines().items():
        assert host in HOST_CURRENCY
        assert baseline.currency == HOST_CURRENCY[host]


def test_every_figure_names_its_page_its_day_and_its_curator() -> None:
    for host in ("SG", "AU"):
        for figure in _figures(load_baselines(only=[host])[host]):
            sources = [figure.source, *(figure.other_sources or [])]
            assert all(s.url.startswith("https://") and s.publisher for s in sources)
            assert all(s.retrieved_on <= date.today() for s in sources)
            assert figure.curator


def test_each_country_has_the_five_categories_and_a_setup_cost() -> None:
    for baseline in load_baselines(only=["SG", "AU"]).values():
        assert set(baseline.categories) == set(CATEGORIES)
        assert baseline.setup_costs


def test_a_live_in_domestic_worker_in_singapore_pays_nothing_for_housing_or_food() -> None:
    sg = load_baselines(only=["SG"])["SG"]

    for category in ("accommodation", "food"):
        override = sg.categories[category].by_job_type
        assert override is not None and override["domestic_worker"].high == 0
    assert sg.categories["accommodation"].high > 0 and sg.categories["food"].high > 0


def test_job_type_overrides_use_the_job_types_of_the_users_collection() -> None:
    for baseline in load_baselines(only=["SG", "AU"]).values():
        for figure in _figures(baseline):
            assert set(figure.by_job_type or {}) <= set(JOB_TYPES)


def test_no_figure_uses_the_stale_placeholder_text() -> None:
    text = (COST_BASELINES_DIR / "SG.json").read_text(encoding="utf-8")
    text += (COST_BASELINES_DIR / "AU.json").read_text(encoding="utf-8")

    assert "example.org" not in text and "TODO" not in text


def _set(path: list[str], value: Any) -> Edit:
    def change(data: dict[str, Any]) -> None:
        node = data
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return change


def _drop(path: list[str]) -> Edit:
    def change(data: dict[str, Any]) -> None:
        node = data
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return change


def _add_category(data: dict[str, Any]) -> None:
    data["categories"]["utilities"] = copy.deepcopy(data["categories"]["food"])


def _bad_job_type(data: dict[str, Any]) -> None:
    data["categories"]["food"]["by_job_type"] = {"astronaut": {"low": 1, "typical": 2, "high": 3}}


def _percent_over_100(data: dict[str, Any]) -> None:
    figure = data["categories"]["mandatory_deductions"]
    figure.update(low=10, typical=50, high=120, unit="pct_of_wage")


def _small_share_on_a_rent_line(data: dict[str, Any]) -> None:
    # Small numbers, so only the unit rule can refuse it, not the limit of 100.
    data["categories"]["food"].update(low=1, typical=2, high=3, unit="pct_of_wage")


def _deductions_without_a_note(data: dict[str, Any]) -> None:
    # Non-zero, so only the "deductions need a note" rule can refuse it, not the zero rule.
    figure = data["categories"]["mandatory_deductions"]
    figure.update(low=5, typical=5, high=5)
    del figure["notes"]


def _rename_setup_cost(data: dict[str, Any]) -> None:
    data["setup_costs"]["SIM Card"] = data["setup_costs"].pop("sim_card")


def _slips() -> list[tuple[str, Edit]]:
    future = (date.today() + timedelta(days=1)).isoformat()
    return [
        ("low above typical", _set(["categories", "food", "low"], 999)),
        ("negative figure", _set(["categories", "food", "low"], -1)),
        ("typical above high", _set(["categories", "food", "typical"], 9999)),
        ("wrong currency", _set(["currency"], "KRW")),
        ("not one of the six hosts", _set(["host_country"], "XX")),
        ("category missing", _drop(["categories", "transport"])),
        ("category added", _add_category),
        ("recurring cost in one_off", _set(["categories", "accommodation", "unit"], "one_off")),
        ("share of wage on a food line", _small_share_on_a_rent_line),
        ("setup cost not one_off", _set(["setup_costs", "sim_card", "unit"], "month")),
        ("share of wage above 100", _percent_over_100),
        ("unknown job type", _bad_job_type),
        ("zero without a note", _drop(["setup_costs", "sim_card", "notes"])),
        ("deductions without a note", _deductions_without_a_note),
        ("source missing", _drop(["categories", "food", "source"])),
        ("http source", _set(["categories", "food", "source", "url"], "http://example.test/x")),
        (
            "source day in the future",
            _set(["categories", "food", "source", "retrieved_on"], future),
        ),
        ("other_sources empty", _set(["categories", "food", "other_sources"], [])),
        ("TODO note", _set(["categories", "food", "notes"], "TODO find a source for this")),
        ("note too long", _set(["categories", "food", "notes"], "x" * 400)),
        ("curator is a name", _set(["categories", "food", "curator"], "Devam")),
        ("stored fields in the file", _set(["version"], 3)),
        ("no setup costs", _set(["setup_costs"], {})),
        ("setup id not snake_case", _rename_setup_cost),
    ]


@pytest.mark.parametrize(("name", "change"), _slips(), ids=[n for n, _ in _slips()])
def test_a_slip_in_the_file_is_refused(tmp_path: Path, name: str, change: Edit) -> None:
    directory = _copy(tmp_path)
    _edit(directory, "SG", change)

    with pytest.raises((ValidationError, ValueError)):
        load_baselines(directory)


def test_a_file_named_for_one_host_cannot_hold_another(tmp_path: Path) -> None:
    directory = _copy(tmp_path)
    shutil.copy(directory / "AU.json", directory / "SG.json")

    with pytest.raises(ValueError, match="name the file AU.json"):
        load_baseline(directory / "SG.json")


def test_only_lists_the_hosts_to_check_and_ignores_the_rest(tmp_path: Path) -> None:
    directory = _copy(tmp_path)
    _edit(directory, "AU", _set(["currency"], "SGD"))

    assert set(load_baselines(directory, only=["SG"])) == {"SG"}
    with pytest.raises(ValidationError):
        load_baselines(directory)


def test_only_a_host_that_has_no_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing file"):
        load_baselines(_copy(tmp_path), only=["KR"])


def test_an_empty_or_missing_folder_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no baseline files"):
        load_baselines(tmp_path)
    with pytest.raises(ValueError, match="not a folder"):
        load_baselines(tmp_path / "nope")


def test_a_bom_at_the_start_of_a_file_is_accepted(tmp_path: Path) -> None:
    directory = _copy(tmp_path)
    path = directory / "SG.json"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())

    assert load_baseline(path).host_country == "SG"


def test_main_prints_ok_per_country(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--only", "SG", "AU"]) == 0

    out = capsys.readouterr().out
    assert "OK   SG SGD: 5 categories" in out and "OK   AU AUD: 5 categories" in out


def test_main_fails_and_says_where(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    directory = _copy(tmp_path)
    _edit(directory, "SG", _set(["categories", "food", "low"], 999))

    assert main(["--input-dir", str(directory)]) == 1

    out = capsys.readouterr().out
    assert out.startswith("FAIL") and "categories.food" in out


def test_main_fails_on_a_missing_folder(tmp_path: Path) -> None:
    assert main(["--input-dir", str(tmp_path / "nope")]) == 1
