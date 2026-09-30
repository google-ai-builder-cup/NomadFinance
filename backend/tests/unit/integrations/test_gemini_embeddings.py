from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any, cast

import pytest
from google import genai
from google.genai import errors as genai_errors

from app.config import get_settings
from app.integrations.gemini import (
    GeminiClient,
    GeminiRateLimitError,
    GeminiRequestError,
    GeminiResponseError,
    GeminiUnavailableError,
)
from app.integrations.gemini.embeddings import EMBEDDING_DIMENSION

pytestmark = pytest.mark.anyio


class FakeModels:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    async def embed_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _response(values: list[float] | None) -> Any:
    embeddings = [SimpleNamespace(values=values)] if values is not None else []
    return SimpleNamespace(embeddings=embeddings)


def _client(outcomes: list[Any]) -> tuple[GeminiClient, FakeModels]:
    models = FakeModels(outcomes)
    sdk = SimpleNamespace(aio=SimpleNamespace(models=models))
    client = GeminiClient(get_settings(), cast(genai.Client, sdk), max_backoff_seconds=0.0)
    return client, models


def _error(cls: type[genai_errors.APIError], code: int, status: str) -> Exception:
    return cls(code, {"error": {"code": code, "status": status, "message": "x"}})


async def test_returns_a_unit_length_vector_and_asks_for_768_numbers() -> None:
    client, models = _client([_response([3.0] * EMBEDDING_DIMENSION)])

    vector = await client.embed_text("they kept my passport", operation="test.embed")

    assert len(vector) == EMBEDDING_DIMENSION
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0)
    call = models.calls[0]
    assert call["model"] == "gemini-embedding-001"
    assert call["config"].output_dimensionality == EMBEDDING_DIMENSION


async def test_retries_a_transient_error() -> None:
    client, models = _client(
        [_error(genai_errors.ServerError, 503, "UNAVAILABLE"), _response([1.0] * 768)]
    )

    await client.embed_text("x", operation="test.embed")

    assert len(models.calls) == 2


async def test_rate_limit_after_all_attempts() -> None:
    err = _error(genai_errors.ClientError, 429, "RESOURCE_EXHAUSTED")
    client, _ = _client([err, err, err])

    with pytest.raises(GeminiRateLimitError):
        await client.embed_text("x", operation="test.embed")


async def test_rejected_request_is_not_retried() -> None:
    client, models = _client([_error(genai_errors.ClientError, 400, "INVALID_ARGUMENT")])

    with pytest.raises(GeminiRequestError):
        await client.embed_text("x", operation="test.embed")
    assert len(models.calls) == 1


@pytest.mark.parametrize("values", [None, [1.0] * 10, [0.0] * 768])
async def test_unusable_vector_is_a_response_error(values: list[float] | None) -> None:
    client, _ = _client([_response(values)])

    with pytest.raises(GeminiResponseError):
        await client.embed_text("x", operation="test.embed")


async def test_unavailable_after_all_attempts() -> None:
    err = _error(genai_errors.ServerError, 503, "UNAVAILABLE")
    client, _ = _client([err, err, err])

    with pytest.raises(GeminiUnavailableError):
        await client.embed_text("x", operation="test.embed")
