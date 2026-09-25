from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved from this file so settings load the same way whether the app starts from
# backend/, the repo root, or a test runner. Missing file is fine: Cloud Run injects env vars.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env.local"


class Settings(BaseSettings):
    """Process-wide configuration read from environment variables.

    Local dev reads `backend/.env.local`; staging and prod receive values from
    Cloud Run env vars and Secret Manager.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "staging", "prod"]
    app_name: str = "NomadFinance API"
    app_version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Not a secret — just tells the Firebase Admin SDK which project to talk to.
    # Prod uses nomadfinance-prod via the Cloud Run service account (ADC). For local
    # dev against the Firebase Emulator Suite, override to any project id and set
    # FIRESTORE_EMULATOR_HOST / FIREBASE_AUTH_EMULATOR_HOST (see
    # docs/runbooks/NF-P1-001-local-dev-setup.md).
    firebase_project_id: str = "nomadfinance-prod"

    # Local: backend/.env.local. Prod: Secret Manager `gemini-api-key`, mounted by Cloud Run.
    gemini_api_key: SecretStr
    # One model per tier so each tier draws on its own per-model quota. Rationale and
    # history in docs/decisions/ADR-002-multi-model-gemini-strategy.md.
    gemini_model_reasoning: str = "gemini-3.5-flash"
    gemini_model_extraction: str = "gemini-3.5-flash-lite"
    gemini_model_classification: str = "gemini-3.1-flash-lite"
    gemini_timeout_seconds: float = Field(default=30.0, gt=0)
    gemini_max_attempts: int = Field(default=3, ge=1)

    # Uploads are sent to Gemini inline, which caps a whole request at about 20 MB.
    # 10 MB covers multi-page phone scans and leaves room for the prompt.
    upload_max_bytes: int = Field(default=10 * 1024 * 1024, gt=0)

    # Cloud Scheduler signs its calls to /api/v1/internal/* with a Google OIDC token for this
    # service account and audience. Required outside local dev (checked below).
    cron_service_account: str | None = None
    cron_audience: str | None = None

    # FX failover chain (ADR-006). Frankfurter and ExchangeRate-API need no key; the two
    # keyed providers are skipped while their key is unset.
    fx_timeout_seconds: float = Field(default=10.0, gt=0)
    currencyfreaks_api_key: SecretStr | None = None
    wise_api_token: SecretStr | None = None

    @model_validator(mode="after")
    def _require_cron_auth_when_deployed(self) -> Settings:
        if self.app_env != "local" and not (self.cron_service_account and self.cron_audience):
            raise ValueError(
                "CRON_SERVICE_ACCOUNT and CRON_AUDIENCE are required when APP_ENV is not local"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance, failing fast if required vars are missing."""
    return Settings()
