"""The API as the load test runs it: the real app, a stand-in for Gemini, and a read counter.

Run from backend/ against the Firebase emulators (NF-HR-007, `tests/load/README.md`):

    uvicorn tests.load.load_app:app --host 127.0.0.1 --port 8080

What is real: the routing, middleware, rate limiter, token check (against the Auth emulator),
every service and repository, and Firestore (the emulator). What is not: Gemini. Its answers are
canned and arrive after a delay shaped like the latencies measured in production
(`docs/runbooks/NF-P4-003-performance-profiling.md`), so the run measures what the service itself
does while it waits: the event loop, the thread pool, Firestore, the streams and the PDF renderer.
`LOAD_GEMINI_SCALE` multiplies every delay (0 makes the stand-in instant).

It also counts the Firestore documents each request reads. `GET /__load/reads` returns the count
by route (`?reset=1` clears it) and every response carries `X-Firestore-Reads`; a streamed answer
is counted in the totals, since its header is sent before the reads are done. Nothing here is
imported by the real app.
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import os
import re
import time
from collections import defaultdict
from typing import Any

from fastapi import FastAPI
from google.cloud.firestore_v1.aggregation import AggregationQuery
from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.query import Query
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.dependencies import get_similar_scam_finder
from app.integrations.gemini import ChatReply, get_gemini_client
from app.main import create_app
from app.schemas.coach_extraction import SlotExtraction
from app.schemas.coach_guard import ScopeVerdict
from app.schemas.coach_review import ReviewReading
from app.schemas.scam_classify import ScamClassification
from app.schemas.scam_explain import BenignReassurance, ScamExplanation
from app.services.scam.retrieval import NOTHING_FOUND, Retrieval
from tests.fixtures.coach_plan_data import compliant_text, translated_text
from tests.fixtures.fake_gemini import FakeStream

SCALE = float(os.environ.get("LOAD_GEMINI_SCALE", "1"))

# Seconds a call takes in production (median; NF-P4-003, "Gemini latency"). A call that thinks
# (the reasoning tier) is the slow one; the reply is a first token and then a stream.
LATENCY = {
    "scam.classify": 2.0,
    "scam.explain": 12.0,
    "scam.reassure": 2.5,
    "coach.guard": 1.0,
    "coach.extract": 2.0,
    "coach.review": 2.0,
    "coach.summarise": 2.0,
    "coach.plan": 25.0,
    "coach.translate_plan": 10.0,
    "embedding": 0.2,
}
FIRST_TOKEN = 1.2
PER_PIECE = 0.05
REPLY = (
    "Thank you, that helps. Let us look at the next part of your plan together. "
    "What is your monthly pay, and in which currency?"
)
VECTOR_SEARCH_SECONDS = 0.3


async def _wait(operation: str) -> None:
    await asyncio.sleep(LATENCY.get(operation, 1.0) * SCALE)


class SlowStream(FakeStream):
    """A reply that arrives a few words at a time, after a first-token delay."""

    def __init__(self, pieces: list[str]) -> None:
        super().__init__(pieces)
        self._started = False

    async def __anext__(self) -> str:
        if not self._started:
            self._started = True
            await asyncio.sleep(FIRST_TOKEN * SCALE)
        else:
            await asyncio.sleep(PER_PIECE * SCALE)
        return await super().__anext__()


class LatencyGemini:
    """The part of `GeminiClient` the services use, answering canned and late."""

    async def generate_structured(self, **kwargs: Any) -> Any:
        operation: str = kwargs["operation"]
        await _wait(operation)
        model = kwargs["response_model"]
        contents = str(kwargs["contents"])
        if model is ScamClassification:
            # Half the messages are scams, decided by the text, so a repeat is the same verdict.
            scam = int(hashlib.sha256(contents.encode()).hexdigest(), 16) % 2 == 0
            return ScamClassification.model_validate(
                {
                    "is_scam": scam,
                    "scam_type": "illegal_recruitment_fee" if scam else None,
                    "tactics": ["urgency"] if scam else [],
                    "risk_level": "high" if scam else "low",
                    "confidence": 0.9,
                    "trigger_phrases": [],
                    "message_language": "en",
                    "details": {},
                }
            )
        if model is ScamExplanation:
            return ScamExplanation.model_validate(
                {
                    "why_it_works": [{"tactic": "urgency", "text": "It rushes you."}],
                    "scammer_wants": "Your money before a real contract.",
                    "next_steps": ["Do not pay.", "Check the agency.", "Tell a support group."],
                }
            )
        if model is BenignReassurance:
            return BenignReassurance(reassurance="This looks normal.", tip="Check the sender.")
        if model is ScopeVerdict:
            return ScopeVerdict(label="on_topic", confidence=0.95)
        if model is SlotExtraction:
            return SlotExtraction(message_kind="other", candidates=[])
        if model is ReviewReading:
            return ReviewReading(action="other", confidence=0.5)
        if operation == "coach.plan":
            return compliant_text(contents)
        if operation == "coach.translate_plan":
            return translated_text(contents)
        raise NotImplementedError(f"the load stand-in has no answer for {operation!r}")

    async def chat(self, **kwargs: Any) -> ChatReply:
        await _wait(kwargs["operation"])
        return ChatReply(text="The worker is planning a move abroad.", dropped_turns=[])

    async def stream(self, **kwargs: Any) -> SlowStream:
        words = REPLY.split(" ")
        return SlowStream([w + " " for w in words[:-1]] + [words[-1]])

    async def embed_text(self, text: str, *, operation: str) -> list[float]:
        await _wait("embedding")
        return [0.0] * 768


class SleepingFinder:
    """The similar-scam search: the emulator has no vector search, so it only takes its time."""

    async def find(self, *_args: Any, **_kwargs: Any) -> Retrieval:
        await asyncio.sleep((LATENCY["embedding"] + VECTOR_SEARCH_SECONDS) * SCALE)
        return NOTHING_FOUND


# --- counting the documents a request reads --------------------------------------------------

_counter: contextvars.ContextVar[list[int] | None] = contextvars.ContextVar(
    "firestore_reads", default=None
)
_totals: dict[str, list[int]] = defaultdict(list)


def _add(n: int = 1) -> None:
    counter = _counter.get()
    if counter is not None:
        counter[0] += n


def _install_counters() -> None:
    """Count what the client returns: a document, found or not, is a read; an aggregation is one."""
    get_all = Client.get_all
    stream = Query.stream
    aggregate = AggregationQuery.get

    def counted_get_all(self: Client, *args: Any, **kwargs: Any) -> Any:
        for snapshot in get_all(self, *args, **kwargs):
            _add()
            yield snapshot

    def counted_stream(self: Query, *args: Any, **kwargs: Any) -> Any:
        for snapshot in stream(self, *args, **kwargs):
            _add()
            yield snapshot

    def counted_aggregate(self: AggregationQuery, *args: Any, **kwargs: Any) -> Any:
        _add()
        return aggregate(self, *args, **kwargs)

    Client.get_all = counted_get_all  # type: ignore[method-assign,assignment]
    Query.stream = counted_stream  # type: ignore[method-assign,assignment]
    AggregationQuery.get = counted_aggregate  # type: ignore[method-assign,assignment]


_ID = re.compile(r"/[0-9a-f]{20,}|/[A-Za-z0-9_-]{20,}")


class ReadCounter:
    """ASGI middleware: one counter per request, a header, and totals by route."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].startswith("/__load/"):
            await self.app(scope, receive, send)
            return
        counter = [0]
        token = _counter.set(counter)
        started = time.perf_counter()

        async def counting_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-firestore-reads", str(counter[0]).encode()))
                message = {**message, "headers": headers}
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                route = scope.get("route")
                key = f"{scope['method']} {getattr(route, 'path', _ID.sub('/{id}', scope['path']))}"
                _totals[key].append(counter[0])
                _totals[f"{key} #ms"].append(round((time.perf_counter() - started) * 1000))
            await send(message)

        try:
            await self.app(scope, receive, counting_send)
        finally:
            _counter.reset(token)


