"""A stand-in Coach server that answers the way the contract says, for the persona runner tests.

It plays each persona's script back correctly, one session per `POST /sessions`, in the order of
the file. A test breaks it on purpose through the hooks to show the runner notices (NF-FC-024).
This is the contract's behaviour, not the real server's: the real routes are exercised in
`tests/integration/api/test_coach_regression_routes.py`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx

from tests.fixtures.coach_personas import Persona
from tests.regression.coach_replay import script_for

Hook = Callable[[Persona, dict[str, Any]], None]


def _sse(events: list[tuple[str, dict[str, Any]]]) -> bytes:
    return "".join(f"event: {n}\ndata: {json.dumps(d)}\n\n" for n, d in events).encode("utf-8")


class _Session:
    def __init__(self, persona: Persona, today: date) -> None:
        self.persona = persona
        self.messages, self.expected = script_for(persona, today)
        self.answers = 0
        self.filled: dict[str, Any] = {}


class FakeCoach:
    """Serve the Coach routes for `personas` in order. Keep `calls` to see what was sent."""

    def __init__(self, personas: list[Persona], today: date) -> None:
        self.personas = personas
        self.today = today
        self.sessions: dict[str, _Session] = {}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.keys: list[str] = []
        self.replays: dict[str, bytes] = {}
        self._requests = 0
        # Hooks and switches a test sets to break the server.
        self.edit_session: Hook | None = None
        self.edit_plan: Hook | None = None
        self.plan_refusal: tuple[int, str] | None = None
        self.refuse_sessions: int | None = None
        self.drop_once: set[tuple[str, int]] = set()
        self.fill_on_follow_up = False
        self.extra_turn_for: str | None = None

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _reply(self, status: int, body: Any, **headers: str) -> httpx.Response:
        self._requests += 1
        headers["X-Request-ID"] = f"req-{self._requests:04d}"
        return httpx.Response(status, json=body, headers=headers)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v2/coach")
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.method, path, body))
        if self.refuse_sessions and path == "/sessions":
            return self._reply(self.refuse_sessions, {"code": "not_found", "message": "no"})
        if request.method == "POST" and path == "/sessions":
            session_id = f"s{len(self.sessions)}"
            persona = self.personas[len(self.sessions)]
            self.sessions[session_id] = _Session(persona, self.today)
            return self._reply(201, {"id": session_id, "resumed": False})
        match = re.fullmatch(r"/sessions/(\w+)(/messages|/plan)?", path)
        assert match, path
        session = self.sessions[match[1]]
        if match[2] == "/messages":
            return self._turn(session, match[1], body, request.headers["Idempotency-Key"])
        if match[2] == "/plan":
            return self._plan(session, body)
        return self._session(session)

    def _turn(self, s: _Session, session_id: str, body: dict[str, Any], key: str) -> httpx.Response:
        self._requests += 1
        headers = {"X-Request-ID": f"req-{self._requests:04d}", "content-type": "text/event-stream"}
        if key in self.replays:
            return httpx.Response(200, content=self.replays[key], headers=headers)
        self.keys.append(key)
        if "text" not in body:
            events: list[tuple[str, dict[str, Any]]] = [("token", {"text": "Hello. "})]
            events.append(("done", {"message_id": "m1", "stage": "intro", "turn_count": 0}))
            return httpx.Response(200, content=_sse(events), headers=headers)
        n = s.answers
        assert body["text"] == s.messages[n], "the runner sent the wrong message"
        if (s.persona.id, n) in self.drop_once:
            self.drop_once.discard((s.persona.id, n))
            return httpx.Response(
                200, content=_sse([("token", {"text": "Thank"})]), headers=headers
            )
        turn = s.persona.script[n]
        fills = list(turn.fills)
        if turn.coach_follow_up and self.fill_on_follow_up:
            fills = ["savings"]
        events = [
            ("slot_update", {"slot": f, "value": s.expected.get(f), "confirmed": True})
            for f in fills
        ]
        events.append(("token", {"text": "Thank you. "}))
        s.answers += 1
        count = s.answers + (1 if self.extra_turn_for == s.persona.id else 0)
        events.append(("done", {"message_id": f"m{n}", "stage": "intro", "turn_count": count}))
        for f in fills:
            s.filled[f] = s.expected.get(f)
        stream = _sse(events)
        self.replays[key] = stream
        return httpx.Response(200, content=stream, headers=headers)

    def _session(self, s: _Session) -> httpx.Response:
        done = s.answers == len(s.messages)
        persona = s.persona
        body: dict[str, Any] = {
            "stage": "plan" if done else "income",
            "turn_count": s.answers,
            "slots": {
                name: {"value": value, "confirmed": True, "source": "user"}
                for name, value in s.filled.items()
            },
            "score": {"total": persona.expected_score.total, "band": persona.expected_score.band},
        }
        if self.edit_session:
            self.edit_session(persona, body)
        return self._reply(200, body)

    def _plan(self, s: _Session, body: dict[str, Any]) -> httpx.Response:
        if self.plan_refusal:
            status, code = self.plan_refusal
            return self._reply(status, {"code": code, "message": "no"})
        persona = s.persona
        plan: dict[str, Any] = {
            "language": body["language"],
            "corridor_id": persona.corridor,
            "score": {"total": persona.expected_score.total, "band": persona.expected_score.band},
            "slots": s.expected,
            "plan": {"weeks": [{"week": i} for i in range(1, 14)], "disclaimer": "Not advice."},
        }
        if self.edit_plan:
            self.edit_plan(persona, plan)
        return self._reply(201, plan)
