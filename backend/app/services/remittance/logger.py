from __future__ import annotations

import logging
from datetime import datetime

from fastapi.concurrency import run_in_threadpool

from app.repositories.fib_repo import EntryKind, FibRepository
from app.schemas.remittance_compare import ProviderResult, RemittanceComparison
from app.schemas.remittance_log import TransferLogRequest, TransferLogResponse

logger = logging.getLogger(__name__)

SOURCE = "remittance_log"
KIND: EntryKind = "transfers"


class ProviderNotInComparisonError(Exception):
    """`rpw_id` is not one of `comparison`'s comparable, ranked providers.

    A provider that pays out in another currency, or that never made the ranked list, has no
    `recipient_receives`, so there is nothing correct to log as `receive_amount`.
    """


def _chosen_provider(comparison: RemittanceComparison, rpw_id: int) -> ProviderResult:
    for provider in comparison.providers:
        if (
            provider.rpw_id == rpw_id
            and provider.comparable
            and provider.recipient_receives is not None
        ):
            return provider
    raise ProviderNotInComparisonError(f"rpw_id {rpw_id} is not a comparable, ranked provider")


async def log_transfer(
    uid: str, body: TransferLogRequest, transfers: FibRepository, now: datetime
) -> TransferLogResponse:
    """Store a transfer the worker actually sent, read from the comparison they chose it in.

    Every financial figure comes from `body.comparison`'s own `rpw_id` row, never typed freely
    by the client: the same reasoning as the recommendation step (NF-P2-016) never trusting a
    provider name Gemini wrote over the comparison's own top-ranked one.

    Args:
        uid: The signed-in worker.
        body: The unmodified `/compare` response and the `rpw_id` they actually used.
        transfers: Repository for `users/{uid}/transfers`.
        now: Current UTC time, used only when `entry_date` is omitted.

    Returns:
        The stored entry, with its new `transfer_id`.

    Raises:
        ProviderNotInComparisonError: `rpw_id` is not a comparable, ranked provider of `comparison`.
    """
    provider = _chosen_provider(body.comparison, body.rpw_id)
    entry_date = body.entry_date or now.date()
    entry_id = await run_in_threadpool(transfers.new_id, uid, KIND)

    data: dict[str, object] = {
        "entry_date": entry_date.isoformat(),
        "corridor_id": body.comparison.corridor_id,
        "provider_name": provider.firm,
        "provider_rpw_id": provider.rpw_id,
        "send_amount": body.comparison.send_amount,
        "send_currency": body.comparison.send_currency,
        "receive_amount": provider.recipient_receives,
        "receive_currency": body.comparison.receive_currency,
        "fee": provider.fee,
        "mid_market_rate": body.comparison.rate.rate,
        "cost_pct": provider.total_cost_pct,
        "source": SOURCE,
    }
    if body.notes:
        data["notes"] = body.notes

    await run_in_threadpool(transfers.save_entry, uid, KIND, entry_id, data)
    logger.info(
        "remittance_log_transfer corridor=%s rpw_id=%d entry_date=%s",
        body.comparison.corridor_id,
        provider.rpw_id,
        entry_date,
    )
    return TransferLogResponse(
        transfer_id=entry_id,
        corridor_id=body.comparison.corridor_id,
        provider_rpw_id=provider.rpw_id,
        provider_name=provider.firm,
        send_amount=body.comparison.send_amount,
        send_currency=body.comparison.send_currency,
        receive_amount=provider.recipient_receives,
        receive_currency=body.comparison.receive_currency,
        fee=provider.fee,
        mid_market_rate=body.comparison.rate.rate,
        cost_pct=provider.total_cost_pct,
        entry_date=entry_date,
        notes=body.notes,
    )
