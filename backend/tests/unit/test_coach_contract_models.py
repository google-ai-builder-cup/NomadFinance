"""The rules written into the Coach contract models, and the contract document itself.

The mocks (`test_coach_mocks.py`) prove the samples fit the models. These prove the models refuse
what the contract says they refuse, and that the document names every route, stream and code.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.coach_plan import CoachPlanResponse, slot_hash
from app.schemas.coach_profile import CoachProfile
from app.schemas.coach_session import (
    MAX_TRANSCRIPT_MESSAGES,
    CoachDoneEvent,
    CoachPlanRequest,
    CoachSession,
    CoachSessionCreateRequest,
    CoachSlotUpdateEvent,
    CoachTurnRequest,
)

REPO = Path(__file__).resolve().parents[3]
MOCKS = REPO / "docs" / "mocks" / "coach"
DOC = (REPO / "docs" / "api" / "v2-coach.md").read_text(encoding="utf-8")
MOCKS_README = (REPO / "docs" / "mocks" / "README.md").read_text(encoding="utf-8")


def _body(name: str) -> dict[str, Any]:
    body: dict[str, Any] = json.loads((MOCKS / name).read_text(encoding="utf-8"))["body"]
    return copy.deepcopy(body)


def _refused(model: Any, body: dict[str, Any], match: str, **changes: Any) -> None:
    """The body is valid; with the changes it is refused, for the reason named."""
    model.model_validate(body)
    with pytest.raises(ValidationError, match=match):
        model.model_validate({**body, **changes})


# ---- a session ---------------------------------------------------------------------------------


def test_next_slot_is_null_exactly_when_the_questions_are_done() -> None:
    review = _body("session-03-review.json")
    debt = _body("session-02-debt.json")

    _refused(CoachSession, review, "`next_slot` is null exactly", next_slot="savings")
    _refused(CoachSession, debt, "`next_slot` is null exactly", next_slot=None)


def test_the_score_appears_from_the_review_stage() -> None:
    score = _body("session-03-review.json")["score"]

    _refused(CoachSession, _body("session-02-debt.json"), "score appears from", score=score)
    assert CoachSession.model_validate(_body("session-03-review.json")).score is not None


def test_a_plan_id_and_the_completed_status_go_together() -> None:
    done = _body("session-07-completed.json")
    open_one = _body("session-04-plan-mid.json")

    _refused(CoachSession, done, "`plan_id` is set exactly", plan_id=None)
    _refused(CoachSession, open_one, "`plan_id` is set exactly", plan_id=done["plan_id"])
    _refused(CoachSession, done, "at the `plan` stage", stage="review", next_slot=None)


def test_a_slot_must_be_one_of_the_eleven_with_a_value_that_fits() -> None:
    body = _body("session-03-review.json")

    bad_name = copy.deepcopy(body)
    bad_name["slots"]["favourite_colour"] = {"value": "red", "confirmed": True, "source": "user"}
    bad_value = copy.deepcopy(body)
    bad_value["slots"]["dependents"]["value"] = 21

    _refused(CoachSession, body, "favourite_colour", slots=bad_name["slots"])
    _refused(CoachSession, body, "dependents", slots=bad_value["slots"])


def test_a_transcript_has_at_most_200_messages() -> None:
    body = _body("session-02-debt.json")
    message = body["messages"][0]

    CoachSession.model_validate({**body, "messages": [message] * MAX_TRANSCRIPT_MESSAGES})
    _refused(CoachSession, body, "at most 200", messages=[message] * (MAX_TRANSCRIPT_MESSAGES + 1))


# ---- the requests and the stream's data ---------------------------------------------------------


def test_a_turn_may_leave_out_the_text_and_never_cuts_it() -> None:
    assert CoachTurnRequest(language="en").text is None
    assert CoachTurnRequest(text=None, language="en").text is None
    assert CoachTurnRequest(text="  Australia  ", language="en").text == "Australia"
    assert CoachTurnRequest(text="x" * 1000, language="en").text == "x" * 1000
    for text in ("", "   ", "x" * 1001):
        with pytest.raises(ValidationError):
            CoachTurnRequest(text=text, language="en")


def test_a_language_outside_the_six_is_refused_everywhere() -> None:
    for model, body in (
        (CoachTurnRequest, {"text": "hi"}),
        (CoachSessionCreateRequest, {}),
        (CoachPlanRequest, {}),
    ):
        _refused(model, {**body, "language": "en"}, "language", language="fr")
        model.model_validate({**body, "language": "ne"})


def test_a_new_session_does_not_restart_unless_asked() -> None:
    assert CoachSessionCreateRequest(language="hi").restart is False
    assert CoachSessionCreateRequest(language="hi", restart=True).restart is True


def test_a_slot_update_must_fit_its_slot_and_a_done_event_its_stage() -> None:
    CoachSlotUpdateEvent(slot="dependents", value=3, confirmed=True)
    with pytest.raises(ValidationError):
        CoachSlotUpdateEvent(slot="monthly_salary", value={"amount": -1}, confirmed=True)
    with pytest.raises(ValidationError):
        CoachDoneEvent(message_id="m_1", stage="review", next_slot="savings", turn_count=3)
    with pytest.raises(ValidationError):
        CoachDoneEvent(message_id="m_1", stage="debt", next_slot=None, turn_count=3)


# ---- a plan -------------------------------------------------------------------------------------


def _plan() -> dict[str, Any]:
    return _body("plan-get-01-english.json")


def _plan_refused(match: str, change: Callable[[dict[str, Any]], None]) -> None:
    """The sample plan is valid, and valid no longer after `change`, for the reason named."""
    CoachPlanResponse.model_validate(_plan())
    body = _plan()
    change(body)
    with pytest.raises(ValidationError, match=match):
        CoachPlanResponse.model_validate(body)


def test_a_plan_has_thirteen_weeks_in_order() -> None:
    def drop_one(body: dict[str, Any]) -> None:
        body["plan"]["weeks"] = body["plan"]["weeks"][:12]

    def swap_two(body: dict[str, Any]) -> None:
        weeks = body["plan"]["weeks"]
        weeks[0], weeks[1] = weeks[1], weeks[0]

    _plan_refused("at least 13", drop_one)
    _plan_refused("weeks 1 to 13, in order", swap_two)


def test_the_budget_must_add_up_and_stay_in_one_currency() -> None:
    def add_one(body: dict[str, Any]) -> None:
        body["plan"]["monthly_budget"]["left_over"]["amount"] += 1

    def other_currency(body: dict[str, Any]) -> None:
        body["plan"]["monthly_budget"]["costs"][0]["amount"]["currency"] = "SGD"

    _plan_refused("`left_over` is income minus", add_one)
    _plan_refused("one currency", other_currency)


def test_every_figure_is_in_the_hosts_currency_except_what_arrives_at_home() -> None:
    def fund_in_rupees(body: dict[str, Any]) -> None:
        body["plan"]["emergency_fund"]["target"]["currency"] = "INR"

    def wrong_reporting_currency(body: dict[str, Any]) -> None:
        body["reporting_currency"] = "SGD"

    _plan_refused("reporting currency", fund_in_rupees)
    _plan_refused("host country's currency", wrong_reporting_currency)
    assert _plan()["plan"]["remittance"]["provider"]["receives"]["currency"] == "INR"


def test_the_id_is_the_start_of_the_hash_of_the_answers() -> None:
    def one_more_dependent(body: dict[str, Any]) -> None:
        body["slots"]["dependents"] = 4

    _plan_refused("start of the slot hash", one_more_dependent)


def test_a_quote_needs_a_corridor_and_the_corridor_needs_the_host_country() -> None:
    def quote_without_corridor(body: dict[str, Any]) -> None:
        body["corridor_id"] = None
        body["plan"]["remittance"]["corridor_id"] = None

    def corridor_of_another_host(body: dict[str, Any]) -> None:
        body["corridor_id"] = "SG-IN"
        body["plan"]["remittance"]["corridor_id"] = "SG-IN"

    _plan_refused("only for one of the six corridors", quote_without_corridor)
    _plan_refused("host country and the home country", corridor_of_another_host)


def test_the_remittance_plan_is_for_the_plans_corridor_and_its_schedule_is_in_order() -> None:
    def other_corridor(body: dict[str, Any]) -> None:
        body["plan"]["remittance"]["corridor_id"] = "AU-PH"

    def sends_out_of_order(body: dict[str, Any]) -> None:
        sends = body["plan"]["remittance"]["schedule"]
        sends[0], sends[1] = sends[1], sends[0]

    _plan_refused("for the plan's corridor", other_corridor)
    _plan_refused("in order of week", sends_out_of_order)


def test_english_is_always_stored_and_so_is_the_language_shown() -> None:
    def only_hindi(body: dict[str, Any]) -> None:
        body["available_languages"] = ["hi"]

    def shown_but_not_stored(body: dict[str, Any]) -> None:
        body["language"] = "hi"
        body["available_languages"] = ["en"]

    _plan_refused("`available_languages` has `en`", only_hindi)
    _plan_refused("`available_languages` has `en`", shown_but_not_stored)


def test_the_score_has_the_five_factors_once() -> None:
    def twice_the_first(body: dict[str, Any]) -> None:
        body["score"]["factors"][1] = body["score"]["factors"][0]

    def only_four(body: dict[str, Any]) -> None:
        body["score"]["factors"] = body["score"]["factors"][:4]

    _plan_refused("five factors exactly once", twice_the_first)
    _plan_refused("at least 5", only_four)


def test_the_hash_of_the_answers_ignores_order_and_changes_with_a_value() -> None:
    slots = _plan()["slots"]
    shuffled = dict(reversed(list(slots.items())))
    changed = {**slots, "dependents": 4}

    first = slot_hash(CoachProfile.model_validate(slots))

    assert first == slot_hash(CoachProfile.model_validate(shuffled))
    assert first != slot_hash(CoachProfile.model_validate(changed))
    # A fixed value, so a change to how the hash is written (and every stored plan id) is noticed.
    assert first.startswith("5a202702c922fc9b4fcf")


# ---- the document -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "route",
    [
        "POST /api/v2/coach/sessions",
        "GET /api/v2/coach/sessions/{id}",
        "POST /api/v2/coach/sessions/{id}/messages",
        "POST /api/v2/coach/sessions/{id}/plan",
        "GET /api/v2/coach/plans/{id}",
        "GET /api/v2/coach/plans/{id}.pdf",
        "GET /api/v2/coach/overview",
    ],
)
def test_the_document_has_a_section_for_each_route(route: str) -> None:
    assert f"`{route}`" in DOC


@pytest.mark.parametrize(
    "code", ["session_not_active", "session_full", "turn_in_progress", "plan_not_ready"]
)
def test_the_document_names_each_code_it_adds(code: str) -> None:
    assert f"`{code}`" in DOC


@pytest.mark.parametrize("path", sorted(MOCKS.glob("*.sse")), ids=lambda path: path.name)
def test_each_stream_is_described_in_both_documents(path: Path) -> None:
    assert path.name in DOC
    assert path.name in MOCKS_README
