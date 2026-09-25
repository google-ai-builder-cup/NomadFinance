from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.integrations.fx import FxProviderError
from app.integrations.fx.currencyfreaks import CurrencyFreaksProvider
from app.integrations.fx.exchangerate_api import ExchangeRateApiProvider
from app.integrations.fx.frankfurter import FrankfurterProvider
from app.integrations.fx.wise import WiseProvider

pytestmark = pytest.mark.anyio

Handler = Callable[[httpx.Request], httpx.Response]


def client_for(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def json_handler(body: Any, status: int = 200, seen: list[httpx.Request] | None = None) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body)

    return handler


async def test_frankfurter_returns_requested_rates() -> None:
    seen: list[httpx.Request] = []
    body = {"base": "SGD", "date": "2026-09-24", "rates": {"PHP": 49.026, "INR": 74.974}}
    async with client_for(json_handler(body, seen=seen)) as client:
        quote = await FrankfurterProvider(client).fetch("SGD", ["PHP", "INR"])

    assert quote.rates == {"PHP": 49.026, "INR": 74.974}
    assert quote.rate_date == "2026-09-24"
    assert seen[0].url.params["base"] == "SGD"
    assert seen[0].url.params["symbols"] == "PHP,INR"


@pytest.mark.parametrize(
    ("handler", "code"),
    [
        (json_handler({"message": "down"}, status=500), "http_500"),
        (
            json_handler({"base": "SGD", "date": "2026-09-24", "rates": {"PHP": 49.0}}),
            "missing_quote",
        ),
        (
            json_handler({"base": "SGD", "date": "2026-09-24", "rates": {"PHP": -1, "INR": 1}}),
            "invalid_response",
        ),
        (
            json_handler({"base": "SGD", "date": "2026-09-24", "rates": {"PHP": "abc", "INR": 1}}),
            "invalid_response",
        ),
        (json_handler(["not", "an", "object"]), "invalid_response"),
        (lambda request: httpx.Response(200, text="<html>"), "invalid_response"),
    ],
)
async def test_frankfurter_failures_become_short_codes(handler: Handler, code: str) -> None:
    async with client_for(handler) as client:
        with pytest.raises(FxProviderError) as exc_info:
            await FrankfurterProvider(client).fetch("SGD", ["PHP", "INR"])
    assert exc_info.value.code == code


@pytest.mark.parametrize(
    ("error", "code"),
    [(httpx.ReadTimeout("slow"), "timeout"), (httpx.ConnectError("down"), "network")],
)
async def test_transport_errors_become_short_codes(error: Exception, code: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    async with client_for(handler) as client:
        with pytest.raises(FxProviderError) as exc_info:
            await FrankfurterProvider(client).fetch("SGD", ["PHP"])
    assert exc_info.value.code == code


async def test_exchangerate_api_uses_update_time_as_rate_date() -> None:
    body = {
        "result": "success",
        "time_last_update_unix": 1790294551,  # 2026-09-25T00:02:31Z
        "rates": {"PHP": 48.99, "INR": 74.9},
    }
    async with client_for(json_handler(body)) as client:
        quote = await ExchangeRateApiProvider(client).fetch("SGD", ["PHP", "INR"])

    assert quote.rates == {"PHP": 48.99, "INR": 74.9}
    assert quote.rate_date == "2026-09-25"


async def test_exchangerate_api_error_result_is_rejected() -> None:
    body = {"result": "error", "error-type": "unsupported-code"}
    async with client_for(json_handler(body)) as client:
        with pytest.raises(FxProviderError) as exc_info:
            await ExchangeRateApiProvider(client).fetch("XXX", ["PHP"])
    assert exc_info.value.code == "invalid_response"


async def test_currencyfreaks_derives_cross_rates_from_usd() -> None:
    seen: list[httpx.Request] = []
    body = {
        "date": "2026-09-25 08:00:00+00",
        "base": "USD",
        "rates": {"SGD": "1.25", "PHP": "61.25", "INR": "93.75"},
    }
    async with client_for(json_handler(body, seen=seen)) as client:
        provider = CurrencyFreaksProvider(client, SecretStr("cf-key"))
        quote = await provider.fetch("SGD", ["PHP", "INR"])

    assert quote.rates == {"PHP": pytest.approx(49.0), "INR": pytest.approx(75.0)}
    assert quote.rate_date == "2026-09-25"
    assert seen[0].url.params["apikey"] == "cf-key"
    assert seen[0].url.params["symbols"] == "SGD,PHP,INR"


@pytest.mark.parametrize("key", [None, SecretStr("")])
async def test_keyed_providers_without_key_are_not_configured(key: SecretStr | None) -> None:
    async with client_for(json_handler({})) as client:
        assert CurrencyFreaksProvider(client, key).configured is False
        assert WiseProvider(client, key).configured is False
        assert FrankfurterProvider(client).configured is True


@pytest.mark.parametrize(
    "body",
    [
        [{"rate": 49.1, "source": "SGD", "target": "PHP", "time": "2026-09-25T08:00:00+0000"}],
        {"rate": 49.1, "source": "SGD", "target": "PHP", "time": "2026-09-25T08:00:00+0000"},
    ],
)
async def test_wise_accepts_list_and_object_responses(body: Any) -> None:
    seen: list[httpx.Request] = []
    async with client_for(json_handler(body, seen=seen)) as client:
        quote = await WiseProvider(client, SecretStr("wise-token")).fetch("SGD", ["PHP"])

    assert quote.rates == {"PHP": 49.1}
    assert quote.rate_date == "2026-09-25"
    assert seen[0].headers["Authorization"] == "Bearer wise-token"
    assert seen[0].url.params["source"] == "SGD"
    assert seen[0].url.params["target"] == "PHP"


async def test_wise_rejects_a_rate_for_the_wrong_currency() -> None:
    body = [{"rate": 1.0, "source": "SGD", "target": "USD", "time": "2026-09-25T08:00:00+0000"}]
    async with client_for(json_handler(body)) as client:
        with pytest.raises(FxProviderError) as exc_info:
            await WiseProvider(client, SecretStr("t")).fetch("SGD", ["PHP"])
    assert exc_info.value.code == "invalid_response"
