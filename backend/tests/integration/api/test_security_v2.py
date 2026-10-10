"""NF-HR-008: the OWASP API Top 10 walked over every `/api/v2` route, as tests.

The table is read from the app, so a route added later without its controls fails here instead
of in review. The checks that were already in the feature tests (the 21 bad tokens of
`test_auth_matrix.py`, one worker's id on another worker's route in each feature's own file) are
not repeated; this file adds what they leave out: every route in one table, the answers a
stranger and a missing id give, what an answer may contain, extra fields in a body, the size
of a JSON body, and what a prompt may contain. `docs/security-review-v2.md` has the verdicts.
"""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.dependencies import (
    get_coach_plans,
    get_coach_sessions,
    get_coach_turns,
    get_current_user,
    get_feature_flag_service,
)
from app.main import create_app
from app.repositories.coach_session_repo import get_coach_plan_repository
from app.schemas.user import AuthenticatedUser
from app.services.coach.turn_service import CoachTurns
from app.services.feature_flag_service import FeatureFlagService
from tests.fixtures.coach_checkins import PLAN_ID, FakePlans
from tests.fixtures.coach_checkins import FakeFlags as CheckinFlags
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_plan_data import UID, make_plans, reach_plan_stage
from tests.fixtures.coach_turns import StubExtractor, StubGemini
from tests.fixtures.fake_gemini import FakeGemini
from tests.fixtures.scam_app import make_app
from tests.fixtures.scam_checks import FakeCheckRepo, FakeIndicatorRepo, make_store
from tests.fixtures.scam_explain import recordings_for

MARICEL = next(p for p in load_personas().personas if p.id == "p01_sg_ph_maricel")
STRANGER = "mallory"
MISSING_SESSION = "s_" + "0" * 20
MISSING_PLAN = "0" * 20
MISSING_CHECK = "f" * 32
KEY = "key-0123456789abcdef"

# Every route of the v2 contract, with the flag that guards it (None: no flag).
ROUTES: dict[tuple[str, str], str | None] = {
    ("GET", "/api/v2/flags"): None,
    ("POST", "/api/v2/coach/sessions"): "coach",
    ("GET", "/api/v2/coach/sessions/{session_id}"): "coach",
    ("GET", "/api/v2/coach/overview"): "coach",
    ("POST", "/api/v2/coach/sessions/{session_id}/known"): "coach",
    ("POST", "/api/v2/coach/sessions/{session_id}/messages"): "coach",
    ("POST", "/api/v2/coach/sessions/{session_id}/plan"): "coach",
    ("GET", "/api/v2/coach/plans/{plan_id}.pdf"): "coach",
    ("GET", "/api/v2/coach/plans/{plan_id}"): "coach",
    ("PUT", "/api/v2/coach/plans/{plan_id}/checkins/{milestone}"): "coach",
    ("POST", "/api/v2/scam/analyze"): "scam",
    ("GET", "/api/v2/scam/checks"): "scam",
    ("GET", "/api/v2/scam/checks/{check_id}"): "scam",
    ("POST", "/api/v2/scam/checks/{check_id}/report"): "scam",
}
# Keys that must never be in an answer to a worker, at any depth.
FORBIDDEN_KEYS = {
    "uid",
    "user_id",
    "reporter_hash",
    "cache_key",
    "text_hash",
    "embedding",
    "vector",
    "revision",
    "models",
    "prompt_versions",
    "declined_slots",
    "question_bank_version",
    "last_turn",
    "idempotency_key",
}


class _Flags:
    def __init__(self, on: bool) -> None:
        self.on = on

    def get_feature_flags(self) -> dict[str, Any]:
        return {
            "flags": {
                "coach": {"enabled": self.on, "allow_uids": []},
                "scam": {"enabled": self.on, "allow_uids": []},
            }
        }


