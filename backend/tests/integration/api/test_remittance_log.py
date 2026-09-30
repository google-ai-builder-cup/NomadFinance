from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.repositories.fib_repo import EntryKind, get_fib_repository
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/remittance/log"

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

NOT_COMPARABLE: dict[str, Any] = PROVIDER | {
    "rpw_id": 2,
    "firm": "USD Direct",
    "payout_currency": "USD",
    "comparable": False,
    "rank": None,
    "recipient_receives": None,
    "lost_to_costs": None,
    "less_than_best": None,
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
    "providers": [PROVIDER, NOT_COMPARABLE],
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

BODY: dict[str, Any] = {"comparison": COMPARISON, "rpw_id": 521250759}


class FakeTransfers:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self._next_id = 0

    def new_id(self, uid: str, kind: EntryKind) -> str:
        self._next_id += 1
        return f"t_{self._next_id}"

    def save_entry(self, uid: str, kind: EntryKind, entry_id: str, data: dict[str, Any]) -> None:
        self.docs[f"{uid}/{kind}/{entry_id}"] = data


@pytest.fixture
def transfers() -> FakeTransfers:
    return FakeTransfers()


@pytest.fixture
def app(transfers: FakeTransfers) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_fib_repository] = lambda: transfers
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_logs_the_chosen_providers_figures(api: TestClient, transfers: FakeTransfers) -> None:
    response = api.post(URL, json=BODY)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["corridor_id"] == "SG-PH"
    assert (body["provider_rpw_id"], body["provider_name"]) == (521250759, "InstaReM")
    assert (body["send_amount"], body["send_currency"]) == (500.0, "SGD")
    assert (body["receive_amount"], body["receive_currency"]) == (24274.33, "PHP")
    assert (body["fee"], body["mid_market_rate"], body["cost_pct"]) == (3.3, 43.2, 0.73)
    assert body["notes"] is None

    stored = transfers.docs["test-user/transfers/t_1"]
    assert stored["source"] == "remittance_log"
    assert stored["provider_rpw_id"] == 521250759


def test_entry_date_and_notes_are_accepted(api: TestClient) -> None:
    response = api.post(URL, json=BODY | {"entry_date": "2026-08-01", "notes": "For rent"})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["entry_date"] == "2026-08-01"
    assert body["notes"] == "For rent"


def test_a_non_comparable_provider_is_a_422(api: TestClient) -> None:
    response = api.post(URL, json=BODY | {"rpw_id": 2})

    assert response.status_code == 422


def test_an_unknown_rpw_id_is_a_422(api: TestClient) -> None:
    response = api.post(URL, json=BODY | {"rpw_id": 999})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {k: v for k, v in BODY.items() if k != "comparison"},
        {k: v for k, v in BODY.items() if k != "rpw_id"},
        BODY | {"comparison": COMPARISON | {"providers": [PROVIDER] * 61}},
    ],
)
def test_invalid_body_is_rejected(api: TestClient, body: dict[str, Any]) -> None:
    assert api.post(URL, json=body).status_code == 422


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        assert client.post(URL, json=BODY).status_code == 401


def test_endpoint_is_documented_in_openapi(api: TestClient) -> None:
    operation = api.get("/openapi.json").json()["paths"][URL]["post"]

    assert {"401", "422", "429"} <= set(operation["responses"])
