from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.remittance_compare import CorridorId, RemittanceComparison

# Same bound as `/remittance/recommend`'s MAX_PROVIDERS (remittance_recommend.py): a real
# corridor has at most 44 surveyed services (JP-PH).
MAX_PROVIDERS = 60

MAX_NOTES_CHARS = 500


class TransferLogRequest(BaseModel):
    """Body of `POST /api/v1/remittance/log`.

    `comparison` is the unmodified response of `/remittance/compare`; every stored amount is
    read from its `rpw_id` provider, never typed freely by the client, the same as the
    recommendation step never trusting a provider name Gemini wrote.
    """

    comparison: RemittanceComparison = Field(
        description="The unmodified response of `/remittance/compare`."
    )
    rpw_id: int = Field(description="The service the worker actually used, by its `rpw_id`.")
    entry_date: date | None = Field(
        default=None, description="The day the transfer was sent. Defaults to today (UTC)."
    )
    notes: str | None = Field(
        default=None, max_length=MAX_NOTES_CHARS, description="Free text from the worker."
    )

    @field_validator("comparison")
    @classmethod
    def _bounded(cls, comparison: RemittanceComparison) -> RemittanceComparison:
        if len(comparison.providers) > MAX_PROVIDERS:
            raise ValueError(f"comparison.providers holds more than {MAX_PROVIDERS} entries")
        return comparison

    @field_validator("notes")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class TransferLogResponse(BaseModel):
    """Response of `POST /api/v1/remittance/log` (NF-P2-017): the stored transfer.

    Feeds the Financial Identity Builder (`users/{uid}/transfers`, `fib.md` in the data model).
    """

    transfer_id: str = Field(description="Id of `users/{uid}/transfers/{transfer_id}`.")
    corridor_id: CorridorId
    provider_rpw_id: int
    provider_name: str
    send_amount: float
    send_currency: str
    receive_amount: float
    receive_currency: str
    fee: float
    mid_market_rate: float
    cost_pct: float
    entry_date: date
    notes: str | None
