"""The shared `FakeGemini` (NF-F0-014) and how a test of a service or an endpoint uses it."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.gemini import GeminiRateLimitError, ModelTier
from app.main import create_app
from app.schemas.contract import DetectedContract
from app.schemas.user import AuthenticatedUser
from app.services.contract.detector import detect_contract
from tests.fixtures.fake_gemini import FakeGemini, NoRecordingError, as_client, override_gemini

pytestmark = pytest.mark.anyio


async def test_a_service_gets_the_recorded_structured_answer(recorded_gemini: FakeGemini) -> None:
    # The real detector, its real prompt, and a recorded answer in place of Gemini.
    detected = await detect_contract("1. Salary: SGD 650 a month", as_client(recorded_gemini))

    assert detected.host_country == "SG"
    assert detected.salary_amount == 650.0
    assert recorded_gemini.calls[0]["operation"] == "contract.detect"
    assert recorded_gemini.calls[0]["tier"] == ModelTier.EXTRACTION


def test_an_endpoint_uses_the_fake_through_the_dependency(recorded_gemini: FakeGemini) -> None:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    override_gemini(app, recorded_gemini)

    with TestClient(app) as client:
        response = client.post("/api/v1/contracts/detect", json={"text": "Salary: SGD 650"})

    assert response.status_code == 200
    assert response.json()["host_country"] == "SG"


async def test_chat_returns_the_recorded_text(recorded_gemini: FakeGemini) -> None:
    reply = await recorded_gemini.chat(
        operation="coach.reply", tier=ModelTier.REASONING, message="Hello"
    )

    assert reply.text.startswith("Thanks.")
    assert reply.dropped_turns == []


async def test_a_stream_joins_back_to_the_whole_text(recorded_gemini: FakeGemini) -> None:
    whole = (
        await recorded_gemini.chat(operation="coach.reply", tier=ModelTier.REASONING, message="x")
    ).text

    async with await recorded_gemini.stream(
        operation="coach.reply", tier=ModelTier.REASONING, message="x"
    ) as stream:
        pieces = [piece async for piece in stream]

    assert len(pieces) > 1
    assert "".join(pieces) == whole == stream.text


async def test_a_recording_can_give_its_own_pieces() -> None:
    fake = FakeGemini({"coach.reply": {"kind": "text", "pieces": ["Hel", "lo"]}})

    stream = await fake.stream(operation="coach.reply", tier=ModelTier.REASONING, message="x")

    assert [piece async for piece in stream] == ["Hel", "lo"]


async def test_a_closed_stream_stops_early() -> None:
    fake = FakeGemini({"coach.reply": {"kind": "text", "text": "one two three"}})
    stream = await fake.stream(operation="coach.reply", tier=ModelTier.REASONING, message="x")

    assert await anext(stream) == "one "
    await stream.aclose()

    assert [piece async for piece in stream] == []


async def test_a_recorded_error_is_raised() -> None:
    fake = FakeGemini({"scam.classify": {"kind": "structured", "error": "GeminiRateLimitError"}})

    with pytest.raises(GeminiRateLimitError):
        await fake.generate_structured(
            operation="scam.classify",
            tier=ModelTier.CLASSIFICATION,
            response_model=DetectedContract,
        )


async def test_a_list_of_responses_is_replayed_in_order_then_the_last_repeats() -> None:
    fake = FakeGemini(
        {
            "coach.reply": {
                "responses": [
                    {"kind": "text", "text": "first"},
                    {"kind": "text", "text": "second"},
                ]
            }
        }
    )

    async def ask() -> str:
        return (
            await fake.chat(operation="coach.reply", tier=ModelTier.REASONING, message="x")
        ).text

    assert [await ask(), await ask(), await ask()] == ["first", "second", "second"]


async def test_a_call_with_no_recording_fails_loudly_and_says_what_to_add() -> None:
    fake = FakeGemini()

    with pytest.raises(NoRecordingError, match=r"no recording for operation 'nobody\.home'"):
        await fake.chat(operation="nobody.home", tier=ModelTier.REASONING, message="x")


async def test_a_recording_of_the_wrong_kind_is_refused() -> None:
    fake = FakeGemini({"coach.reply": {"kind": "text", "text": "hi"}})

    with pytest.raises(NoRecordingError, match="not a 'structured' answer"):
        await fake.generate_structured(
            operation="coach.reply", tier=ModelTier.REASONING, response_model=DetectedContract
        )


async def test_a_recording_that_no_longer_fits_the_model_fails_the_test() -> None:
    fake = FakeGemini({"contract.detect": {"kind": "structured", "response": {"language": "xx"}}})

    with pytest.raises(ValueError):
        await fake.generate_structured(
            operation="contract.detect",
            tier=ModelTier.EXTRACTION,
            response_model=DetectedContract,
        )


async def test_every_call_is_kept_for_the_test_to_inspect(recorded_gemini: FakeGemini) -> None:
    await recorded_gemini.chat(
        operation="coach.reply", tier=ModelTier.REASONING, message="hello", temperature=0.2
    )

    call: dict[str, Any] = recorded_gemini.calls[0]
    assert (call["call"], call["message"], call["temperature"]) == ("chat", "hello", 0.2)
