"""The Server-Sent Events helpers (NF-FC-009): the wire format and the heartbeat."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from app.core.sse import PING, sse_event, with_heartbeat

pytestmark = pytest.mark.anyio


def test_an_event_is_an_event_line_a_one_line_json_data_line_and_a_blank_line() -> None:
    frame = sse_event("token", {"text": "नमस्ते\nfriend"})

    assert frame == 'event: token\ndata: {"text":"नमस्ते\\nfriend"}\n\n'
    assert frame.count("\n") == 3  # the newline inside the text is escaped, not a line break


async def _frames(*items: str, wait: float = 0.0) -> AsyncIterator[str]:
    for item in items:
        await asyncio.sleep(wait)
        yield item


async def _collect(frames: AsyncIterator[str]) -> list[str]:
    return [frame async for frame in frames]


async def test_frames_pass_through_in_order_and_the_end_ends_the_stream() -> None:
    assert await _collect(with_heartbeat(_frames("a", "b", "c"), 5)) == ["a", "b", "c"]


async def test_a_ping_is_sent_whenever_the_interval_passes_with_no_frame() -> None:
    result = await _collect(with_heartbeat(_frames("a", wait=0.12), 0.03))

    assert result[-1] == "a" and result.count(PING) >= 2
    assert PING == ": ping\n\n"


async def test_an_error_in_the_source_reaches_the_reader() -> None:
    async def broken() -> AsyncIterator[str]:
        yield "first"
        raise RuntimeError("boom")

    seen: list[str] = []
    with pytest.raises(RuntimeError, match="boom"):
        async for frame in with_heartbeat(broken(), 5):
            seen.append(frame)
    assert seen == ["first"]


async def test_closing_the_reader_cancels_the_source_so_what_it_holds_is_released() -> None:
    released = asyncio.Event()

    async def hanging() -> AsyncIterator[str]:
        try:
            yield "first"
            await asyncio.Event().wait()
        finally:
            released.set()

    stream = with_heartbeat(hanging(), 5)
    assert await anext(stream) == "first"
    await stream.aclose()

    assert released.is_set()


async def test_cancelling_the_reader_cancels_the_source() -> None:
    released = asyncio.Event()

    async def hanging() -> AsyncIterator[str]:
        try:
            await asyncio.Event().wait()
            yield "never"
        finally:
            released.set()

    task = asyncio.create_task(_collect(with_heartbeat(hanging(), 5)))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert released.is_set()
