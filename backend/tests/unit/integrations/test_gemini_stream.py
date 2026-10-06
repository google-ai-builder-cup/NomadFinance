from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest
from google.genai import errors as genai_errors

from app.config import get_settings
from app.integrations.gemini import (
    ChatTurn,
    GeminiClient,
    GeminiRequestError,
    GeminiResponseError,
    GeminiStream,
    GeminiTimeoutError,
    GeminiUnavailableError,
    ModelTier,
)
from tests.unit.integrations.gemini_fakes import (
    HANG,
    api_error,
    make_client,
    text_response,
    unavailable,
    usage,
)

pytestmark = pytest.mark.anyio

REPLY = [
    text_response("Start "),
    text_response("with a month "),
    text_response("of rent."),
    text_response("", usage(80, 12, 150)),
]


async def start(client: GeminiClient, **kwargs: Any) -> GeminiStream:
    return await client.stream(
        operation="coach.reply",
        tier=ModelTier.REASONING,
        message="How much should I save?",
        **kwargs,
    )


async def read_all(stream: GeminiStream) -> list[str]:
    return [piece async for piece in stream]


def calls_logged(caplog: pytest.LogCaptureFixture, prefix: str) -> list[dict[str, Any]]:
    return [r.__dict__["gemini_usage"] for r in caplog.records if r.getMessage().startswith(prefix)]


# --- the happy path --------------------------------------------------------------------


async def test_pieces_arrive_in_order_and_add_up_to_the_reply() -> None:
    client, fake = make_client([list(REPLY)])

    stream = await start(client)
    pieces = await read_all(stream)

    assert pieces == ["Start ", "with a month ", "of rent."]
    assert stream.text == "Start with a month of rent."
    assert fake.streams[0].closed


async def test_a_usage_only_last_chunk_is_not_a_piece_but_its_tokens_are_kept() -> None:
    client, _ = make_client([list(REPLY)])

    stream = await start(client)
    await read_all(stream)

    assert stream.usage is not None
    assert (stream.usage.prompt_token_count, stream.usage.candidates_token_count) == (80, 12)


async def test_stream_is_opened_with_history_the_summary_and_the_options() -> None:
    client, fake = make_client([list(REPLY)])
    history = [ChatTurn("user", "u1"), ChatTurn("model", "m1"), ChatTurn("user", "u2")]

    stream = await start(
        client,
        history=history,
        max_history_turns=1,
        system_instruction="rules",
        summary="<summary>s</summary>",
        thinking_budget=0,
    )

    call = fake.calls[0]
    assert call["model"] == get_settings().gemini_model_reasoning
    assert [c.parts[0].text for c in call["contents"]] == ["u2", "How much should I save?"]
    assert call["config"].system_instruction == "rules\n\n<summary>s</summary>"
    assert call["config"].thinking_config.thinking_budget == 0
    assert [t.text for t in stream.dropped_turns] == ["u1", "m1"]
    await stream.aclose()


# --- usage logging ---------------------------------------------------------------------