def _install_session_start_without_the_transaction_query() -> None:
    """Start or resume a session without a query inside a transaction.

    The Firestore emulator makes transactions that run a query contend across different workers'
    sub-collections ("Transaction lock timeout": 2 workers at once take 2 s, 10 take 30 s and
    fail with 409), which a probe with the plain client shows too; reading a document in a
    transaction does not. Production Firestore locks per collection path and is not known to
    behave so, but that is not verified (D-273). This stand-in keeps the same reads and writes,
    without the transaction, so the rest of the Coach path can be measured. Set
    `LOAD_KEEP_SESSION_TRANSACTION=1` to run the real one.
    """
    from google.cloud.firestore_v1.base_query import FieldFilter

    from app.repositories.coach_session_repo import CoachSessionRepository

    def create_or_resume(
        self: CoachSessionRepository,
        uid: str,
        session_id: str,
        document: dict[str, Any],
        *,
        restart: bool,
        idle_before: Any,
    ) -> tuple[str, dict[str, Any], bool]:
        sessions = self._sessions(uid)
        query = sessions.where(filter=FieldFilter("status", "==", "active")).limit(5)
        for snapshot in query.stream():
            stored = snapshot.to_dict() or {}
            idle = stored.get("last_active") is None or stored["last_active"] <= idle_before
            if restart or idle:
                snapshot.reference.update({"status": "abandoned"})
                continue
            return str(snapshot.id), stored, True
        sessions.document(session_id).set(document)
        return session_id, document, False

    CoachSessionRepository.create_or_resume = create_or_resume  # type: ignore[method-assign]


def build() -> FastAPI:
    _install_counters()
    if not os.environ.get("LOAD_KEEP_SESSION_TRANSACTION"):
        _install_session_start_without_the_transaction_query()
    app = create_app()
    app.dependency_overrides[get_gemini_client] = lambda: LatencyGemini()
    finder = SleepingFinder()
    app.dependency_overrides[get_similar_scam_finder] = lambda: finder

    @app.get("/__load/reads", include_in_schema=False)
    async def reads(reset: int = 0) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        for key, values in sorted(_totals.items()):
            if key.endswith(" #ms"):
                continue
            ms = sorted(_totals.get(f"{key} #ms", []))
            summary[key] = {
                "requests": len(values),
                "reads_total": sum(values),
                "reads_max": max(values),
                "reads_mean": round(sum(values) / len(values), 2),
                "ms_p50": ms[len(ms) // 2] if ms else None,
            }
        if reset:
            _totals.clear()
        return summary

    return app


app = ReadCounter(build())  # type: ignore[assignment]
