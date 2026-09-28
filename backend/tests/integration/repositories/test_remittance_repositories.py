from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from google.cloud import firestore

from app.constants import CURRENCY_PAIRS
from app.integrations.fx import FxQuote, ProviderAttempt
from app.repositories.base import get_firestore_client
from app.repositories.corridor_repo import CorridorRepository
from app.repositories.rate_repo import RateRepository
from app.services.remittance.engine import compare_remittance

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        "FIRESTORE_EMULATOR_HOST" not in os.environ,
        reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
    ),
]

RPW = Path(__file__).resolve().parents[4] / "data-scripts" / "data" / "processed"
DATA: dict[str, Any] = json.loads((RPW / "rpw_corridors.json").read_text(encoding="utf-8"))


class _Collections:
    """Throwaway collection names, so a run never touches (or trusts) real documents."""

    def __init__(self) -> None:
        suffix = uuid.uuid4().hex[:8]
        self.corridors = f"corridors_test_{suffix}"
        self.rates = f"rates_cache_test_{suffix}"


def _repos() -> tuple[CorridorRepository, RateRepository]:
    names = _Collections()
    corridors = CorridorRepository(get_firestore_client())
    corridors.collection_name = names.corridors
    rates = RateRepository(get_firestore_client())
    rates.collection_name = names.rates
    return corridors, rates


def _load_like_the_loader(corridors: CorridorRepository) -> None:
    for corridor in DATA["corridors"]:
        corridors.set(
            corridor["corridor_id"],
            corridor | {"source": DATA["source"], "loaded_at": firestore.SERVER_TIMESTAMP},
        )


def test_a_loaded_corridor_is_read_back_whole() -> None:
    corridors, _ = _repos()
    _load_like_the_loader(corridors)

    doc = corridors.get_corridor("SG-PH")

    assert doc is not None
    assert doc["corridor_id"] == "SG-PH" and len(doc["providers"]) == 39
    assert doc["source"]["attribution"].startswith("The World Bank")


def test_an_unknown_corridor_is_none() -> None:
    corridors, _ = _repos()

    assert corridors.get_corridor("ZZ-ZZ") is None


def test_the_cron_writes_a_rate_that_is_read_back_by_pair() -> None:
    _, rates = _repos()
    pair = CURRENCY_PAIRS[0]
    quote = FxQuote(base=pair.base, rates={pair.quote: 43.31}, rate_date="2026-09-28")
    rates.save_pair(
        pair, quote, "frankfurter", [ProviderAttempt("frankfurter", True)], datetime.now(UTC)
    )

    doc = rates.get_rate(pair.pair_id)

    assert doc is not None and doc["rate"] == 43.31
    assert doc["fetched_at"].tzinfo is not None
    assert rates.get_rate("XXX_YYY") is None


async def test_a_comparison_runs_on_what_the_loader_and_the_cron_stored() -> None:
    corridors, rates = _repos()
    _load_like_the_loader(corridors)
    pair = CURRENCY_PAIRS[0]
    quote = FxQuote(base=pair.base, rates={pair.quote: 43.31}, rate_date="2026-09-28")
    rates.save_pair(pair, quote, "frankfurter", [], datetime.now(UTC))

    result = await compare_remittance("SG-PH", 500, corridors, rates, datetime.now(UTC))

    assert result.rate.source == "live" and result.rate.rate == 43.31
    assert result.rate.stale is False  # a Firestore timestamp is read as a real UTC time
    assert result.summary.comparable_count == 38
    assert result.providers[0].rank == 1
