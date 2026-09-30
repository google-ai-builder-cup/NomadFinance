from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.repositories.fib_repo import EntryKind
from app.schemas.remittance_compare import (
    ComparisonSummary,
    ProviderResult,
    RateInfo,
    RemittanceComparison,
    SurveyInfo,
)
from app.schemas.remittance_log import TransferLogRequest
from app.services.remittance.logger import ProviderNotInComparisonError, log_transfer

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _provider(
    rpw_id: int, firm: str, rank: int | None, comparable: bool = True, **over: Any
) -> ProviderResult:
    values: dict[str, Any] = {
        "rpw_id": rpw_id,
        "firm": firm,
        "firm_type": "Money Transfer Operator",
        "payment_instrument": "Bank account transfer",
        "access_point": "Internet",
        "pickup_method": "Bank account",
        "speed": "Same day",
        "speed_order": 1,
        "network_coverage": "Medium",
        "note": None,
        "payout_currency": "PHP",
        "comparable": comparable,
        "rank": rank,
        "estimated": False,
        "fee": 3.3,
        "fx_margin_pct": 0.07,
        "rate_cost": 0.35,
        "total_cost": 3.65,
        "total_cost_pct": 0.73,
        "recipient_receives": 24274.17 if comparable else None,
        "lost_to_costs": 178.83 if comparable else None,
        "less_than_best": 0.0 if rank == 1 else (100.0 if comparable else None),
    }
    return ProviderResult.model_validate(values | over)


def _comparison(*providers: ProviderResult, **over: Any) -> RemittanceComparison:
    ranked = [p for p in providers if p.comparable]
    best, worst = ranked[0], ranked[-1]
    values: dict[str, Any] = {
        "corridor_id": "SG-PH",
        "send_amount": 500.0,
        "send_currency": "SGD",
        "receive_currency": "PHP",
        "rate": RateInfo(
            pair="SGD_PHP",
            rate=43.2,
            source="live",
            provider="frankfurter",
            rate_date="2026-09-28",
            fetched_at=None,
            stale=False,
        ),
        "survey": SurveyInfo(
            period="2025_1Q",
            surveyed_from="2025-02-05",
            surveyed_to="2025-02-28",
            source_name="World Bank Remittance Prices Worldwide",
            source_url="http://remittanceprices.worldbank.org",
            attribution="The World Bank, Remittance Prices Worldwide",
        ),
        "providers": list(providers),
        "summary": ComparisonSummary(
            comparable_count=len(ranked),
            best_rpw_id=best.rpw_id,
            best_firm=best.firm,
            best_recipient_receives=best.recipient_receives or 0.0,
            worst_rpw_id=worst.rpw_id,
            worst_firm=worst.firm,
            worst_recipient_receives=worst.recipient_receives or 0.0,
            extra_vs_worst=(best.recipient_receives or 0.0) - (worst.recipient_receives or 0.0),
            mid_market_receives=24453.0,
            median_total_cost_pct=1.74,
        ),
    }
    return RemittanceComparison.model_validate(values | over)


class FakeTransfers:
    """Stands in for `FibRepository`, just for `transfers`."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self._next_id = 0

    def new_id(self, uid: str, kind: EntryKind) -> str:
        self._next_id += 1
        return f"t_{self._next_id}"

    def save_entry(self, uid: str, kind: EntryKind, entry_id: str, data: dict[str, Any]) -> None:
        self.docs[f"{uid}/{kind}/{entry_id}"] = data


async def test_logs_the_chosen_providers_own_figures() -> None:
    provider = _provider(521250759, "InstaReM", rank=1)
    comparison = _comparison(provider)
    body = TransferLogRequest(comparison=comparison, rpw_id=521250759)
    transfers = FakeTransfers()

    result = await log_transfer("uid_priya", body, transfers, NOW)  # type: ignore[arg-type]

    assert result.transfer_id == "t_1"
    assert (result.provider_rpw_id, result.provider_name) == (521250759, "InstaReM")
    assert (result.send_amount, result.send_currency) == (500.0, "SGD")
    assert (result.receive_amount, result.receive_currency) == (24274.17, "PHP")
    assert (result.fee, result.mid_market_rate, result.cost_pct) == (3.3, 43.2, 0.73)
    assert result.entry_date == date(2026, 9, 30)
    assert result.notes is None

    stored = transfers.docs["uid_priya/transfers/t_1"]
    assert stored["source"] == "remittance_log"
    assert stored["corridor_id"] == "SG-PH"
    assert stored["entry_date"] == "2026-09-30"
    assert "notes" not in stored


async def test_entry_date_defaults_to_today_when_omitted() -> None:
    provider = _provider(1, "Wise", rank=1)
    body = TransferLogRequest(comparison=_comparison(provider), rpw_id=1)

    result = await log_transfer("uid", body, FakeTransfers(), NOW)  # type: ignore[arg-type]

    assert result.entry_date == NOW.date()


async def test_a_given_entry_date_is_kept() -> None:
    provider = _provider(1, "Wise", rank=1)
    body = TransferLogRequest(
        comparison=_comparison(provider), rpw_id=1, entry_date=date(2026, 8, 1)
    )

    result = await log_transfer("uid", body, FakeTransfers(), NOW)  # type: ignore[arg-type]

    assert result.entry_date == date(2026, 8, 1)


async def test_notes_are_stored_when_given() -> None:
    provider = _provider(1, "Wise", rank=1)
    body = TransferLogRequest(comparison=_comparison(provider), rpw_id=1, notes="For rent")
    transfers = FakeTransfers()

    result = await log_transfer("uid", body, transfers, NOW)  # type: ignore[arg-type]

    assert result.notes == "For rent"
    assert transfers.docs["uid/transfers/t_1"]["notes"] == "For rent"


async def test_blank_notes_are_dropped_by_the_request_model() -> None:
    body = TransferLogRequest(
        comparison=_comparison(_provider(1, "Wise", rank=1)), rpw_id=1, notes="   "
    )

    assert body.notes is None


@pytest.mark.parametrize(
    "rpw_id",
    [999, 2],
)
async def test_an_unknown_or_non_comparable_rpw_id_is_rejected(rpw_id: int) -> None:
    ranked = _provider(1, "Wise", rank=1)
    not_comparable = _provider(2, "USD Direct", rank=None, comparable=False)
    body = TransferLogRequest(comparison=_comparison(ranked, not_comparable), rpw_id=rpw_id)

    with pytest.raises(ProviderNotInComparisonError):
        await log_transfer("uid", body, FakeTransfers(), NOW)  # type: ignore[arg-type]
