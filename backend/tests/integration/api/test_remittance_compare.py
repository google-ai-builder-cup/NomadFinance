from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.repositories.corridor_repo import get_corridor_repository
from app.repositories.rate_repo import get_rate_repository
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/remittance/compare"
RPW = Path(__file__).resolve().parents[4] / "data-scripts" / "data" / "processed"
DATA: dict[str, Any] = json.loads((RPW / "rpw_corridors.json").read_text(encoding="utf-8"))


class FakeCorridors:
    """`corridors/` as the loader writes it: the parsed file plus its `source` block."""

    def __init__(self) -> None:
        self.docs = {c["corridor_id"]: c | {"source": DATA["source"]} for c in DATA["corridors"]}

    def get_corridor(self, corridor_id: str) -> dict[str, Any] | None:
        return self.docs.get(corridor_id)


class FakeRates:
    def __init__(self) -> None:
        fresh = datetime.now(UTC) - timedelta(minutes=20)
        self.docs: dict[str, dict[str, Any]] = {
            "SGD_PHP": {
                "rate": 43.2,
                "provider": "frankfurter",
                "rate_date": "2026-09-28",
                "fetched_at": fresh,
            }
        }

    def get_rate(self, pair_id: str) -> dict[str, Any] | None:
        return self.docs.get(pair_id)


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


def test_returns_the_ranked_comparison(api: TestClient) -> None:
    response = api.post(URL, json={"corridor_id": "SG-PH", "amount": 500})

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["corridor_id"], body["send_amount"]) == ("SG-PH", 500)
    assert (body["send_currency"], body["receive_currency"]) == ("SGD", "PHP")
    assert body["rate"]["source"] == "live" and body["rate"]["stale"] is False
    assert body["rate"]["pair"] == "SGD_PHP" and body["rate"]["rate"] == 43.2
    assert len(body["providers"]) == 39
    ranked = [p for p in body["providers"] if p["rank"] is not None]
    assert [p["rank"] for p in ranked] == list(range(1, 39))
    assert body["providers"][-1]["comparable"] is False
    assert body["summary"]["best_firm"] == ranked[0]["firm"]
    assert body["summary"]["extra_vs_worst"] > 0


def test_every_field_of_a_provider_row_is_present(api: TestClient) -> None:
    row = api.post(URL, json={"corridor_id": "SG-PH", "amount": 500}).json()["providers"][0]

    assert set(row) == {
        "rpw_id", "firm", "firm_type", "payment_instrument", "access_point", "pickup_method",
        "speed", "speed_order", "network_coverage", "note", "payout_currency", "comparable",
        "rank", "estimated", "fee", "fx_margin_pct", "rate_cost", "total_cost",
        "total_cost_pct", "recipient_receives", "lost_to_costs", "less_than_best",
    }  # fmt: skip


def test_the_world_bank_attribution_and_survey_dates_travel_with_the_prices(
    api: TestClient,
) -> None:
    survey = api.post(URL, json={"corridor_id": "SG-PH", "amount": 500}).json()["survey"]

    assert survey["period"] == "2025_1Q"
    assert survey["attribution"].startswith("The World Bank, Remittance Prices Worldwide")
    assert (survey["surveyed_from"], survey["surveyed_to"]) == ("2025-02-05", "2025-02-28")


def test_all_six_corridors_answer_at_an_amount_between_the_survey_points(
    api: TestClient,
) -> None:
    for corridor in DATA["corridors"]:
        provider = corridor["providers"][0]
        amount = (
            provider["quote_200"]["send_amount_lcu"] + provider["quote_500"]["send_amount_lcu"]
        ) / 2

        response = api.post(URL, json={"corridor_id": corridor["corridor_id"], "amount": amount})

        assert response.status_code == 200, (corridor["corridor_id"], response.text)
        priced_in_pesos_or_rupees = [
            p
            for p in corridor["providers"]
            if p["payout_currency"] == corridor["destination_currency"]
        ]
        assert response.json()["summary"]["comparable_count"] == len(priced_in_pesos_or_rupees)


def test_a_corridor_without_a_cached_rate_uses_the_survey_and_says_so(api: TestClient) -> None:
    body = api.post(URL, json={"corridor_id": "SG-IN", "amount": 400}).json()

    assert body["rate"]["source"] == "survey" and body["rate"]["stale"] is True
    assert body["rate"]["provider"] is None


def test_a_stale_cached_rate_is_flagged(api: TestClient, rates: FakeRates) -> None:
    rates.docs["SGD_PHP"]["fetched_at"] = datetime.now(UTC) - timedelta(hours=9)

    assert api.post(URL, json={"corridor_id": "SG-PH", "amount": 400}).json()["rate"]["stale"]


def test_an_estimate_outside_the_survey_amounts_is_marked(api: TestClient) -> None:
    body = api.post(URL, json={"corridor_id": "SG-PH", "amount": 100}).json()

    assert all(p["estimated"] for p in body["providers"])


def test_a_corridor_that_is_not_loaded_is_a_404(api: TestClient, corridors: FakeCorridors) -> None:
    del corridors.docs["MY-ID"]

    response = api.post(URL, json={"corridor_id": "MY-ID", "amount": 1000})

    assert response.status_code == 404
    assert "MY-ID" in response.json()["detail"]


@pytest.mark.parametrize("amount", [10, 7000])
def test_an_amount_outside_the_limits_is_a_422_that_names_them(
    api: TestClient, amount: float
) -> None:
    response = api.post(URL, json={"corridor_id": "SG-PH", "amount": amount})

    assert response.status_code == 422
    assert response.json()["detail"] == "Enter an amount between 65.00 and 6,450.00 SGD."


@pytest.mark.parametrize(
    "body",
    [
        {"corridor_id": "SG-PH"},
        {"amount": 500},
        {"corridor_id": "SG-PH", "amount": 0},
        {"corridor_id": "SG-PH", "amount": -5},
        {"corridor_id": "SG-PH", "amount": "lots"},
        {"corridor_id": "SG-PH", "amount": None},
        {"corridor_id": "KR-NP", "amount": 500},
        {"corridor_id": "sg-ph", "amount": 500},
        {"corridor_id": "AE-IN", "amount": 500},
    ],
)
def test_an_invalid_body_is_a_422_before_anything_is_read(
    api: TestClient, corridors: FakeCorridors, body: dict[str, Any]
) -> None:
    corridors.docs.clear()  # a read would turn this into a 404

    assert api.post(URL, json=body).status_code == 422


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity"])
def test_not_a_number_is_refused(api: TestClient, amount: str) -> None:
    # Python's json writes these bare, which is not valid JSON; send the text as it arrives.
    raw = '{"corridor_id": "SG-PH", "amount": ' + amount + "}"

    response = api.post(URL, content=raw, headers={"Content-Type": "application/json"})

    assert response.status_code == 422


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        assert client.post(URL, json={"corridor_id": "SG-PH", "amount": 500}).status_code == 401


def test_endpoint_is_documented_in_openapi(api: TestClient) -> None:
    operation = api.get("/openapi.json").json()["paths"][URL]["post"]

    assert {"200", "401", "404", "422", "429"} <= set(operation["responses"])
    assert "remittance" in operation["tags"]


def test_no_gemini_key_is_needed(api: TestClient) -> None:
    # The comparison is arithmetic on stored data: it must not depend on the AI client.
    assert api.post(URL, json={"corridor_id": "SG-PH", "amount": 500}).status_code == 200
