"""The coach mocks in docs/mocks/coach/ must always parse as what the backend will really send.

Shape alone is not enough, so this also checks the facts a screen leans on: the next question
follows the question bank, the transcript is already redacted, a plan id is the real hash of its
slots, the plan's figures add up, the Hindi plan keeps every number, and the history, the
overview and the streams agree about the same worker.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.core.redact import redact_text
from app.schemas.coach_checkin import CheckinAnswerResponse
from app.schemas.coach_plan import CoachPlanResponse
from app.schemas.coach_profile import CoachProfile
from app.schemas.coach_session import (
    CoachOverview,
    CoachSession,
    CoachSessionCreateResponse,
)
from app.schemas.errors import ErrorEnvelope
from app.services.coach.known_details import OFFER_ORDER, SLOT_SOURCES
from app.services.coach.question_bank import is_applicable, load_question_bank
from tests.fixtures.coach_mocks import (
    JSON_FILES,
    MOCKS,
    SSE_FILES,
    is_success,
    load,
    plans_by_key,
    sessions_by_id,
)

# Codes of docs/api/v2-conventions.md section 2 that the coach uses, and the five it adds.
KNOWN_CODES = {
    "validation_failed",
    "rate_limited",
    "not_found",
    "unauthenticated",
    "request_in_progress",
    "ai_busy",
    "ai_unavailable",
    "ai_timeout",
    "ai_bad_response",
    "session_not_active",
    "session_full",
    "turn_in_progress",
    "plan_not_ready",
    "checkin_not_due",
}
SESSION_ID = r"[a-z0-9_]+"
PLAN_ID = r"[0-9a-f]{20}"
# The text of a plan: everything else in it (ids, figures, dates) must survive translation as is.
TEXT_KEYS = {"summary", "title", "actions", "text", "disclaimer"}
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _model_for(request: str) -> type[BaseModel] | None:
    method, path = request.split(" ", 1)
    path = path.split("?", 1)[0]
    routes: list[tuple[str, str, type[BaseModel] | None]] = [
        ("POST", r"/api/v2/coach/sessions", CoachSessionCreateResponse),
        ("GET", rf"/api/v2/coach/sessions/{SESSION_ID}", CoachSession),
        ("POST", rf"/api/v2/coach/sessions/{SESSION_ID}/known", CoachSession),
        ("POST", rf"/api/v2/coach/sessions/{SESSION_ID}/plan", CoachPlanResponse),
        ("GET", rf"/api/v2/coach/plans/{PLAN_ID}", CoachPlanResponse),
        ("GET", r"/api/v2/coach/overview", CoachOverview),
        ("PUT", rf"/api/v2/coach/plans/{PLAN_ID}/checkins/d(30|60|90)", CheckinAnswerResponse),
        ("POST", rf"/api/v2/coach/sessions/{SESSION_ID}/messages", None),
    ]
    for route_method, pattern, model in routes:
        if method == route_method and re.fullmatch(pattern, path):
            return model
    raise AssertionError(f"{request} is not a route of the contract")


def test_the_coach_mocks_exist() -> None:
    names = {path.name for path in JSON_FILES + SSE_FILES}

    assert {
        "sessions-create-01-new.json",
        "session-03-review.json",
        "plan-01-created.json",
        "plan-get-02-hindi.json",
        "overview-01-active-session.json",
        "turn-01-start.sse",
        "turn-05-review.sse",
        "turn-error-dropped.sse",
    } <= names


@pytest.mark.parametrize("path", JSON_FILES, ids=lambda path: path.name)
def test_each_mock_is_a_request_the_contract_has(path: Path) -> None:
    mock = load(path)

    _model_for(mock["request"])
    assert {"description", "request", "status"} <= set(mock)


@pytest.mark.parametrize(
    "path", [p for p in JSON_FILES if is_success(p)], ids=lambda path: path.name
)
def test_a_success_mock_fits_the_response_model_with_no_extra_fields(path: Path) -> None:
    mock = load(path)
    model = _model_for(mock["request"])
    assert model is not None

    parsed = model.model_validate(mock["body"])

    # What was set, written back out, is the file again: a stray or misspelt field would be dropped.
    assert parsed.model_dump(mode="json", exclude_unset=True) == mock["body"]


@pytest.mark.parametrize(
    "path", [p for p in JSON_FILES if not is_success(p)], ids=lambda path: path.name
)
def test_an_error_mock_is_the_standard_envelope(path: Path) -> None:
    mock = load(path)
    envelope = ErrorEnvelope.model_validate(mock["body"])

    assert envelope.request_id == mock["headers"]["X-Request-ID"]
    assert envelope.code in KNOWN_CODES
    assert (envelope.details is not None) == (envelope.code == "validation_failed")


def test_the_two_turn_refusals_that_wait_say_how_long() -> None:
    for name, seconds in (("turn-error-in-progress.json", "2"), ("turn-error-ai-busy.json", "30")):
        assert load(MOCKS / name)["headers"]["Retry-After"] == seconds
    assert load(MOCKS / "plan-error-in-progress.json")["headers"]["Retry-After"] == "5"


# ---- the sessions -------------------------------------------------------------------------------


@pytest.mark.parametrize("sid", sorted(sessions_by_id()))
def test_the_next_question_follows_the_question_bank(sid: str) -> None:
    session = sessions_by_id()[sid]
    bank = load_question_bank()
    profile = CoachProfile.model_validate({k: v["value"] for k, v in session["slots"].items()})
    asked = [
        q for q in bank.questions if is_applicable(q, profile) and q.slot not in session["slots"]
    ]

    if session["stage"] in ("review", "plan"):
        # Everything the worker had to answer is answered. The departure date may be left out.
        assert [q.slot for q in asked if q.required] == []
        assert session["next_slot"] is None
    else:
        assert session["next_slot"] == asked[0].slot
        assert session["stage"] == asked[0].stage


@pytest.mark.parametrize("sid", sorted(sessions_by_id()))
def test_the_transcript_is_whole_redacted_and_counts_the_answers(sid: str) -> None:
    session = sessions_by_id()[sid]
    messages = session["messages"]

    assert [m["id"] for m in messages] == [f"m_{i:03d}" for i in range(1, len(messages) + 1)]
    assert [m["at"] for m in messages] == sorted(m["at"] for m in messages)
    assert all(redact_text(m["text"]) == m["text"] for m in messages)
    assert [m["role"] for m in messages[:2]] in ([], ["coach", "user"])
    assert session["turn_count"] == sum(m["role"] == "user" for m in messages)
    assert session["last_active"] == (messages[-1]["at"] if messages else session["created_at"])
    assert session["language"] == (messages[-1]["language"] if messages else session["language"])


def test_a_stage_the_worker_confirmed_has_a_score_and_a_plan_screen_has_a_band_each() -> None:
    sessions = sessions_by_id()
    scored = {sid: s for sid, s in sessions.items() if s["score"]}

    assert set(scored) == {"s_03", "s_04", "s_05", "s_06", "s_07"}
    assert {s["score"]["band"] for s in scored.values()} == {
        "needs_work",
        "getting_ready",
        "well_prepared",
    }
    for session in scored.values():
        total = round(sum(f["score"] * f["weight"] for f in session["score"]["factors"]))
        assert total == session["score"]["total"]


def test_the_create_answers_are_sessions_that_exist_as_details() -> None:
    sessions = sessions_by_id()
    for name in (
        "sessions-create-01-new.json",
        "sessions-create-02-resumed.json",
        "sessions-create-03-known.json",
    ):
        body = dict(load(MOCKS / name)["body"])
        resumed = body.pop("resumed")

        assert body == sessions[body["id"]]
        assert resumed == (body["turn_count"] > 0)


def test_the_known_mocks_agree_with_each_other_and_with_the_rules_of_keeping() -> None:
    offered = sessions_by_id()["s_08"]["known"]["items"]
    applied = load(MOCKS / "known-01-applied.json")["body"]

    assert [item["slot"] for item in offered] == list(OFFER_ORDER)
    assert set(applied["slots"]) == {item["slot"] for item in offered}
    for item in offered:
        kept = applied["slots"][item["slot"]]
        assert kept == {
            "value": item["value"],
            "confirmed": True,
            "source": SLOT_SOURCES[item["source"]],
        }
    assert "known" not in applied and applied["messages"] == []
    assert applied["next_slot"] == "departure_date"


def test_a_completed_session_points_at_a_plan_that_exists() -> None:
    completed = sessions_by_id()["s_07"]

    assert any(key.startswith(completed["plan_id"]) for key in plans_by_key())


def test_the_overview_agrees_with_the_sessions_andplans_by_key() -> None:
    sessions = sessions_by_id()
    plans = {key.split("/")[0]: body for key, body in plans_by_key().items()}
    for path in (p for p in JSON_FILES if p.name.startswith("overview-")):
        body = load(path)["body"]
        if body["session"]:
            session = sessions[body["session"]["id"]]
            assert body["session"] == {
                k: session[k] for k in ("id", "stage", "language", "turn_count", "last_active")
            }
        if body["plan"]:
            plan = plans[body["plan"]["id"]]
            assert body["plan"] == {
                "id": plan["id"],
                "created_at": plan["created_at"],
                "score_total": plan["score"]["total"],
                "band": plan["score"]["band"],
                "departure_date": plan["departure_date"],
            }


# ---- the plans ----------------------------------------------------------------------------------


def _text_and_skeleton(node: Any) -> tuple[Any, list[str]]:
    """The node with its sentences blanked, and the numbers of those sentences in order."""
    numbers: list[str] = []
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key in TEXT_KEYS:
                strings = value if isinstance(value, list) else [value]
                for sentence in strings:
                    numbers += NUMBER.findall(sentence)
                out[key] = "" if not isinstance(value, list) else [""] * len(value)
            else:
                out[key], found = _text_and_skeleton(value)
                numbers += found
        return out, numbers
    if isinstance(node, list):
        parts = [_text_and_skeleton(item) for item in node]
        return [part for part, _ in parts], [n for _, found in parts for n in found]
    return node, numbers


def test_the_hindi_plan_keeps_every_figure_and_number_of_the_english_one() -> None:
    plans = plans_by_key()
    english = plans["5a202702c922fc9b4fcf/en"]["plan"]
    hindi = plans["5a202702c922fc9b4fcf/hi"]["plan"]

    english_skeleton, english_numbers = _text_and_skeleton(english)
    hindi_skeleton, hindi_numbers = _text_and_skeleton(hindi)

    assert hindi_skeleton == english_skeleton
    assert hindi_numbers == english_numbers
    assert hindi["summary"] != english["summary"]


@pytest.mark.parametrize("key", sorted(plans_by_key()))
def test_the_plan_figures_can_be_worked_out_from_each_other(key: str) -> None:
    body = plans_by_key()[key]
    plan = body["plan"]
    budget = plan["monthly_budget"]
    costs = sum(line["amount"]["amount"] for line in budget["costs"])
    fund = plan["emergency_fund"]

    assert fund["target"]["amount"] == fund["months_of_costs"] * costs
    assert {s["amount"]["amount"] for s in plan["remittance"]["schedule"]} == {
        plan["remittance"]["monthly_amount"]["amount"]
    }
    goals = {line["id"]: line["amount"]["amount"] for line in budget["goals"]}
    assert goals["remittance"] == plan["remittance"]["monthly_amount"]["amount"]
    assert goals["emergency_fund"] == fund["monthly_saving"]["amount"]
    if plan["debt"]:
        assert goals["debt_payment"] == plan["debt"]["monthly_payment"]["amount"]
    else:
        assert "debt_payment" not in goals
    provider = plan["remittance"]["provider"]
    if provider:
        sent = plan["remittance"]["monthly_amount"]["amount"] - provider["fee"]["amount"]
        assert provider["receives"]["amount"] == pytest.approx(sent * provider["fx_rate"], abs=0.01)


def test_the_months_to_clear_the_debt_follow_the_interest_the_worker_stated() -> None:
    body = plans_by_key()["5a202702c922fc9b4fcf/en"]
    debt = body["plan"]["debt"]
    rate = body["slots"]["debt_interest"]["rate_percent"] / 100
    balance, months = debt["outstanding"]["amount"], 0
    while balance > 0:
        balance = balance * (1 + rate) - debt["monthly_payment"]["amount"]
        months += 1

    assert months == debt["months_to_clear"]


def test_a_plan_without_a_corridor_has_no_quote_and_one_without_debt_has_none() -> None:
    plan = plans_by_key()["e75fa9f24fd3159ad83d/en"]

    assert plan["corridor_id"] is None
    assert plan["plan"]["remittance"]["provider"] is None
    assert plan["plan"]["debt"] is None
    assert "debt_interest" not in plan["slots"]


# ---- the check-in -------------------------------------------------------------------------------


def test_the_check_in_mocks_are_the_same_plan_and_a_repeat_returns_the_first_answers() -> None:
    first = load(MOCKS / "checkin-01-answered.json")["body"]
    again = load(MOCKS / "checkin-02-already-answered.json")["body"]

    assert any(key.startswith(first["plan_id"]) for key in plans_by_key())
    assert first["already_answered"] is False and again["already_answered"] is True
    assert {**first, "already_answered": True} == again