async def test_a_finished_stream_logs_feature_model_tokens_latency_and_first_token_time(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _ = make_client([list(REPLY)])

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        await read_all(await start(client))

    (fields,) = calls_logged(caplog, "gemini_call ")
    assert fields["feature"] == "coach"
    assert fields["model"] == get_settings().gemini_model_reasoning
    assert fields["tokens_in"] == 80
    assert fields["tokens_out"] == 162
    assert isinstance(fields["latency_ms"], int)
    assert isinstance(fields["time_to_first_token_ms"], int)
    assert fields["time_to_first_token_ms"] <= fields["latency_ms"]


# --- retries happen only before the first piece ----------------------------------------


async def test_a_failure_before_the_first_piece_is_retried() -> None:
    client, fake = make_client([unavailable(), list(REPLY)])

    stream = await start(client)

    assert await read_all(stream) == ["Start ", "with a month ", "of rent."]
    assert len(fake.calls) == 2


async def test_an_open_that_keeps_failing_raises_after_the_attempts_and_logs_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, fake = make_client([unavailable()] * 3)

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        with pytest.raises(GeminiUnavailableError):
            await start(client)

    assert len(fake.calls) == 3
    (fields,) = calls_logged(caplog, "gemini_call_failed")
    assert fields["outcome"] == "failed"
    assert fields["error"] == "GeminiUnavailableError"
    assert fields["attempts"] == 3


async def test_a_rejected_request_is_not_retried() -> None:
    client, fake = make_client([api_error(genai_errors.ClientError, 400, "INVALID_ARGUMENT")])

    with pytest.raises(GeminiRequestError):
        await start(client)

    assert len(fake.calls) == 1


async def test_a_stream_with_no_text_is_a_response_error_and_is_not_retried() -> None:
    client, fake = make_client([[text_response("", usage(5, 0))]])

    with pytest.raises(GeminiResponseError, match="no content"):
        await start(client)

    assert len(fake.calls) == 1
    assert fake.streams[0].closed


async def test_waiting_too_long_for_the_first_piece_times_out_and_is_retried() -> None:
    client, fake = make_client([[HANG], [HANG]], gemini_max_attempts=2)

    with pytest.raises(GeminiTimeoutError):
        await start(client, timeout_seconds=0.05)

    assert len(fake.calls) == 2
    assert all(stream.closed for stream in fake.streams)


# --- failures after the first piece end the iteration, never restart it ----------------


async def test_a_failure_mid_stream_ends_the_iteration_with_the_error_and_no_retry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, fake = make_client([[text_response("Start "), unavailable()]])
    received: list[str] = []

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        stream = await start(client)
        with pytest.raises(GeminiUnavailableError):
            async for piece in stream:
                received.append(piece)

    assert received == ["Start "]
    assert len(fake.calls) == 1
    assert fake.streams[0].closed
    (fields,) = calls_logged(caplog, "gemini_call_failed")
    assert fields["outcome"] == "failed"
    assert calls_logged(caplog, "gemini_call ") == []


async def test_a_pause_longer_than_the_timeout_between_pieces_is_a_timeout_error() -> None:
    client, fake = make_client([[text_response("Start "), HANG]])

    stream = await start(client, timeout_seconds=0.05)
    with pytest.raises(GeminiTimeoutError):
        await read_all(stream)

    assert fake.streams[0].closed


# --- closing and cancelling ------------------------------------------------------------


async def test_cancelling_the_reader_closes_the_upstream_call_and_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The worker's phone goes away: the endpoint's task is cancelled mid-reply."""
    client, fake = make_client([[text_response("Start "), HANG]])
    got_first = asyncio.Event()

    async def reader() -> None:
        stream = await start(client)
        async for _ in stream:
            got_first.set()

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        task = asyncio.create_task(reader())
        await asyncio.wait_for(got_first.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert fake.streams[0].closed
    (fields,) = calls_logged(caplog, "gemini_call_failed")
    assert fields["outcome"] == "cancelled"


async def test_cancelling_while_waiting_for_the_first_piece_closes_it_too(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, fake = make_client([[HANG]])

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        task = asyncio.create_task(start(client))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert fake.streams[0].closed
    (fields,) = calls_logged(caplog, "gemini_call_failed")
    assert fields["outcome"] == "cancelled"


async def test_leaving_async_with_early_closes_the_upstream_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, fake = make_client([list(REPLY)])

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        async with await start(client) as stream:
            async for _ in stream:
                break

    assert fake.streams[0].closed
    (fields,) = calls_logged(caplog, "gemini_call_failed")
    assert fields["outcome"] == "closed"
    assert fields["error"] is None


async def test_closing_twice_or_after_the_end_is_harmless_and_logs_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _ = make_client([list(REPLY)])

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        stream = await start(client)
        await read_all(stream)
        await stream.aclose()
        await stream.aclose()

    assert len(calls_logged(caplog, "gemini_call ")) == 1
    assert calls_logged(caplog, "gemini_call_failed") == []


async def test_a_second_attempt_does_not_repeat_a_piece_already_sent() -> None:
    """Retrying only before the first piece is what keeps the worker from seeing words twice."""
    client, fake = make_client([[text_response("Start "), unavailable()], list(REPLY)])
    received: list[str] = []

    stream = await start(client)
    with pytest.raises(GeminiUnavailableError):
        async for piece in stream:
            received.append(piece)

    assert received == ["Start "]
    assert len(fake.calls) == 1
    assert len(fake.outcomes) == 1  # the second reply was never asked for
