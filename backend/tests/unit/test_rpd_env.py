"""`infra/monitoring/rpd_env.py`: one file of daily limits feeds both the alerts and the guard."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.integrations.gemini.budget import SHARES

MONITORING = Path(__file__).resolve().parents[3] / "infra" / "monitoring"


def _helper() -> Any:
    spec = importlib.util.spec_from_file_location("rpd_env", MONITORING / "rpd_env.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _limits(**rpd: Any) -> dict[str, Any]:
    tiers = {"a": "REASONING", "b": "EXTRACTION", "c": "CLASSIFICATION", "d": "EMBEDDING"}
    return {"models": {f"model-{k}": {"tier": tiers[k], "rpd": rpd.get(k)} for k in tiers}}


def test_a_limit_becomes_the_variable_the_backend_reads() -> None:
    pairs, unset = _helper().rpd_env(_limits(a=500, c=1500))

    assert pairs == ["GEMINI_RPD_REASONING=500", "GEMINI_RPD_CLASSIFICATION=1500"]
    assert unset == ["model-b", "model-d"]


@pytest.mark.parametrize("bad", [0, -1, 1.5, "500", True])
def test_a_limit_that_is_not_a_whole_number_above_zero_stops_the_deploy(bad: Any) -> None:
    with pytest.raises(ValueError, match="whole number"):
        _helper().rpd_env(_limits(a=bad))


def test_every_tier_in_the_limits_file_is_a_setting_and_has_shares() -> None:
    limits = json.loads((MONITORING / "quota-limits.json").read_text(encoding="utf-8"))
    pairs, unset = _helper().rpd_env(
        {"models": {m: {**e, "rpd": 100} for m, e in limits["models"].items()}}
    )

    settings = Settings(
        app_env="local",
        gemini_api_key="k",
        _env_file=None,
        **{pair.split("=")[0].lower(): 100 for pair in pairs},
    )
    tiers = {entry["tier"].lower() for entry in limits["models"].values()}
    assert set(settings.gemini_rpd) == tiers == set(SHARES)
    assert unset == []