class World:
    """One real app over in-memory storage and recorded models, with a worker who has a session,
    a plan and a scam check, and a stranger to ask for them."""

    def __init__(self) -> None:
        self.scam_gemini = FakeGemini(recordings_for("high"))
        self.checks = make_store(FakeCheckRepo(), FakeIndicatorRepo())
        self.plans, self.service, _, _, _ = make_plans(MARICEL)
        self.stub = StubGemini()
        self.turns = CoachTurns(
            self.service, self.stub, extractor=StubExtractor()  # type: ignore[arg-type]
        )
        self.checkin_plans = FakePlans()
        self.session_id = asyncio.run(reach_plan_stage(self.service, MARICEL))
        with self.client(UID) as owner:
            self.plan_id: str = owner.post(
                f"/api/v2/coach/sessions/{self.session_id}/plan", json={"language": "en"}
            ).json()["id"]
            self.check_id: str = owner.post(
                "/api/v2/scam/analyze",
                json={"text": "Pay the fee today", "language": "en", "corridor_id": "SG-IN"},
            ).json()["id"]

    def client(self, uid: str, *, flags_on: bool = True) -> TestClient:
        app = make_app(self.scam_gemini, store=self.checks, uid=uid)
        flags = FeatureFlagService(_Flags(flags_on))  # type: ignore[arg-type]
        app.dependency_overrides[get_feature_flag_service] = lambda: flags
        app.dependency_overrides[get_coach_sessions] = lambda: self.service
        app.dependency_overrides[get_coach_plans] = lambda: self.plans
        app.dependency_overrides[get_coach_turns] = lambda: self.turns
        # The check-in route reads its own repository; without this it would build a real
        # Firestore client, which a machine with no Google credentials (CI) cannot.
        app.dependency_overrides[get_coach_plan_repository] = lambda: self.checkin_plans
        return TestClient(app, raise_server_exceptions=False)

    def calls(self, session_id: str, plan_id: str, check_id: str) -> list[tuple[str, str, Any]]:
        """One valid request for every route that takes an id, as `(method, path, body)`."""
        coach = f"/api/v2/coach/sessions/{session_id}"
        return [
            ("GET", coach, None),
            ("POST", f"{coach}/known", {"keep": []}),
            ("POST", f"{coach}/messages", {"text": "I earn 2000", "language": "en"}),
            ("POST", f"{coach}/plan", {"language": "en"}),
            ("GET", f"/api/v2/coach/plans/{plan_id}", None),
            ("GET", f"/api/v2/coach/plans/{plan_id}.pdf", None),
            ("GET", f"/api/v2/scam/checks/{check_id}", None),
            ("POST", f"/api/v2/scam/checks/{check_id}/report", {"indicator_ids": []}),
        ]


@pytest.fixture(scope="module")
def world() -> World:
    return World()


def _send(api: TestClient, method: str, path: str, body: Any) -> Any:
    headers = {"Idempotency-Key": KEY} if path.endswith("/messages") else {}
    return api.request(method, path, json=body, headers=headers)


def _shape(response: Any) -> tuple[int, str | None, str | None]:
    """What a caller can tell apart: status, code and message (the request id is per call)."""
    body = response.json() if "json" in response.headers.get("content-type", "") else {}
    return response.status_code, body.get("code"), body.get("message")


