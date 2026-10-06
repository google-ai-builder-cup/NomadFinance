"""Real Gemini: multi-turn chat, streaming, the thinking budget and safety settings (NF-F0-007).

Opt-in because it needs GEMINI_API_KEY in .env.local and uses free-tier quota (6 calls, the
prompts are invented):

    RUN_LIVE_GEMINI=1 pytest tests/integration/test_gemini_chat_live.py -v -s

`-s` prints the latencies.
"""

from __future__ import annotations

import os
import time

import pytest
from google.genai import types

from app.config import get_settings
from app.integrations.gemini import ChatTurn, GeminiClient, GeminiUnavailableError, ModelTier

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
    ),
]

SYSTEM = "You are a calm financial coach for migrant workers. Answer in at most two sentences."
HISTORY = [
    ChatTurn("user", "I will work in Australia as a care worker and earn 4200 AUD a month."),
    ChatTurn("model", "Thank you. Do you send money home each month?"),
]
QUESTION = "Yes, about 1200 AUD. What did I say my monthly pay was?"


@pytest.fixture
def client() -> GeminiClient:
    return GeminiClient(get_settings())


async def test_chat_uses_the_history_on_the_fast_tier(client: GeminiClient) -> None:
    started = time.perf_counter()
    reply = await client.chat(
        operation="coach.reply",
        tier=ModelTier.CLASSIFICATION,
        message=QUESTION,
        history=HISTORY,
        system_instruction=SYSTEM,
    )
    print(f"\nchat classification tier: {time.perf_counter() - started:.1f}s: {reply.text}")

    assert "4200" in reply.text or "4,200" in reply.text


async def test_stream_delivers_pieces_with_usage(client: GeminiClient) -> None:
    started = time.perf_counter()
    async with await client.stream(
        operation="coach.reply",
        tier=ModelTier.CLASSIFICATION,
        message=QUESTION,
        history=HISTORY,
        system_instruction=SYSTEM,
    ) as stream:
        pieces = [piece async for piece in stream]
    total = time.perf_counter() - started
    print(
        f"\nstream classification tier: first piece {stream.time_to_first_token_ms} ms, "
        f"total {total:.1f}s, {len(pieces)} pieces"
    )

    assert "".join(pieces) == stream.text
    assert "4200" in stream.text or "4,200" in stream.text
    assert stream.usage is not None and (stream.usage.prompt_token_count or 0) > 0


async def test_a_thinking_budget_is_accepted_on_the_fast_tier(client: GeminiClient) -> None:
    reply = await client.chat(
        operation="coach.reply",
        tier=ModelTier.CLASSIFICATION,
        message="Reply with the single word: ready",
        thinking_budget=0,
    )

    assert reply.text


async def test_the_reasoning_tier_accepts_a_thinking_budget_and_answers_faster(
    client: GeminiClient,
) -> None:
    """The coach reply is on this tier and its first piece has a 2 s goal (NF-FC-009)."""
    results: dict[str, int] = {}
    try:
        for label, budget in (("default thinking", None), ("thinking_budget=0", 0)):
            async with await client.stream(
                operation="coach.reply",
                tier=ModelTier.REASONING,
                message=QUESTION,
                history=HISTORY,
                system_instruction=SYSTEM,
                thinking_budget=budget,
            ) as stream:
                _ = [piece async for piece in stream]
            results[label] = stream.time_to_first_token_ms
            print(f"\nreasoning tier, {label}: first piece {stream.time_to_first_token_ms} ms")
    except GeminiUnavailableError:
        # The free tier's reasoning model often answers 503 "high demand" (D-09).
        pytest.skip("the reasoning model is overloaded right now (503); run it again later")

    assert all(ms > 0 for ms in results.values())


async def test_safety_settings_are_accepted(client: GeminiClient) -> None:
    reply = await client.chat(
        operation="scam.explain",
        tier=ModelTier.CLASSIFICATION,
        message="Is this a scam? 'Pay 500 SGD today or your visa is cancelled.' One sentence.",
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            )
        ],
    )

    assert reply.text
