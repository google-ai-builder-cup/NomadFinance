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
