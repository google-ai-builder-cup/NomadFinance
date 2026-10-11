"""The demo-day projection's arithmetic, limits and exit codes (NF-HR-010)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "project_demo_usage.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("project_demo_usage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


proj = _load()


def test_an_empty_day_makes_no_requests() -> None:
    totals = proj.project(proj.Scenario(rehearsals=0, live_runs=0, visitors=0))

    assert all(requests == 0 for requests in totals.values())


def test_two_visitors_cost_their_journeys_with_the_retry_allowance() -> None:
    totals = proj.project(proj.Scenario(rehearsals=0, live_runs=0, visitors=2))

    # One plan each (1.33 calls) on the reasoning tier, and two scam explainers each (of the
    # three checks a visitor makes, two are scams).
    assert totals[("coach", "reasoning")] == pytest.approx(2 * 1.33 * proj.OVERHEAD)
    assert totals[("scam", "reasoning")] == pytest.approx(2 * 2 * 1 * proj.OVERHEAD)


def test_the_team_scam_checks_are_free_when_prewarmed_and_cost_when_not() -> None:
    warm = proj.project(proj.Scenario(rehearsals=0, live_runs=2, visitors=0))
    cold = proj.project(
        proj.Scenario(rehearsals=0, live_runs=2, visitors=0, prewarmed_team_scam_checks=False)
    )

    assert warm[("scam", "reasoning")] == 0
    assert cold[("scam", "reasoning")] == pytest.approx(2 * 2 * proj.OVERHEAD)


def test_the_coach_reply_can_be_moved_to_another_model() -> None:
    default = proj.project(proj.Scenario(visitors=10))
    moved = proj.project(proj.Scenario(visitors=10, coach_reply_tier="extraction"))

    assert ("coach", "extraction") not in default
    assert moved[("coach", "extraction")] > 100
    assert moved[("coach", "classification")] < default[("coach", "classification")]


def test_limits_come_from_the_flag_then_the_file_then_the_design_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    limits = {
        "models": {
            "a": {"tier": "REASONING", "rpd": 80},
            "b": {"tier": "EXTRACTION", "rpd": None},
            "c": {"tier": "CLASSIFICATION", "rpd": None},
            "d": {"tier": "EMBEDDING", "rpd": None},
        }
    }
    file = tmp_path / "quota-limits.json"
    file.write_text(json.dumps(limits), encoding="utf-8")
    monkeypatch.setattr(proj, "LIMITS_FILE", file)

    rpd, assumed = proj.read_rpd({"classification": 700})

    assert rpd == {"reasoning": 80, "extraction": 1500, "classification": 700, "embedding": 1500}
    assert assumed == {"extraction", "embedding"}  # a figure read for this project is not assumed


def test_a_plan_over_the_target_exits_1_and_says_which_model(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = proj.main(["--visitors", "60"])

    out = capsys.readouterr().out
    assert code == 1
    assert "classification" in out and "OVER the target" in out and "ASSUMED" in out


def test_a_plan_inside_the_target_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    assert proj.main(["--visitors", "10"]) == 0
    assert "OVER" not in capsys.readouterr().out


def test_the_budget_a_feature_would_hit_is_named(capsys: pytest.CaptureFixture[str]) -> None:
    proj.main(["--visitors", "30"])

    assert "would be REFUSED by its budget" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["reasoning", "reasoning=0", "turbo=5", "reasoning=x"])
def test_a_bad_limit_flag_is_refused(bad: str) -> None:
    with pytest.raises(SystemExit) as raised:
        proj.main(["--rpd", bad])

    assert raised.value.code == 2
