"""A client for the Coach routes that behaves like the app's own screens (NF-FC-024).

It sends the same requests and follows the same rules as `docs/api/v2-coach.md`: a turn carries an
`Idempotency-Key`, a stream that ends with neither `done` nor `error` is sent again with the same
key, and text and facts count only once `done` has arrived. It also keeps under the Gemini budget
of 10 turns a minute per worker, so a run does not spend its time being refused.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

API = "/api/v2/coach"
TURN_ATTEMPTS = 3
PLAN_ATTEMPTS = 6
# The conventions' codes for "the same request is still being handled": wait and ask again.
BUSY_CODES = {"turn_in_progress", "request_in_progress"}

Sleep = Callable[[float], Awaitable[None]]


class SetupError(RuntimeError):
    """The run cannot start: no access, the module is off for this account, or no server."""


class TurnFailed(RuntimeError):
    """A turn was refused or did not complete after its tries; the session may be left half way."""


class StreamError(RuntimeError):
    """The server sent something that is not a well-formed event."""


@dataclass(frozen=True)
class Reply:
    """A plain JSON answer, or the refusal that came instead of a stream."""

    status: int
    body: Any
    request_id: str | None
    retry_after: float | None = None

    @property
    def code(self) -> str | None:
        if isinstance(self.body, dict) and "code" in self.body:
            return str(self.body["code"])
        return None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


@dataclass
class Turn:
    """What one turn's stream carried. `done` is set only when the turn completed."""

    request_id: str | None
    text: str = ""
    slot_updates: list[dict[str, Any]] = field(default_factory=list)
    first_token_s: float | None = None
    done: dict[str, Any] | None = None
    failure: str = "the stream ended without done"
    attempts: int = 1


async def events(lines: AsyncIterator[str]) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """The `event:` / `data:` pairs of a stream; comment lines (`: ping`) are skipped."""
    name = "message"
    data: list[str] = []
    async for line in lines:
        if line == "":
            if data:
                try:
                    yield name, json.loads("\n".join(data))
                except ValueError as exc:
                    raise StreamError(f"event {name!r} has data that is not JSON") from exc
            name, data = "message", []
        elif line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return None


def _loads(raw: bytes) -> Any:
    try:
        return json.loads(raw)
    except ValueError:
        return None


class CoachApi:
    """The Coach routes for one worker, paced to `rpm` Gemini-spending calls a minute."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        rpm: int = 0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            transport=transport,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        self._interval = 60.0 / rpm if rpm else 0.0
        self._next_start = 0.0
        self._sleep = sleep
        self._clock = clock
        self.request_ids: list[str] = []
        self.retries = 0

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _pace(self) -> None:
        if not self._interval:
            return
        now = self._clock()
        wait = self._next_start - now
        self._next_start = max(now, self._next_start) + self._interval
        if wait > 0:
            await self._sleep(wait)

    def _seen(self, response: httpx.Response) -> str | None:
        request_id: str | None = response.headers.get("X-Request-ID")
        if request_id:
            self.request_ids.append(request_id)
        return request_id

    async def call(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        paced: bool = False,
        wait_s: float | None = None,
    ) -> Reply:
        """One JSON request. `paced` marks a call that can spend the Gemini budget."""
        if paced:
            await self._pace()
        response = await self._http.request(
            method,
            f"{API}{path}",
            json=body,
            timeout=wait_s if wait_s else httpx.USE_CLIENT_DEFAULT,
        )
        return Reply(
            response.status_code,
            _loads(response.content),
            self._seen(response),
            _retry_after(response),
        )

    async def turn(self, session_id: str, text: str | None, language: str) -> Turn:
        """One turn, sent again with the same key when the stream drops or Gemini is busy.

        Raises:
            TurnFailed: The turn was refused for good, or did not complete in `TURN_ATTEMPTS`.
        """
        body: dict[str, str] = {"language": language}
        if text is not None:
            body["text"] = text
        key = uuid.uuid4().hex
        why = "no attempt was made"
        for attempt in range(1, TURN_ATTEMPTS + 1):
            if attempt > 1:
                self.retries += 1
            await self._pace()
            try:
                refusal, streamed = await self._turn_once(session_id, body, key)
            except (httpx.TransportError, StreamError) as exc:
                why = f"{type(exc).__name__}: {exc}"[:200]
                continue
            if refusal is not None:
                why = f"HTTP {refusal.status} {refusal.code}"
                if refusal.status in (429, 502, 503, 504) or refusal.code in BUSY_CODES:
                    await self._sleep(refusal.retry_after or 2.0)
                    continue
                raise TurnFailed(f"the turn was refused: {why}")
            assert streamed is not None
            if streamed.done is not None:
                streamed.attempts = attempt
                return streamed
            why = streamed.failure
        raise TurnFailed(f"no complete turn in {TURN_ATTEMPTS} tries; last: {why}")

    async def _turn_once(
        self, session_id: str, body: dict[str, str], key: str
    ) -> tuple[Reply | None, Turn | None]:
        started = self._clock()
        headers = {"Idempotency-Key": key, "Accept": "text/event-stream"}
        async with self._http.stream(
            "POST", f"{API}/sessions/{session_id}/messages", json=body, headers=headers
        ) as response:
            request_id = self._seen(response)
            if response.status_code != 200:
                raw = await response.aread()
                refusal = Reply(
                    response.status_code, _loads(raw), request_id, _retry_after(response)
                )
                return refusal, None
            turn = Turn(request_id=request_id)
            async for name, data in events(response.aiter_lines()):
                if name == "token":
                    turn.text += str(data.get("text", ""))
                    if turn.first_token_s is None:
                        turn.first_token_s = self._clock() - started
                elif name == "slot_update":
                    turn.slot_updates.append(data)
                elif name == "done":
                    turn.done = data
                    break
                elif name == "error":
                    turn.failure = f"error event {data.get('code')}"
                    break
        return None, turn

    async def make_plan(self, session_id: str, language: str) -> Reply:
        """Ask for the plan; wait while the same plan is being made or Gemini is busy.

        A refusal that says the plan failed its checks (`ai_bad_response`) or that the score
        cannot be worked out is returned as it is: it is a result of the run, not a thing to retry.
        """
        reply = Reply(0, None, None)
        for attempt in range(1, PLAN_ATTEMPTS + 1):
            if attempt > 1:
                self.retries += 1
            reply = await self.call(
                "POST",
                f"/sessions/{session_id}/plan",
                body={"language": language},
                paced=True,
                wait_s=150,
            )
            busy = reply.status in (429, 503, 504) and reply.code != "score_unavailable"
            if reply.code == "request_in_progress" or busy:
                await self._sleep(reply.retry_after or 5.0)
                continue
            break
        return reply
