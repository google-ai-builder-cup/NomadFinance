from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.gemini import GeminiResponseError, GeminiUnavailableError, get_gemini_client
from app.main import create_app
from app.schemas.remittance_recommend import RecommendationAnswer
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/remittance/recommend"

PROVIDER: dict[str, Any] = {
    "rpw_id": 521250759,
    "firm": "InstaReM",
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
    "rank": 1,
    "estimated": False,
    "fee": 3.3,
    "fx_margin_pct": 0.07,
    "rate_cost": 0.35,
    "total_cost": 3.65,
    "total_cost_pct": 0.73,
    "recipient_receives": 24274.33,
    "lost_to_costs": 178.67,
    "less_than_best": 0.0,
}

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
    "providers": [PROVIDER],
    "summary": {
        "comparable_count": 1,
        "best_rpw_id": 521250759,
        "best_firm": "InstaReM",
        "best_recipient_receives": 24274.33,
        "worst_rpw_id": 521250759,
        "worst_firm": "InstaReM",
        "worst_recipient_receives": 24274.33,
        "extra_vs_worst": 0.0,
        "mid_market_receives": 24453.0,
        "median_total_cost_pct": 0.73,
    },
}

BODY: dict[str, Any] = {"comparison": COMPARISON, "target_language": "hi"}

ANSWER: dict[str, Any] = {
    "best_provider": "InstaReM",
    "headline": "Send with InstaReM: your family gets more.",
    "explanation": "InstaReM's fee and rate markup are lower than the alternatives.",
    "timing_tip": None,
}


class FakeGemini:
    def __init__(self) -> None:
        self.outcome: RecommendationAnswer | Exception = RecommendationAnswer.model_validate(ANSWER)
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> RecommendationAnswer:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def fake_gemini() -> FakeGemini:
    return FakeGemini()


@pytest.fixture
def app(fake_gemini: FakeGemini) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_gemini_client] = lambda: fake_gemini
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_returns_the_recommendation_with_the_top_provider_set_by_code(api: TestClient) -> None:
    response = api.post(URL, json=BODY)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["corridor_id"] == "SG-PH" and body["target_language"] == "hi"
    assert (body["recommended_rpw_id"], body["recommended_firm"]) == (521250759, "InstaReM")
    assert body["headline"] == ANSWER["headline"]
    assert body["timing_tip"] is None


def test_trend_is_optional(api: TestClient) -> None:
    assert api.post(URL, json=BODY).status_code == 200


def test_a_wrong_recommended_provider_is_a_502(api: TestClient, fake_gemini: FakeGemini) -> None:
    fake_gemini.outcome = RecommendationAnswer.model_validate(ANSWER | {"best_provider": "Wise"})

    response = api.post(URL, json=BODY)

    assert response.status_code == 502
    assert "Wise" not in response.text


def test_an_empty_explanation_is_a_502(api: TestClient, fake_gemini: FakeGemini) -> None:
    fake_gemini.outcome = RecommendationAnswer.model_validate(ANSWER | {"explanation": "  "})

    assert api.post(URL, json=BODY).status_code == 502


@pytest.mark.parametrize(
    "body",
    [
        BODY | {"target_language": "fr"},
        BODY | {"target_language": "HI"},
        {k: v for k, v in BODY.items() if k != "target_language"},
        {k: v for k, v in BODY.items() if k != "comparison"},
        BODY | {"comparison": COMPARISON | {"providers": []}},
        BODY
        | {
            "comparison": COMPARISON
            | {"providers": [PROVIDER | {"rank": None, "comparable": False}]}
        },
    ],
)
def test_invalid_body_is_rejected_before_gemini(
    api: TestClient, fake_gemini: FakeGemini, body: dict[str, Any]
) -> None:
    response = api.post(URL, json=body)

    assert response.status_code == 422
    assert fake_gemini.calls == []


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (GeminiUnavailableError("gemini-x: 503 UNAVAILABLE"), 503),
        (GeminiResponseError("gemini-x output did not match RecommendationAnswer"), 502),
    ],
)
def test_gemini_failures_map_to_clean_errors(
    api: TestClient, fake_gemini: FakeGemini, error: Exception, status_code: int
) -> None:
    fake_gemini.outcome = error

    response = api.post(URL, json=BODY)

    assert response.status_code == status_code
    assert "gemini-x" not in response.text


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        assert client.post(URL, json=BODY).status_code == 401


def test_endpoint_is_documented_in_openapi(api: TestClient) -> None:
    operation = api.get("/openapi.json").json()["paths"][URL]["post"]

    assert {"401", "422", "429", "502", "503", "504"} <= set(operation["responses"])
