"""Locust scenarios for the load test (NF-HR-007). See `tests/load/README.md`.

    locust -f tests/load/locustfile.py --headless -u 25 -r 5 -t 3m --host http://127.0.0.1:8080

`LOAD_SCENARIO` picks what runs: `scam`, `coach`, `v1` (the endpoints that existed before the
Future Scope work, for the comparison with v1.0) or `all`. `LOAD_WORKERS` is how many seeded
workers there are (`python -m tests.load.seed --users N`): each simulated user is one of them, so
the per-user limits are exercised as they would be for real workers. Run against the emulators and
`tests.load.load_app`, never against production.
"""

from __future__ import annotations

import itertools
import json
import os
import random
import time
import uuid
from typing import Any

import requests
from locust import HttpUser, between, events, task

AUTH = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
WORKERS = int(os.environ.get("LOAD_WORKERS", "60"))
SCENARIO = os.environ.get("LOAD_SCENARIO", "all")
PASSWORD = "load-test-only-password"
_next_worker = itertools.count()


def _weight(name: str) -> int:
    return 1 if SCENARIO in ("all", name) else 0


def _token(n: int) -> str:
    response = requests.post(
        f"http://{AUTH}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=demo-api-key",
        json={
            "email": f"load-{n:03d}@load.example",
            "password": PASSWORD,
            "returnSecureToken": True,
        },
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["idToken"])


class Worker(HttpUser):
    """A signed-in worker: one seeded account, a bearer token on every call."""

    abstract = True
    wait_time = between(2, 4)

    def on_start(self) -> None:
        self.number = next(_next_worker) % WORKERS
        self.client.headers["Authorization"] = f"Bearer {_token(self.number)}"
        self.client.headers["Accept-Language"] = "en"


def _stream(user: HttpUser, name: str, path: str, body: dict[str, Any]) -> None:
    """One streamed turn: success only if the stream ends with `done`; the time to the first
    token and the whole turn are reported as their own rows (Locust times the headers)."""
    started = time.perf_counter()
    first: float | None = None
    done = False
    with user.client.post(
        path,
        json=body,
        headers={"Accept": "text/event-stream", "Idempotency-Key": str(uuid.uuid4())},
        stream=True,
        name=name,
        catch_response=True,
    ) as response:
        if response.status_code != 200:
            response.failure(f"{response.status_code}: {response.text[:120]}")
            return
        for line in response.iter_lines():
            if first is None and line.startswith(b"event: token"):
                first = time.perf_counter()
            if line.startswith(b"event: done"):
                done = True
            if line.startswith(b"event: error"):
                response.failure("the stream ended with an error event")
                return
        if done:
            response.success()
        else:
            response.failure("the stream ended without `done`")
    environment = user.environment
    total = (time.perf_counter() - started) * 1000
    if first is not None:
        environment.events.request.fire(
            request_type="SSE",
            name=f"{name} (first token)",
            response_time=(first - started) * 1000,
            response_length=0,
            exception=None,
            context={},
        )
    environment.events.request.fire(
        request_type="SSE",
        name=f"{name} (complete)",
        response_time=total,
        response_length=0,
        exception=None if done else RuntimeError("no done"),
        context={},
    )


class ScamUser(Worker):
    weight = _weight("scam")

    def on_start(self) -> None:
        super().on_start()
        self.seen: list[str] = []

    @task(4)
    def analyze_new(self) -> None:
        text = (
            f"Congratulations. Pay the placement fee of {random.randint(500, 3000)} SGD to account "
            f"{random.randint(10**9, 10**10)} before {uuid.uuid4().hex[:8]} or lose your job."
        )
        self.seen.append(text)
        self.client.post(
            "/api/v2/scam/analyze",
            json={"text": text, "language": "en", "corridor_id": "SG-IN"},
            name="POST /scam/analyze (new message)",
        )

    @task(2)
    def analyze_again(self) -> None:
        if not self.seen:
            return
        self.client.post(
            "/api/v2/scam/analyze",
            json={"text": random.choice(self.seen), "language": "en", "corridor_id": "SG-IN"},
            name="POST /scam/analyze (repeat, from cache)",
        )

    @task(3)
    def history(self) -> None:
        self.client.get("/api/v2/scam/checks?limit=20", name="GET /scam/checks")


class CoachUser(Worker):
    weight = _weight("coach")

    def on_start(self) -> None:
        super().on_start()
        self.session: str | None = None
        self.plan: str | None = None
        started = self.client.post("/api/v2/coach/sessions", json={"language": "en"})
        if started.ok:
            self.session = started.json()["id"]
        overview = self.client.get("/api/v2/coach/overview")
        if overview.ok and overview.json().get("plan"):
            self.plan = overview.json()["plan"]["id"]

    @task(5)
    def turn(self) -> None:
        if self.session is None:
            return
        _stream(
            self,
            "POST /coach/sessions/{id}/messages",
            f"/api/v2/coach/sessions/{self.session}/messages",
            {"text": "I will work as a domestic worker in Singapore.", "language": "en"},
        )

    @task(2)
    def session_view(self) -> None:
        if self.session is not None:
            self.client.get(
                f"/api/v2/coach/sessions/{self.session}", name="GET /coach/sessions/{id}"
            )

    @task(1)
    def overview(self) -> None:
        self.client.get("/api/v2/coach/overview", name="GET /coach/overview")

    @task(2)
    def plan_view(self) -> None:
        if self.plan is not None:
            self.client.get(
                f"/api/v2/coach/plans/{self.plan}?language=en", name="GET /coach/plans/{id}"
            )

    @task(1)
    def plan_pdf(self) -> None:
        if self.plan is not None:
            self.client.get(
                f"/api/v2/coach/plans/{self.plan}.pdf?language=en", name="GET /coach/plans/{id}.pdf"
            )


class V1User(Worker):
    """The endpoints that existed in v1.0, to compare the same load before and after."""

    weight = _weight("v1")

    @task(4)
    def compare(self) -> None:
        self.client.post(
            "/api/v1/remittance/compare",
            json={"corridor_id": "SG-IN", "amount": random.choice([200, 300, 400, 500])},
            name="POST /remittance/compare",
        )

    @task(2)
    def trends(self) -> None:
        self.client.get(
            "/api/v1/remittance/trends?corridor_id=SG-IN&days=30", name="GET /remittance/trends"
        )

    @task(2)
    def savings(self) -> None:
        self.client.get(
            "/api/v1/remittance/savings?corridor_id=SG-IN&amount=400&months=12",
            name="GET /remittance/savings",
        )

    @task(2)
    def log_income(self) -> None:
        self.client.post(
            "/api/v1/fib/income",
            json={"amount": 650, "currency": "SGD", "category": "salary"},
            name="POST /fib/income",
        )


@events.test_start.add_listener
def _announce(environment: Any, **_kwargs: Any) -> None:
    print(f"scenario={SCENARIO} workers={WORKERS} host={environment.host}")


def summary(path: str) -> dict[str, Any]:  # pragma: no cover - a helper for the report script
    return json.load(open(path, encoding="utf-8"))  # type: ignore[no-any-return]
