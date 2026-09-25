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
