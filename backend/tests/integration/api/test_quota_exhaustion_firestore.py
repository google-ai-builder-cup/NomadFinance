"""NF-HR-010 through the real wiring: `get_gemini_client()`, the Firestore counts and two instances.

The Gemini SDK is replaced; everything else is the production path: the client is built from the
`GEMINI_RPD_*` settings as the deploy script sets them, every request is counted in
`gemini_usage/{day}` on the Firestore emulator, and a second client (a second Cloud Run instance)
reads the first one's counts.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from google import genai
from google.cloud.firestore import Client

from app.config import get_settings
from app.integrations.gemini import (
    GeminiBudget,
    GeminiBudgetExhaustedError,
    GeminiClient,
    GeminiRateLimitError,
    ModelTier,
    get_gemini_client,
)
from app.integrations.gemini.budget import budget_day
from app.repositories.gemini_usage_repo import GeminiUsageRepository, get_gemini_usage_repository
from tests.unit.integrations.gemini_fakes import FakeModels, text_response

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        "FIRESTORE_EMULATOR_HOST" not in os.environ,
        reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
    ),
]


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The settings of a deploy whose quota-limits.json had a reasoning limit of 8."""
    monkeypatch.setenv("GEMINI_RPD_REASONING", "8")
    caches = (get_settings, get_gemini_client, get_gemini_usage_repository)
    for cache in caches:
        cache.cache_clear()  # type: ignore[attr-defined]
    yield
    monkeypatch.undo()
    for cache in caches:
        cache.cache_clear()  # type: ignore[attr-defined]


def _with_sdk(client: GeminiClient, outcomes: list[Any]) -> FakeModels:
    fake = FakeModels(outcomes)
    client._sdk = cast(genai.Client, SimpleNamespace(aio=SimpleNamespace(models=fake)))
    return fake


async def ask(client: GeminiClient, operation: str) -> str:
    reply = await client.chat(operation=operation, tier=ModelTier.REASONING, message="hi")
    return reply.text


def _today_document(db: Client) -> dict[str, Any]:
    day = budget_day(datetime.now(UTC))
    return db.collection("gemini_usage").document(day).get().to_dict() or {}


async def test_the_client_built_for_production_counts_every_request_in_firestore(
    configured: None, clean_firestore: Client
) -> None:
    client = get_gemini_client()
    fake = _with_sdk(client, [text_response("ok")] * 3)

    await ask(client, "scam.explain")
    await ask(client, "scam.explain")
    await ask(client, "coach.plan")

    assert len(fake.calls) == 3
    document = _today_document(clean_firestore)
    assert document["calls"] == {"scam": {"reasoning": 2}, "coach": {"reasoning": 1}}


async def test_a_second_instance_sees_the_first_ones_requests(
    configured: None, clean_firestore: Client
) -> None:
    settings = get_settings()
    first = GeminiClient(
        settings, budget=GeminiBudget(GeminiUsageRepository(clean_firestore), settings.gemini_rpd)
    )
    _with_sdk(first, [text_response("ok")] * 2)
    await ask(first, "scam.explain")
    await ask(first, "scam.explain")  # scam's share of 8: 2

    second = GeminiClient(
        settings, budget=GeminiBudget(GeminiUsageRepository(clean_firestore), settings.gemini_rpd)
    )
    fake = _with_sdk(second, [text_response("ok")])

    with pytest.raises(GeminiBudgetExhaustedError) as refused:
        await ask(second, "scam.explain")
    assert refused.value.source == "budget"
    assert fake.calls == []  # the second instance never sent it
    assert await ask(second, "coach.plan") == "ok"  # coach's share (1) is separate


async def test_a_per_day_429_closes_the_model_for_every_instance(
    configured: None, clean_firestore: Client
) -> None:
    from tests.unit.integrations.budget_fakes import DAILY_429

    settings = get_settings()
    first = GeminiClient(
        settings, budget=GeminiBudget(GeminiUsageRepository(clean_firestore), settings.gemini_rpd)
    )
    fake = _with_sdk(first, [DAILY_429])
    with pytest.raises(GeminiRateLimitError) as google:
        await ask(first, "coach.plan")
    assert google.value.daily is True and not isinstance(google.value, GeminiBudgetExhaustedError)
    assert len(fake.calls) == 1  # not retried
    assert _today_document(clean_firestore)["exhausted"].keys() == {"reasoning"}

    second = GeminiClient(
        settings, budget=GeminiBudget(GeminiUsageRepository(clean_firestore), settings.gemini_rpd)
    )
    other = _with_sdk(second, [text_response("ok")])
    with pytest.raises(GeminiBudgetExhaustedError) as refused:
        await ask(second, "scam.explain")

    assert refused.value.source == "google" and other.calls == []
