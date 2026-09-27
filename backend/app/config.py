from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from limits import parse_many
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved from this file so settings load the same way whether the app starts from
# backend/, the repo root, or a test runner. Missing file is fine: Cloud Run injects env vars.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env.local"

# The Firebase Hosting sites in prod; the Vite dev server and `vite preview` locally.
_DEFAULT_CORS_ORIGINS: dict[str, tuple[str, ...]] = {
    "local": (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ),
    "staging": ("https://nomadfinance-prod.web.app", "https://nomadfinance-prod.firebaseapp.com"),
    "prod": ("https://nomadfinance-prod.web.app", "https://nomadfinance-prod.firebaseapp.com"),
}
_ORIGIN = re.compile(r"^https?://[a-z0-9.-]+(:\d{1,5})?$")
# Boundaries and part headers of a one-file multipart form are well under 1 KB.
_MULTIPART_OVERHEAD_BYTES = 64 * 1024


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
    # PDF contract extraction writes out the whole document: about 2.6 s per page (NF-P2-001),
    # so a 20-page PDF needs about 55 s. 3 attempts x 90 s + backoff stay under Cloud Run's
    # 300 s request limit. Photos (one page) keep gemini_timeout_seconds.
    gemini_extraction_timeout_seconds: float = Field(default=90.0, gt=0)
    gemini_max_attempts: int = Field(default=3, ge=1)

    # Bucket holding users' files (contracts/{uid}/, bills/{uid}/, exports/{uid}/), deleted
    # with the account. Local dev with the Storage emulator can override it.
    firebase_storage_bucket: str = "nomadfinance-prod.firebasestorage.app"
    # Deleting an account cannot be undone, so it needs a sign-in this recent (seconds).
    account_deletion_max_login_age_seconds: int = Field(default=300, gt=0)

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

    # Browser origins allowed to call the API (CORS). Empty means the defaults for APP_ENV
    # below. Override as a JSON list: CORS_ALLOWED_ORIGINS='["https://example.web.app"]'.
    cors_allowed_origins: list[str] = []

    # Per caller (user, or IP without a token), in the `limits` notation ("60/minute").
    # Memory storage: counted per Cloud Run instance, reset when an instance restarts.
    rate_limit_enabled: bool = True
    rate_limit_default: str = "60/minute"
    # Endpoints that call Gemini share one free-tier quota across all users.
    rate_limit_ai: str = "10/minute"

    @model_validator(mode="after")
    def _require_cron_auth_when_deployed(self) -> Settings:
        if self.app_env != "local" and not (self.cron_service_account and self.cron_audience):
            raise ValueError(
                "CRON_SERVICE_ACCOUNT and CRON_AUDIENCE are required when APP_ENV is not local"
            )
        return self

    @model_validator(mode="after")
    def _check_cors_and_rate_limits(self) -> Settings:
        if not self.cors_allowed_origins:
            self.cors_allowed_origins = list(_DEFAULT_CORS_ORIGINS[self.app_env])
        for origin in self.cors_allowed_origins:
            # An origin is scheme://host[:port] exactly; browsers never send a path or "*".
            if not _ORIGIN.match(origin):
                raise ValueError(f"CORS_ALLOWED_ORIGINS: {origin!r} is not an origin")
        for name in ("rate_limit_default", "rate_limit_ai"):
            try:
                parse_many(getattr(self, name))
            except ValueError as exc:
                raise ValueError(f"{name.upper()}: {exc}") from exc
        return self

    @property
    def request_max_bytes(self) -> int:
        """Largest request body accepted: one upload plus room for the multipart framing."""
        return self.upload_max_bytes + _MULTIPART_OVERHEAD_BYTES


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance, failing fast if required vars are missing."""
    return Settings()
