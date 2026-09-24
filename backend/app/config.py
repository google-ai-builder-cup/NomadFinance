from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

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


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance, failing fast if required vars are missing."""
    return Settings()
