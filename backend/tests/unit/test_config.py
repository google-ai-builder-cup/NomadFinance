from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_deployed_environments_require_cron_auth() -> None:
    with pytest.raises(ValidationError, match="CRON_SERVICE_ACCOUNT"):
        Settings(app_env="prod", gemini_api_key="k", _env_file=None)


def test_prod_with_cron_auth_is_valid() -> None:
    settings = Settings(
        app_env="prod",
        gemini_api_key="k",
        cron_service_account="sa@p.iam.gserviceaccount.com",
        cron_audience="https://api.example",
        _env_file=None,
    )
    assert settings.cron_audience == "https://api.example"


def test_local_dev_needs_no_cron_auth() -> None:
    settings = Settings(app_env="local", gemini_api_key="k", _env_file=None)
    assert settings.cron_service_account is None


_DEPLOYED = {
    "gemini_api_key": "k",
    "cron_service_account": "sa@p.iam.gserviceaccount.com",
    "cron_audience": "https://api.example",
    "_env_file": None,
}


@pytest.mark.parametrize(
    "variable",
    ["FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST", "FIREBASE_STORAGE_EMULATOR_HOST"],
)
@pytest.mark.parametrize("app_env", ["staging", "prod"])
def test_a_deployed_environment_refuses_to_start_with_an_emulator_variable(
    monkeypatch: pytest.MonkeyPatch, variable: str, app_env: str
) -> None:
    # With the Auth emulator variable set, firebase-admin stops checking token signatures and
    # trusts whatever the token says: anyone could sign in as anyone (NF-P4-004).
    monkeypatch.setenv(variable, "127.0.0.1:9099")

    with pytest.raises(ValidationError, match=variable):
        Settings(app_env=app_env, **_DEPLOYED)  # type: ignore[arg-type]


def test_local_dev_may_use_the_emulators(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8085")

    assert Settings(app_env="local", gemini_api_key="k", _env_file=None).app_env == "local"


def test_an_empty_emulator_variable_is_not_an_emulator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "")

    assert Settings(app_env="prod", **_DEPLOYED).app_env == "prod"  # type: ignore[arg-type]


def test_no_daily_limit_is_set_by_default_so_the_budget_guard_is_off() -> None:
    settings = Settings(app_env="local", gemini_api_key="k", _env_file=None)

    assert settings.gemini_rpd == {}


def test_the_daily_limits_that_are_set_are_listed_by_tier() -> None:
    settings = Settings(
        app_env="local",
        gemini_api_key="k",
        gemini_rpd_reasoning=500,
        gemini_rpd_embedding=1500,
        _env_file=None,
    )

    assert settings.gemini_rpd == {"reasoning": 500, "embedding": 1500}


def test_the_daily_limits_are_read_from_the_variables_the_deploy_script_sets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_RPD_CLASSIFICATION", "1500")

    settings = Settings(app_env="local", gemini_api_key="k", _env_file=None)

    assert settings.gemini_rpd == {"classification": 1500}


@pytest.mark.parametrize("value", [0, -5])
def test_a_daily_limit_must_be_above_zero(value: int) -> None:
    with pytest.raises(ValidationError, match="gemini_rpd_reasoning"):
        Settings(app_env="local", gemini_api_key="k", gemini_rpd_reasoning=value, _env_file=None)