def _keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from _keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _keys(inner)


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for inner in value.values():
            yield from _strings(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _strings(inner)


# --- API9 inventory: the route table is the documented one --------------------------------------


def _v2_routes() -> set[tuple[str, str]]:
    """Every endpoint with its full path. An included router exposes one context per endpoint."""
    found: set[tuple[str, str]] = set()
    for route in create_app().routes:
        if isinstance(route, APIRoute):
            contexts: list[Any] = [route]
        elif hasattr(route, "effective_route_contexts"):
            contexts = list(route.effective_route_contexts())
        else:
            continue
        for context in contexts:
            if context.path.startswith("/api/v2"):
                found |= {(m, context.path) for m in context.methods - {"HEAD", "OPTIONS"}}
    return found


def test_the_v2_route_table_is_exactly_the_one_this_review_covers() -> None:
    assert _v2_routes() == set(ROUTES), "a v2 route was added or removed: review it, then list it"


# --- API5 / flags: a route behind a flag is not there when the flag is off ----------------------


def test_every_guarded_route_answers_the_unknown_path_answer_when_its_flag_is_off(
    world: World,
) -> None:
    api = world.client(UID, flags_on=False)
    unknown = _shape(api.get("/api/v2/coach/not-a-route"))
    bad: list[str] = []
    for method, path, body in world.calls(MISSING_SESSION, MISSING_PLAN, MISSING_CHECK):
        if _shape(_send(api, method, path, body)) != unknown:
            bad.append(f"{method} {path}")
    for method, path in [
        ("POST", "/api/v2/coach/sessions"),
        ("GET", "/api/v2/coach/overview"),
        ("GET", "/api/v2/scam/checks"),
    ]:
        if (
            _shape(_send(api, method, path, {"language": "en"} if method == "POST" else None))
            != unknown
        ):
            bad.append(f"{method} {path}")
    assert bad == [], f"a flag that is off still answers differently: {bad}"


# --- API1: another worker's id is the same answer as an id that does not exist ------------------


def _owner_state(world: World) -> list[Any]:
    with world.client(UID) as owner:
        return [
            owner.get(f"/api/v2/coach/sessions/{world.session_id}").json(),
            owner.get(f"/api/v2/coach/plans/{world.plan_id}").json(),
            owner.get(f"/api/v2/scam/checks/{world.check_id}").json(),
        ]


def test_a_strangers_id_and_a_missing_id_are_indistinguishable_and_change_nothing(
    world: World,
) -> None:
    before = _owner_state(world)
    stranger = world.client(STRANGER)
    mine = world.calls(world.session_id, world.plan_id, world.check_id)
    missing = world.calls(MISSING_SESSION, MISSING_PLAN, MISSING_CHECK)
    leaks: list[str] = []
    for (method, path, body), (_, absent, _) in zip(mine, missing, strict=True):
        got = _send(stranger, method, path, body)
        want = _send(stranger, method, absent, body)
        if got.status_code != 404 or _shape(got) != _shape(want):
            leaks.append(f"{method} {path}: {_shape(got)} against {_shape(want)}")
    assert leaks == [], leaks
    assert _owner_state(world) == before, "a stranger's call changed the owner's data"


def test_a_strangers_check_in_is_the_answer_for_a_plan_that_does_not_exist() -> None:
    plans = FakePlans()
    plans.add(uid="u1", plan_id=PLAN_ID)
    app = create_app()
    app.dependency_overrides[get_coach_plan_repository] = lambda: plans
    app.dependency_overrides[get_feature_flag_service] = lambda: CheckinFlags({"u1", "u2"})
    caller = {"uid": "u2"}
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid=caller["uid"])
    body = {"answers": {"remittance": "on_track", "savings": "behind", "pay": "full_on_time"}}

    with TestClient(app, raise_server_exceptions=False) as api:
        url = "/api/v2/coach/plans/{}/checkins/d30"
        theirs = api.put(url.format(PLAN_ID), json=body)
        absent = api.put(url.format("0" * 20), json=body)

    assert theirs.status_code == 404 and _shape(theirs) == _shape(absent)
    assert "checkins" not in plans.plans[("u1", PLAN_ID)]


def test_a_cursor_from_another_worker_is_refused_not_followed(world: World) -> None:
    with world.client(UID) as owner:
        for text in ("First message to check", "Second message to check"):
            owner.post("/api/v2/scam/analyze", json={"text": text, "language": "en"})
        page = owner.get("/api/v2/scam/checks", params={"limit": 1}).json()
    cursor = page["next_cursor"]
    assert cursor

    with world.client(STRANGER) as stranger:
        refused = stranger.get("/api/v2/scam/checks", params={"cursor": cursor})
        own = stranger.get("/api/v2/scam/checks").json()

    assert refused.status_code == 400 and refused.json()["code"] == "invalid_cursor"
    assert own["items"] == []


# --- API3: what an answer may contain -----------------------------------------------------------


def test_no_answer_to_the_owner_carries_an_internal_field_or_a_uid(world: World) -> None:
    with world.client(UID) as owner:
        answers = [
            owner.get(f"/api/v2/coach/sessions/{world.session_id}").json(),
            owner.get("/api/v2/coach/overview").json(),
            owner.get(f"/api/v2/coach/plans/{world.plan_id}").json(),
            owner.get("/api/v2/scam/checks").json(),
            owner.get(f"/api/v2/scam/checks/{world.check_id}").json(),
            owner.post(
                f"/api/v2/scam/checks/{world.check_id}/report", json={"indicator_ids": []}
            ).json(),
            owner.get("/api/v2/flags").json(),
        ]
    for answer in answers:
        assert not FORBIDDEN_KEYS & set(_keys(answer)), set(_keys(answer)) & FORBIDDEN_KEYS
        assert UID not in set(_strings(answer)), "the worker's uid is in an answer"


# --- mass assignment: a field the contract does not name is never written -----------------------


