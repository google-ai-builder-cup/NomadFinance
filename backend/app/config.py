from __future__ import annotations

import os
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

# Setting any of these points the Firebase libraries at a local emulator. The Auth one is the
# dangerous one: firebase-admin then stops verifying token signatures and trusts the payload.
_EMULATOR_VARIABLES = (
    "FIREBASE_AUTH_EMULATOR_HOST",
    "FIRESTORE_EMULATOR_HOST",
    "FIREBASE_STORAGE_EMULATOR_HOST",
)

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
    # Not a tier: embeddings are a separate endpoint (ADR-002; text-embedding-004 is shut down).
    gemini_model_embedding: str = "gemini-embedding-001"
    gemini_timeout_seconds: float = Field(default=30.0, gt=0)
    # PDF contract extraction writes out the whole document: about 2.6 s per page (NF-P2-001),
    # so a 20-page PDF needs about 55 s. 3 attempts x 90 s + backoff stay under Cloud Run's
    # 300 s request limit. Photos (one page) keep gemini_timeout_seconds.
    gemini_extraction_timeout_seconds: float = Field(default=90.0, gt=0)
    # Clause comparison (NF-P2-004, reasoning tier) took 20 to 33 s for 6 to 25 terms; the
    # default 30 s would fail the longer ones. Same bound as above for Cloud Run.
    gemini_compare_timeout_seconds: float = Field(default=90.0, gt=0)
    # Report translation (NF-P2-005) writes out the whole contract text plus every clause
    # again in another language: comparable output size to extraction, so it gets the same
    # longer bound rather than the 30 s default (classification tier is fast, but the output
    # is not small).
    gemini_translate_timeout_seconds: float = Field(default=60.0, gt=0)
    # The complaint letter (NF-P2-006, reasoning tier) is written twice, once per language,
    # and the reasoning tier spends 13 to 23 s thinking even on short prompts (D-08).
    gemini_complaint_timeout_seconds: float = Field(default=60.0, gt=0)
    # The Financial Identity narrative (NF-P3-013, reasoning tier) took 21 to 40 s in the
    # NF-P1-029 live check (D-08). It runs in the weekly cron, not a user request, so there is
    # no 300 s Cloud Run request limit to fit under, only the scheduler's own deadline.
    gemini_narrative_timeout_seconds: float = Field(default=90.0, gt=0)
    gemini_max_attempts: int = Field(default=3, ge=1)
    # How much of a conversation a chat or streamed reply sends (NF-F0-007): the newest turns
    # that fit both limits, never the whole transcript, so one turn stays inside the model's
    # per-minute token quota. The caller summarises what is left out. The token figure is an
    # estimate (3 characters a token), deliberately high for Hindi and Bengali.
    gemini_chat_history_turns: int = Field(default=24, ge=1)
    gemini_chat_history_tokens: int = Field(default=6000, ge=1)

    # How long a Financial Identity PDF link (NF-P3-014) works. A day is long enough to hand to a
    # lender, short enough to limit a leaked link. V4 signed URLs allow 7 days at most.
    export_url_expiry_minutes: int = Field(default=24 * 60, gt=0, le=7 * 24 * 60)

    # Bucket holding users' files (contracts/{uid}/, bills/{uid}/, exports/{uid}/), deleted
    # with the account. Local dev with the Storage emulator can override it.
    firebase_storage_bucket: str = "nomadfinance-prod.firebasestorage.app"
    # Deleting an account cannot be undone, so it needs a sign-in this recent (seconds).
    account_deletion_max_login_age_seconds: int = Field(default=300, gt=0)

    # HMAC key for `radar_reports.reporter_hash` (NF-P3-001, radar.md). Local: any random
    # string. Prod: Secret Manager `radar-reporter-hash-secret`.
    radar_reporter_hash_secret: SecretStr

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

    # Anti-abuse for POST /radar/report (NF-P3-025). Defaults off: enforcing before the
    # frontend has a real reCAPTCHA v3 site key configured would reject every real
    # submission, not just bots. Flip to true only once a deployed domain's key is wired
    # through (docs/runbooks/NF-P3-025-radar-app-check.md, "Before this works in production").
    app_check_enabled: bool = False

    @model_validator(mode="after")
    def _require_cron_auth_when_deployed(self) -> Settings:
        if self.app_env != "local" and not (self.cron_service_account and self.cron_audience):
            raise ValueError(
                "CRON_SERVICE_ACCOUNT and CRON_AUDIENCE are required when APP_ENV is not local"
            )
        return self

    @model_validator(mode="after")
    def _refuse_emulators_when_deployed(self) -> Settings:
        if self.app_env != "local":
            for name in _EMULATOR_VARIABLES:
                if os.environ.get(name):
                    raise ValueError(
                        f"{name} is set but APP_ENV is {self.app_env}: with an emulator "
                        "variable set, firebase-admin skips token signature checks"
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
