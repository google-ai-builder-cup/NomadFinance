"""Server-Sent Events as the v2 conventions write them (`docs/api/v2-conventions.md`, section 4)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

SSE_MEDIA_TYPE = "text/event-stream; charset=utf-8"
SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}
HEARTBEAT_SECONDS = 15.0
# A comment line: clients ignore it. It keeps a proxy or the phone's radio from closing the
# connection while the model is still thinking.
PING = ": ping\n\n"


def sse_event(event: str, data: Any) -> str:
    """One event: the `event:` line, a `data:` line of one-line JSON, a blank line."""
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {body}\n\n"


async def with_heartbeat(
    frames: AsyncIterator[str], interval: float = HEARTBEAT_SECONDS
) -> AsyncGenerator[str, None]:
    """Pass `frames` through, adding a `: ping` whenever `interval` seconds pass with none.

    `frames` runs in its own task so a wait for the model can be interrupted by the timer. If
    the reader goes away (the client closed the connection) this generator is cancelled or
    closed and the task is cancelled with it, which closes whatever `frames` had open: the
    upstream Gemini call is never left running for nobody.
    """
    queue: asyncio.Queue[str | BaseException | None] = asyncio.Queue()

    async def pump() -> None:
        try:
            async for frame in frames:
                await queue.put(frame)
            await queue.put(None)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:  # handed to the reader, which re-raises it
            await queue.put(exc)

    task = asyncio.create_task(pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval)
            except TimeoutError:
                yield PING
                continue
            if item is None:
                return
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
