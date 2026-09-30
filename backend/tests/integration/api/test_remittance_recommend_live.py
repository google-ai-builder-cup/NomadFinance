"""End-to-end: real request through the app to real Gemini; auth faked. Uses a hand-built
comparison (the shape `POST /remittance/compare` returns), so no Firestore is touched.

Opt-in because it needs GEMINI_API_KEY in .env.local. Classification tier, a separate quota
from the reasoning tier that D-58 found exhausted, and the answers are short (about 3 calls):

    RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_remittance_recommend_live.py -v -s

`-s` prints each recommendation, for a person to read.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.schemas.user import AuthenticatedUser

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
)

URL = "/api/v1/remittance/recommend"


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="live-test")
    with TestClient(app) as client:
        yield client


def _provider(rpw_id: int, firm: str, rank: int, receives: float, **over: Any) -> dict[str, Any]:
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
        "comparable": True,
        "rank": rank,
        "estimated": False,
        "fee": 3.3,
        "fx_margin_pct": 0.07,
        "rate_cost": 0.35,
        "total_cost": 3.65,
        "total_cost_pct": 0.73,
        "recipient_receives": receives,
        "lost_to_costs": 24453.0 - receives,
        "less_than_best": 0.0 if rank == 1 else 24274.33 - receives,
    }
    return values | over


BEST = _provider(521250759, "InstaReM", 1, 24274.33)
WORST = _provider(
    521255281, "Maybank", 2, 21367.03, fee=40.0, fx_margin_pct=23.10, total_cost_pct=12.62
)

COMPARISON: dict[str, Any] = {
    "corridor_id": "SG-PH",
    "send_amount": 500.0,
    "send_currency": "SGD",
    "receive_currency": "PHP",
    "rate": {
        "pair": "SGD_PHP",
        "rate": 43.2,
        "source": "live",
        "provider": "frankfurter",
        "rate_date": "2026-09-28",
        "fetched_at": "2026-09-28T11:40:00Z",
        "stale": False,
    },
    "survey": {
        "period": "2025_1Q",
        "surveyed_from": "2025-02-05",
        "surveyed_to": "2025-02-28",
        "source_name": "World Bank Remittance Prices Worldwide",
        "source_url": "http://remittanceprices.worldbank.org",
        "attribution": "The World Bank, Remittance Prices Worldwide",
    },
    "providers": [BEST, WORST],
    "summary": {
        "comparable_count": 2,
        "best_rpw_id": 521250759,
        "best_firm": "InstaReM",
        "best_recipient_receives": 24274.33,
        "worst_rpw_id": 521255281,
        "worst_firm": "Maybank",
        "worst_recipient_receives": 21367.03,
        "extra_vs_worst": 2907.30,
        "mid_market_receives": 24453.0,
        "median_total_cost_pct": 6.68,
    },
}

TREND: dict[str, Any] = {
    "corridor_id": "SG-PH",
    "pair": "SGD_PHP",
    "base_currency": "SGD",
    "quote_currency": "PHP",
    "days": 90,
    "points": [],
    "summary": None,
    "last_date": "2026-09-28",
    "best_day": {"weekday": "wednesday", "advantage_pct": 0.3, "weeks": 12, "beat_share": 0.75},
    "best_day_reason": None,
    "weeks_analysed": 12,
    "weekdays": [],
    "providers": ["frankfurter"],
}


def recommend(api: TestClient, language: str, with_trend: bool) -> dict[str, Any]:
    body = {"comparison": COMPARISON, "target_language": language}
    if with_trend:
        body["trend"] = TREND
    started = time.perf_counter()
    response = api.post(URL, json=body)
    result: dict[str, Any] = response.json()
    elapsed = time.perf_counter() - started
    print(f"\n[{language}, trend={with_trend}] {response.status_code} in {elapsed:.1f}s")
    print("headline:   ", result.get("headline"))
    print("explanation:", result.get("explanation"))
    print("timing_tip: ", result.get("timing_tip"))
    assert response.status_code == 200, result
    return result


def test_recommends_instarem_in_hindi_with_a_wednesday_tip(api: TestClient) -> None:
    result = recommend(api, "hi", with_trend=True)

    assert (result["recommended_rpw_id"], result["recommended_firm"]) == (521250759, "InstaReM")
    assert result["timing_tip"] is not None
    for word in ("InstaReM", "Maybank"):
        assert word in result["headline"] or word in result["explanation"]


def test_recommends_instarem_in_nepali_without_a_trend(api: TestClient) -> None:
    result = recommend(api, "ne", with_trend=False)

    assert result["recommended_firm"] == "InstaReM"
    assert result["timing_tip"] is None


def test_recommends_instarem_in_tagalog(api: TestClient) -> None:
    result = recommend(api, "tl", with_trend=False)

    assert result["recommended_firm"] == "InstaReM"
