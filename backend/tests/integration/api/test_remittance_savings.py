from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.repositories.corridor_repo import get_corridor_repository
from app.repositories.rate_repo import get_rate_repository
from app.schemas.user import AuthenticatedUser
from app.services.remittance.savings import target_months

URL = "/api/v1/remittance/savings"

SOURCE = {"name": "World Bank", "url": "http://remittanceprices.worldbank.org", "attribution": "x"}


def provider(rpw_id: int, firm: str, total_cost_pct: float) -> dict[str, Any]:
    quote = {
        "send_amount_lcu": 200,
        "fee_lcu": 0,
        "fx_margin_pct": total_cost_pct,
        "total_cost_pct": total_cost_pct,
    }
    return {
        "rpw_id": rpw_id,
        "firm": firm,
        "firm_type": "Money Transfer Operator",
        "payment_instrument": "Cash",
        "access_point": "Agent",
        "pickup_method": "Cash",
        "speed": "Same day",
        "network_coverage": None,
        "note": None,
        "payout_currency": "PHP",
        "interbank_rate": 43.0,
        "surveyed_on": "2025-02-10",
        "quote_200": quote,
        "quote_500": quote | {"send_amount_lcu": 500},
    }


CORRIDOR: dict[str, Any] = {
    "corridor_id": "SG-PH",
    "source_currency": "SGD",
    "destination_currency": "PHP",
    "period": "2025_1Q",
    "providers": [provider(1, "Cheap", 0.0), provider(2, "Pricey", 10.0)],
    "source": SOURCE,
}

# Computed against the real current month, not a fixed date, so the test stays correct
# whatever day it runs on. Rate 40, 41, 42 for the three months just before this one.
NOW = datetime.now(UTC)
THREE_MONTHS = target_months((NOW.year, NOW.month), 3)
MONTH_LABELS = [f"{year:04d}-{month:02d}" for year, month in THREE_MONTHS]
HISTORY: dict[str, Any] = {
    "base_currency": "SGD",
    "quote_currency": "PHP",
    "daily": {
        f"{year:04d}-{month:02d}-10": {"rate": 40.0 + index, "provider": "frankfurter"}
        for index, (year, month) in enumerate(THREE_MONTHS)
    },
}


class FakeCorridors:
    def __init__(self) -> None:
        self.docs: dict[str, Any] = {"SG-PH": CORRIDOR}

    def get_corridor(self, corridor_id: str) -> dict[str, Any] | None:
        return self.docs.get(corridor_id)


class FakeRates:
    def __init__(self) -> None:
        self.history: dict[str, Any] = {"SGD_PHP": HISTORY}

    def get_history(self, pair_id: str) -> dict[str, Any] | None:
        return self.history.get(pair_id)

    def get_rate(self, pair_id: str) -> dict[str, Any] | None:
        return None


@pytest.fixture
def corridors() -> FakeCorridors:
    return FakeCorridors()


@pytest.fixture
def rates() -> FakeRates:
    return FakeRates()


@pytest.fixture
def app(corridors: FakeCorridors, rates: FakeRates) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_corridor_repository] = lambda: corridors
    app.dependency_overrides[get_rate_repository] = lambda: rates
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_returns_best_vs_worst_savings_over_the_history(api: TestClient) -> None:
    response = api.get(URL, params={"corridor_id": "SG-PH", "amount": 500, "months": 3})

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["best_firm"], body["worst_firm"]) == ("Cheap", "Pricey")
    assert body["months_requested"] == 3
    assert body["months_used"] == 3
    assert [m["month"] for m in body["months"]] == MONTH_LABELS
    assert body["total_savings"] == 6150.0


def test_months_defaults_to_twelve(api: TestClient) -> None:
    response = api.get(URL, params={"corridor_id": "SG-PH", "amount": 500})

    assert response.status_code == 200, response.text
    assert response.json()["months_requested"] == 12


@pytest.mark.parametrize("months", [0, 13])
def test_months_out_of_1_to_12_is_a_422(api: TestClient, months: int) -> None:
    response = api.get(URL, params={"corridor_id": "SG-PH", "amount": 500, "months": months})

    assert response.status_code == 422


def test_unknown_corridor_is_a_404(api: TestClient) -> None:
    response = api.get(URL, params={"corridor_id": "SG-IN", "amount": 500})

    assert response.status_code == 404


def test_amount_out_of_range_is_a_422(api: TestClient) -> None:
    response = api.get(URL, params={"corridor_id": "SG-PH", "amount": 1})

    assert response.status_code == 422


def test_no_rate_history_is_a_404(api: TestClient, rates: FakeRates) -> None:
    rates.history.clear()

    response = api.get(URL, params={"corridor_id": "SG-PH", "amount": 500, "months": 3})

    assert response.status_code == 404


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        response = client.get(URL, params={"corridor_id": "SG-PH", "amount": 500})
        assert response.status_code == 401


def test_endpoint_is_documented_in_openapi(api: TestClient) -> None:
    operation = api.get("/openapi.json").json()["paths"][URL]["get"]

    assert {"401", "404", "422", "429"} <= set(operation["responses"])
