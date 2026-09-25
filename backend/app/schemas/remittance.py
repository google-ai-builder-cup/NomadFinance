from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProviderAttemptOut(BaseModel):
    provider: str
    ok: bool
    error: str | None = None


class RefreshedPair(BaseModel):
    pair: str = Field(description="Firestore id, e.g. SGD_PHP")
    rate: float
    provider: str
    rate_date: str


class FailedPair(BaseModel):
    pair: str
    attempts: list[ProviderAttemptOut]


class RefreshRatesResponse(BaseModel):
    """Result of `POST /api/v1/internal/refresh-rates`."""

    history_point: str = Field(description="rates_history point id written, e.g. 2026-09-27T08")
    refreshed: list[RefreshedPair]
    failed: list[FailedPair]
    completed_at: datetime