@pytest.mark.parametrize(
    "extra", [{"uid": "mallory", "status": "completed", "stage": "plan", "revision": 99}]
)
def test_extra_fields_in_a_body_change_nothing_that_is_stored(
    world: World, extra: dict[str, Any]
) -> None:
    with world.client(UID) as owner:
        before = owner.get(f"/api/v2/coach/sessions/{world.session_id}").json()
        owner.post(f"/api/v2/coach/sessions/{world.session_id}/known", json={"keep": [], **extra})
        owner.post("/api/v2/coach/sessions", json={"language": "en", **extra})
        owner.post(
            f"/api/v2/scam/checks/{world.check_id}/report", json={"indicator_ids": [], **extra}
        )
        after = owner.get(f"/api/v2/coach/sessions/{world.session_id}").json()
    assert after["status"] == before["status"]
    assert after["stage"] == before["stage"]
    assert STRANGER not in json.dumps(after)


def test_the_check_in_body_refuses_a_field_it_does_not_name(world: World) -> None:
    with world.client(UID) as owner:
        response = owner.put(
            f"/api/v2/coach/plans/{world.plan_id}/checkins/d30",
            json={
                "answers": {"remittance": "on_track", "savings": "on_track", "pay": "full_on_time"},
                "uid": STRANGER,
            },
        )
    assert response.status_code == 422


# --- API4: the size of a body -------------------------------------------------------------------


def test_a_json_body_over_a_few_hundred_kilobytes_is_refused_before_it_is_read(
    world: World,
) -> None:
    body = json.dumps({"text": "a" * (2 * 1024 * 1024), "language": "en"})
    with world.client(UID) as owner:
        response = owner.post(
            "/api/v2/scam/analyze", content=body, headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 413 and response.json()["code"] == "payload_too_large"


def test_a_message_at_the_documented_limit_is_still_accepted(world: World) -> None:
    text = "ü" * 4000
    with world.client(UID) as owner:
        response = owner.post("/api/v2/scam/analyze", json={"text": text, "language": "en"})
    assert response.status_code == 200, response.text


# --- API8: how an answer may be kept ------------------------------------------------------------


def test_a_worker_answer_is_never_stored_by_a_cache_and_is_not_sniffed(world: World) -> None:
    with world.client(UID) as owner:
        for path in (
            f"/api/v2/coach/plans/{world.plan_id}",
            "/api/v2/coach/overview",
            "/api/v2/scam/checks",
            f"/api/v2/scam/checks/{world.check_id}",
            "/api/v2/flags",
        ):
            response = owner.get(path)
            assert "no-store" in response.headers.get("cache-control", ""), path
            assert response.headers.get("x-content-type-options") == "nosniff", path


# --- API7 / model input: a link in a message is never followed ----------------------------------


def test_a_link_in_a_message_is_never_opened(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[Any] = []

    def refuse(self: socket.socket, address: Any) -> None:
        attempts.append(address)
        raise OSError("no network in this test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    text = (
        "Send the fee to http://169.254.169.254/latest/meta-data and http://127.0.0.1:8080/health"
    )
    with world.client(UID) as owner:
        response = owner.post("/api/v2/scam/analyze", json={"text": text, "language": "en"})
    assert response.status_code == 200
    assert "169.254.169.254" not in response.json()["redacted_text"]
    assert attempts == []


# --- Model input: what a prompt may contain -----------------------------------------------------


def test_nothing_one_worker_typed_reaches_a_prompt_built_for_another(world: World) -> None:
    marker = "MARKER-ALICE-91827"
    with world.client(UID) as owner:
        owner.post("/api/v2/scam/analyze", json={"text": f"{marker} pay the fee", "language": "en"})
    scam_calls_before = len(world.scam_gemini.calls)
    with world.client(STRANGER) as stranger:
        started = stranger.post("/api/v2/coach/sessions", json={"language": "en"}).json()
        stranger.post(
            f"/api/v2/coach/sessions/{started['id']}/messages",
            json={"text": "I work in Singapore", "language": "en"},
            headers={"Idempotency-Key": KEY},
        )
        stranger.post(
            "/api/v2/scam/analyze", json={"text": "Pay the fee today please", "language": "en"}
        )

    seen = json.dumps(world.stub.calls, default=str) + json.dumps(
        world.scam_gemini.calls[scam_calls_before:], default=str
    )
    assert marker not in seen
    assert UID not in seen
