"""The client with a spent quota (NF-HR-010): no retry of a daily 429, no request once refused, and
no false request count for a refusal."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, cast

import pytest
from google import genai

from app.config import get_settings
from app.integrations.gemini import (
    GeminiBudget,
    GeminiBudgetExhaustedError,
    GeminiClient,
    GeminiRateLimitError,
    ModelTier,
)
from app.integrations.gemini.embeddings import EMBEDDING_DIMENSION
from tests.unit.integrations.budget_fakes import DAILY_429, PER_MINUTE_429, make_budget
from tests.unit.integrations.gemini_fakes import FakeModels, text_response, unavailable

pytestmark = pytest.mark.anyio


# --- the client --------------------------------------------------------------------------------


def client_with(
    budget: GeminiBudget, outcomes: list[Any], **overrides: Any
) -> tuple[GeminiClient, FakeModels]:
    fake = FakeModels(outcomes)
    sdk = cast(genai.Client, SimpleNamespace(aio=SimpleNamespace(models=fake)))
    settings = get_settings().model_copy(update=overrides)
    return GeminiClient(settings, sdk_client=sdk, max_backoff_seconds=0, budget=budget), fake


async def ask(client: GeminiClient, operation: str = "scam.explain") -> str:
    reply = await client.chat(operation=operation, tier=ModelTier.REASONING, message="hi")
    return reply.text


async def test_a_daily_429_is_not_retried_and_closes_the_model_for_the_next_call() -> None:
    budget, _, _ = make_budget({})
    client, fake = client_with(budget, [DAILY_429])

    with pytest.raises(GeminiRateLimitError) as first:
        await ask(client)
    with pytest.raises(GeminiBudgetExhaustedError) as second:
        await ask(client, "coach.plan")

    assert first.value.daily is True
    assert second.value.source == "google"
    assert len(fake.calls) == 1  # one request to Google, in total


async def test_a_per_minute_429_is_still_retried() -> None:
    budget, _, _ = make_budget({})
    client, fake = client_with(budget, [PER_MINUTE_429, text_response("ok")])

    assert await ask(client) == "ok"
    assert len(fake.calls) == 2


async def test_a_refused_call_makes_no_request_and_leaves_no_request_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    budget, _, _ = make_budget({"reasoning": 1})
    client, fake = client_with(budget, [text_response("ok")])
    await ask(client)  # scam's one request

    with caplog.at_level(logging.INFO), pytest.raises(GeminiBudgetExhaustedError):
        await ask(client)

    assert len(fake.calls) == 1
    # The three lines that count requests against the quota (NF-F0-016) must not include it.
    request_lines = [
        r for r in caplog.records if r.getMessage().startswith(("gemini_call", "gemini_retry"))
    ]
    assert len(request_lines) == 1


async def test_every_retry_counts_against_the_budget() -> None:
    budget, store, _ = make_budget({"reasoning": 20})  # scam 5
    client, fake = client_with(budget, [unavailable(), unavailable(), text_response("ok")])

    assert await ask(client) == "ok"

    assert len(fake.calls) == 3
    assert store.days["2026-11-12"].calls == {("scam", "reasoning"): 3}


async def test_a_retry_stops_when_the_budget_runs_out_between_attempts() -> None:
    budget, _, _ = make_budget({"reasoning": 8})  # scam 2
    client, fake = client_with(budget, [unavailable(), unavailable(), text_response("ok")])

    with pytest.raises(GeminiBudgetExhaustedError):
        await ask(client)

    assert len(fake.calls) == 2


async def test_a_stream_is_refused_before_a_request_and_a_daily_429_is_not_retried() -> None:
    budget, _, _ = make_budget({})
    client, fake = client_with(budget, [DAILY_429])

    with pytest.raises(GeminiRateLimitError):
        await client.stream(operation="coach.reply", tier=ModelTier.CLASSIFICATION, message="hi")
    with pytest.raises(GeminiBudgetExhaustedError):
        await client.stream(operation="coach.reply", tier=ModelTier.CLASSIFICATION, message="hi")

    assert len(fake.calls) == 1


async def test_a_stream_counts_against_its_features_share() -> None:
    budget, _, _ = make_budget({"classification": 8})  # coach 4
    client, fake = client_with(budget, [DAILY_429])
    budget_for_coach = budget.limit_for("coach", "classification")

    assert budget_for_coach == 4
    for _ in range(4):
        await budget.admit("coach", "classification")
    with pytest.raises(GeminiBudgetExhaustedError):
        await client.stream(operation="coach.reply", tier=ModelTier.CLASSIFICATION, message="hi")
    assert fake.calls == []


class EmbedModels:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def embed_content(self, **_: Any) -> Any:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def embed_client_with(
    budget: GeminiBudget, outcomes: list[Any]
) -> tuple[GeminiClient, EmbedModels]:
    models = EmbedModels(outcomes)
    sdk = cast(genai.Client, SimpleNamespace(aio=SimpleNamespace(models=models)))
    return GeminiClient(get_settings(), sdk, max_backoff_seconds=0, budget=budget), models


async def test_an_embedding_daily_429_is_flagged_daily_and_not_retried() -> None:
    budget, _, _ = make_budget({})
    client, models = embed_client_with(budget, [DAILY_429])

    with pytest.raises(GeminiRateLimitError) as raised:
        await client.embed_text("x", operation="scam.embed")
    with pytest.raises(GeminiBudgetExhaustedError):
        await client.embed_text("x", operation="scam.embed")

    assert raised.value.daily is True
    assert models.calls == 1


async def test_embeddings_have_their_own_tier_and_budget() -> None:
    budget, store, _ = make_budget({"embedding": 2})  # scam 0.8 -> 1
    vector = SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0] * EMBEDDING_DIMENSION)])
    client, models = embed_client_with(budget, [vector])

    await client.embed_text("x", operation="scam.embed")
    with pytest.raises(GeminiBudgetExhaustedError):
        await client.embed_text("x", operation="scam.embed")

    assert models.calls == 1
    assert store.days["2026-11-12"].calls == {("scam", "embedding"): 1}
