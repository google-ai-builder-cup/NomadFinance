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

INCOME_URL = "/api/v1/fib/income"
BILL_URL = "/api/v1/fib/bill"
SAVINGS_URL = "/api/v1/fib/savings"


class FakeFib:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self._next_id = 0

    def new_id(self, uid: str, kind: EntryKind) -> str:
        self._next_id += 1
        return f"e_{self._next_id}"

    def save_entry(self, uid: str, kind: EntryKind, entry_id: str, data: dict[str, Any]) -> None:
        self.docs[f"{uid}/{kind}/{entry_id}"] = data


@pytest.fixture
def fib() -> FakeFib:
    return FakeFib()


@pytest.fixture
def app(fib: FakeFib) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_fib_repository] = lambda: fib
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_income_is_logged(api: TestClient, fib: FakeFib) -> None:
    response = api.post(INCOME_URL, json={"amount": 650, "currency": "SGD", "category": "salary"})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["category"] == "salary"
    assert body["category_source"] == "user"
    assert body["verified"] is False
    assert "test-user/income/e_1" in fib.docs


def test_income_without_a_category_is_rejected(api: TestClient) -> None:
    response = api.post(INCOME_URL, json={"amount": 650, "currency": "SGD"})

    assert response.status_code == 422


def test_bill_is_logged(api: TestClient, fib: FakeFib) -> None:
    response = api.post(
        BILL_URL,
        json={"amount": 38.5, "currency": "SGD", "paid": True, "vendor": "Example Telecom"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["vendor"] == "Example Telecom"
    assert body["paid"] is True
    assert body["category"] is None
    assert "test-user/bills/e_1" in fib.docs


def test_bill_without_paid_is_rejected(api: TestClient) -> None:
    response = api.post(BILL_URL, json={"amount": 38.5, "currency": "SGD"})

    assert response.status_code == 422


def test_savings_is_logged(api: TestClient, fib: FakeFib) -> None:
    response = api.post(
        SAVINGS_URL, json={"amount": 120, "currency": "SGD", "direction": "deposit"}
    )

    assert response.status_code == 201, response.text
    assert response.json()["direction"] == "deposit"
    assert "test-user/savings/e_1" in fib.docs


def test_negative_savings_amount_is_rejected(api: TestClient) -> None:
    response = api.post(
        SAVINGS_URL, json={"amount": -10, "currency": "SGD", "direction": "withdrawal"}
    )

    assert response.status_code == 422


def test_an_invalid_currency_code_is_rejected(api: TestClient) -> None:
    response = api.post(SAVINGS_URL, json={"amount": 10, "currency": "sgd", "direction": "deposit"})

    assert response.status_code == 422


@pytest.mark.parametrize("url", [INCOME_URL, BILL_URL, SAVINGS_URL])
def test_missing_token_is_rejected(app: FastAPI, url: str) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        assert client.post(url, json={}).status_code == 401


def test_endpoints_are_documented_in_openapi(api: TestClient) -> None:
    paths = api.get("/openapi.json").json()["paths"]

    assert "post" in paths["/api/v1/fib/income"]
    assert "post" in paths["/api/v1/fib/bill"]
    assert "post" in paths["/api/v1/fib/savings"]


# --- NF-HR-004: no entry is beyond the limit ------------------------------------------------


@pytest.mark.parametrize(
    ("url", "body"),
    [
        (INCOME_URL, {"amount": 1_000_001, "currency": "SGD", "category": "salary"}),
        (BILL_URL, {"amount": 1e15, "currency": "AUD", "paid": True}),
        (SAVINGS_URL, {"amount": 100_000_001, "currency": "JPY", "direction": "deposit"}),
    ],
)
def test_an_amount_beyond_the_limit_is_refused_and_nothing_is_stored(
    api: TestClient, fib: FakeFib, url: str, body: dict[str, Any]
) -> None:
    response = api.post(url, json=body)

    assert response.status_code == 422
    assert fib.docs == {}


def test_the_largest_amounts_are_still_accepted(api: TestClient) -> None:
    sgd = {"amount": 1_000_000, "currency": "SGD", "category": "salary"}
    yen = {"amount": 100_000_000, "currency": "JPY", "category": "salary"}

    assert api.post(INCOME_URL, json=sgd).status_code == 201
    assert api.post(INCOME_URL, json=yen).status_code == 201
