from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from app.constants import CURRENCY_PAIRS
from app.integrations.fx import FxQuote, ProviderAttempt
from app.repositories.base import get_firestore_client
from app.repositories.rate_repo import RateRepository

# Real Firestore writes: only against the emulator (docs/runbooks/NF-P1-019-fx-refresh-cron.md).
pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
)


def test_save_pair_writes_cache_history_header_and_hourly_point() -> None:
    client = get_firestore_client()
    repo = RateRepository(client)
    pair = CURRENCY_PAIRS[0]  # SGD_PHP
    quote = FxQuote(base="SGD", rates={"PHP": 49.026, "INR": 74.974}, rate_date="2026-09-24")
    attempts = [
        ProviderAttempt("frankfurter", False, "timeout"),
        ProviderAttempt("exchangerate_api", True),
    ]
    hour = datetime(2026, 9, 27, 8, tzinfo=UTC)

    repo.save_pair(pair, quote, "exchangerate_api", attempts, hour)
    # A second run in the same hour must overwrite the point, not add a duplicate.
    repo.save_pair(pair, quote, "exchangerate_api", attempts, hour)

    cache = client.document("rates_cache/SGD_PHP").get().to_dict()
    assert cache is not None
    assert cache["rate"] == 49.026
    assert cache["provider"] == "exchangerate_api"
    assert cache["rate_date"] == "2026-09-24"
    assert cache["corridor_ids"] == ["SG-PH"]
    assert cache["schema_version"] == 1
    assert cache["attempts"] == [
        {"provider": "frankfurter", "ok": False, "error": "timeout"},
        {"provider": "exchangerate_api", "ok": True},
    ]
    assert cache["fetched_at"] is not None

    header = client.document("rates_history/SGD_PHP").get().to_dict()
    assert header is not None and header["quote_currency"] == "PHP"

    points = list(client.collection("rates_history/SGD_PHP/points").stream())
    assert [p.id for p in points] == ["2026-09-27T08"]
    assert points[0].to_dict() == {
        "at": hour,
        "rate": 49.026,
        "provider": "exchangerate_api",
        "source": "cron",
    }
