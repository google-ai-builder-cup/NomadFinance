from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from app.config import get_settings
from app.integrations.gemini import (
    GeminiClient,
    GeminiRateLimitError,
    GeminiRequestError,
    GeminiResponseError,
    GeminiTimeoutError,
    GeminiUnavailableError,
    ModelTier,
)

pytestmark = pytest.mark.anyio


class Clause(BaseModel):
    title: str
    risky: bool


class FakeModels:
    """Stands in for `genai.Client().aio.models`; plays back one outcome per call."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> types.GenerateContentResponse:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome == "hang":
            await asyncio.sleep(5)
        return cast(types.GenerateContentResponse, outcome)


def make_client(outcomes: list[Any], **settings_overrides: Any) -> tuple[GeminiClient, FakeModels]:
    fake = FakeModels(outcomes)
    sdk = cast(genai.Client, SimpleNamespace(aio=SimpleNamespace(models=fake)))
    settings = get_settings().model_copy(update=settings_overrides)
    return GeminiClient(settings, sdk_client=sdk, max_backoff_seconds=0), fake


def json_response(text: str) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=text)]),
                finish_reason=types.FinishReason.STOP,
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=12, candidates_token_count=7, total_token_count=19
        ),
    )


def api_error(cls: type[genai_errors.APIError], code: int, status: str) -> genai_errors.APIError:
    return cls(code, {"error": {"code": code, "message": "fake failure", "status": status}})


OK = json_response('{"title": "Overtime", "risky": true}')


async def generate(client: GeminiClient) -> Clause:
    return await client.generate_structured(
        operation="test.clause",
        tier=ModelTier.REASONING,
        contents="Analyse this clause",
        response_model=Clause,
    )


async def test_returns_validated_model_and_sends_schema() -> None:
    client, fake = make_client([OK])

    result = await generate(client)

    assert result == Clause(title="Overtime", risky=True)
    call = fake.calls[0]
    assert call["model"] == get_settings().gemini_model_reasoning
    assert call["config"].response_schema is Clause
    assert call["config"].response_mime_type == "application/json"


async def test_uses_sdk_parsed_object_when_present() -> None:
    response = json_response("ignored")
    response.parsed = Clause(title="Deductions", risky=False)
    client, _ = make_client([response])

    assert await generate(client) == Clause(title="Deductions", risky=False)


@pytest.mark.parametrize(
    ("tier", "setting"),
    [
        (ModelTier.REASONING, "gemini_model_reasoning"),
        (ModelTier.EXTRACTION, "gemini_model_extraction"),
        (ModelTier.CLASSIFICATION, "gemini_model_classification"),
    ],
)
async def test_routes_each_tier_to_its_configured_model(tier: ModelTier, setting: str) -> None:
    client, fake = make_client([OK], **{setting: "custom-model"})

    await client.generate_structured(
        operation="test.route", tier=tier, contents="x", response_model=Clause
    )

    assert fake.calls[0]["model"] == "custom-model"


@pytest.mark.parametrize(
    "transient",
    [
        api_error(genai_errors.ServerError, 503, "UNAVAILABLE"),
        api_error(genai_errors.ClientError, 429, "RESOURCE_EXHAUSTED"),
        httpx.ConnectError("connection reset"),
    ],
)
async def test_retries_transient_failures_then_succeeds(transient: Exception) -> None:
    client, fake = make_client([transient, OK])

    assert await generate(client) == Clause(title="Overtime", risky=True)
    assert len(fake.calls) == 2


async def test_does_not_retry_rejected_request() -> None:
    client, fake = make_client([api_error(genai_errors.ClientError, 400, "INVALID_ARGUMENT"), OK])

    with pytest.raises(GeminiRequestError, match="400 INVALID_ARGUMENT"):
        await generate(client)
    assert len(fake.calls) == 1


async def test_rate_limit_raised_after_all_attempts() -> None:
    errors = [api_error(genai_errors.ClientError, 429, "RESOURCE_EXHAUSTED") for _ in range(3)]
    client, fake = make_client(errors, gemini_max_attempts=3)

    with pytest.raises(GeminiRateLimitError):
        await generate(client)
    assert len(fake.calls) == 3


async def test_server_error_raised_after_all_attempts() -> None:
    errors = [api_error(genai_errors.ServerError, 500, "INTERNAL") for _ in range(2)]
    client, _ = make_client(errors, gemini_max_attempts=2)

    with pytest.raises(GeminiUnavailableError):
        await generate(client)


async def test_times_out_each_attempt_then_gives_up() -> None:
    client, fake = make_client(["hang", "hang"], gemini_timeout_seconds=0.01, gemini_max_attempts=2)

    with pytest.raises(GeminiTimeoutError, match="did not respond"):
        await generate(client)
    assert len(fake.calls) == 2


async def test_per_call_timeout_overrides_the_default() -> None:
    # Default 30 s would wait out the 5 s hang; the call's own 0.01 s must win.
    client, _ = make_client(["hang"], gemini_max_attempts=1)

    with pytest.raises(GeminiTimeoutError, match="within 0.01s"):
        await client.generate_structured(
            operation="test.clause",
            tier=ModelTier.REASONING,
            contents="Analyse this clause",
            response_model=Clause,
            timeout_seconds=0.01,
        )


async def test_schema_mismatch_raises_response_error_without_retry() -> None:
    client, fake = make_client([json_response('{"title": "Overtime"}'), OK])

    with pytest.raises(GeminiResponseError, match="did not match Clause"):
        await generate(client)
    assert len(fake.calls) == 1


async def test_blocked_prompt_raises_response_error() -> None:
    blocked = types.GenerateContentResponse(
        prompt_feedback=types.GenerateContentResponsePromptFeedback(
            block_reason=types.BlockedReason.SAFETY
        )
    )
    client, _ = make_client([blocked])

    with pytest.raises(GeminiResponseError, match="prompt blocked"):
        await generate(client)


async def test_logs_token_usage(caplog: pytest.LogCaptureFixture) -> None:
    client, _ = make_client([api_error(genai_errors.ServerError, 503, "UNAVAILABLE"), OK])

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini.client"):
        await generate(client)

    usage = [r for r in caplog.records if r.getMessage().startswith("gemini_call")]
    assert len(usage) == 1
    fields = usage[0].__dict__["gemini_usage"]
    assert fields["operation"] == "test.clause"
    assert fields["prompt_tokens"] == 12
    assert fields["output_tokens"] == 7
    assert fields["total_tokens"] == 19
    assert fields["attempts"] == 2
    assert any(r.getMessage().startswith("gemini_retry") for r in caplog.records)
