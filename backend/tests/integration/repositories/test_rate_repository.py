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


def test_the_daily_map_keeps_every_market_day_across_runs() -> None:
    client = get_firestore_client()
    repo = RateRepository(client)
    pair = CURRENCY_PAIRS[3]  # MYR_IDR
    attempts = [ProviderAttempt("frankfurter", True)]
    thursday = FxQuote(base="MYR", rates={"IDR": 3570.5}, rate_date="2026-09-24")
    friday = FxQuote(base="MYR", rates={"IDR": 3581.25}, rate_date="2026-09-25")
    friday_again = FxQuote(base="MYR", rates={"IDR": 3582.0}, rate_date="2026-09-25")
    undated = FxQuote(base="MYR", rates={"IDR": 3590.0}, rate_date="None")

    repo.save_pair(pair, thursday, "frankfurter", attempts, datetime(2026, 9, 24, 16, tzinfo=UTC))
    repo.save_pair(pair, friday, "frankfurter", attempts, datetime(2026, 9, 25, 16, tzinfo=UTC))
    # Saturday's run gets Friday's rate again: it rewrites Friday, it adds no Saturday.
    repo.save_pair(
        pair, friday_again, "exchangerate_api", attempts, datetime(2026, 9, 26, 10, tzinfo=UTC)
    )
    # A provider without a usable date is filed under the run's own UTC day.
    repo.save_pair(pair, undated, "currencyfreaks", attempts, datetime(2026, 9, 27, 6, tzinfo=UTC))

    history = repo.get_history("MYR_IDR")
    assert history is not None
    assert history["base_currency"] == "MYR" and history["updated_at"] is not None
    assert history["daily"] == {
        "2026-09-24": {"rate": 3570.5, "provider": "frankfurter", "source": "cron"},
        "2026-09-25": {"rate": 3582.0, "provider": "exchangerate_api", "source": "cron"},
        "2026-09-27": {"rate": 3590.0, "provider": "currencyfreaks", "source": "cron"},
    }
    points = [p.id for p in client.collection("rates_history/MYR_IDR/points").stream()]
    assert points == ["2026-09-24T16", "2026-09-25T16", "2026-09-26T10", "2026-09-27T06"]


def test_get_history_of_a_pair_never_written_is_none() -> None:
    assert RateRepository(get_firestore_client()).get_history("XXX_YYY") is None
