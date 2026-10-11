"""NF-HR-010: what a worker meets when Gemini's daily quota is spent, in both new features.

The real budget sits in front of the usual fakes (`GatedGemini`), so these tests show the
guard, the features' own fallbacks and the API's answer working together. The rules they hold:
a spent quota is a calm `503 ai_busy` that says when to come back, never a stack trace; the other
features and the other model tiers are not dragged down; nothing reaches Google once the
quota is gone; and what the worker already has (a stored check) is still served.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_coach_plans
from app.integrations.gemini import GeminiBudgetExhaustedError
from app.schemas.errors import ErrorEnvelope
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_plan_data import UID, WritingGemini, make_plans, reach_plan_stage
from tests.fixtures.coach_sessions import make_coach_app
from tests.fixtures.coach_turns import ScriptedStream, StubGemini, make_turn_app, make_turns
from tests.fixtures.fake_gemini import FakeGemini
from tests.fixtures.gated_gemini import Clock, GatedGemini, make_budget
from tests.fixtures.scam_app import make_app
from tests.fixtures.scam_classify import load_mock_body
from tests.fixtures.scam_explain import recordings_for

SCAM_URL = "/api/v2/scam/analyze"
SESSIONS = "/api/v2/coach/sessions"
FOURTEEN_HOURS = str(14 * 3600)  # to midnight Pacific from the fixtures' 10:00
MARICEL = next(p for p in load_personas().personas if p.id == "p01_sg_ph_maricel")


def _scam_body(text: str | None = None, **changes: Any) -> dict[str, Any]:
    text = text or load_mock_body("high")["redacted_text"]
    return {"text": text, "language": "hi", "corridor_id": "SG-IN"} | changes


def _closed(budget: Any, *tiers: str) -> None:
    """Google has answered a per-day 429 for these tiers' models."""
    for tier in tiers:
        asyncio.run(budget.mark_exhausted(tier))


def _spent(response: Any) -> ErrorEnvelope:
    assert response.status_code == 503, response.text
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.code == "ai_busy"
    assert response.headers["Retry-After"] == FOURTEEN_HOURS
    assert "today" in envelope.message  # not "in a minute": a spent day does not come back then
    assert "Traceback" not in response.text and "Exhausted" not in response.text
    return envelope


# --- Scam Analyzer -----------------------------------------------------------------------------


def test_scam_the_explainer_falls_back_a_tier_when_the_reasoning_model_is_spent() -> None:
    budget = make_budget()
    _closed(budget, "reasoning")
    gemini = GatedGemini(FakeGemini(recordings_for("high")), budget)

    with TestClient(make_app(gemini)) as client:  # type: ignore[arg-type]
        answer = client.post(SCAM_URL, json=_scam_body()).json()

    assert answer["verdict"] == load_mock_body("high")["verdict"]
    assert answer["explainer_status"] == "ready"
    explain = [c for c in gemini.calls if c["operation"] == "scam.explain"]
    assert [c["tier"].value for c in explain] == [
        "classification"
    ]  # reasoning never reached Google


def test_scam_a_features_share_of_the_reasoning_model_runs_out_before_the_models_day() -> None:
    budget = make_budget({"reasoning": 4})  # scam's share: 1 request
    gemini = GatedGemini(FakeGemini(recordings_for("high")), budget)
    first = _scam_body(load_mock_body("high")["redacted_text"])
    second = _scam_body("Send the processing fee today or lose the job")

    with TestClient(make_app(gemini)) as client:  # type: ignore[arg-type]
        answers = [client.post(SCAM_URL, json=body) for body in (first, second)]

    assert [a.status_code for a in answers] == [200, 200]
    assert [a.json()["explainer_status"] for a in answers] == ["ready", "ready"]
    tiers = [c["tier"].value for c in gemini.calls if c["operation"] == "scam.explain"]
    assert tiers == ["reasoning", "classification"]  # the second worker still got an explainer


def test_scam_with_the_classification_model_spent_the_check_is_a_calm_try_again_later() -> None:
    budget = make_budget()
    _closed(budget, "classification")
    gemini = GatedGemini(FakeGemini(recordings_for("high")), budget)

    with TestClient(make_app(gemini), raise_server_exceptions=False) as client:  # type: ignore[arg-type]
        response = client.post(SCAM_URL, json=_scam_body("a private message text"))

    _spent(response)
    assert "private message text" not in response.text
    assert gemini.calls == []  # nothing was sent to Google


def test_scam_a_message_checked_before_is_still_answered_when_every_model_is_spent() -> None:
    budget = make_budget()
    gemini = GatedGemini(FakeGemini(recordings_for("high")), budget)
    body = _scam_body()

    with TestClient(make_app(gemini), raise_server_exceptions=False) as client:  # type: ignore[arg-type]
        assert client.post(SCAM_URL, json=body).status_code == 200
        _closed(budget, "reasoning", "classification", "extraction", "embedding")
        again = client.post(SCAM_URL, json=body)

    assert again.status_code == 200 and again.json()["cached"] is True
    assert len(gemini.calls) == 2  # classify and explain, once; the repeat cost nothing


def test_scam_the_budget_of_another_feature_is_not_touched() -> None:
    budget = make_budget({"reasoning": 4})
    gemini = GatedGemini(FakeGemini(recordings_for("high")), budget)

    with TestClient(make_app(gemini)) as client:  # type: ignore[arg-type]
        client.post(SCAM_URL, json=_scam_body())
        client.post(SCAM_URL, json=_scam_body("Another message to check"))

    asyncio.run(budget.admit("coach", "reasoning"))  # coach's share (1) is still whole


# --- Financial Coach ---------------------------------------------------------------------------


def _turn_world(budget: Any) -> tuple[TestClient, StubGemini, str]:
    stub = StubGemini()
    turns, service, _, _ = make_turns(GatedGemini(stub, budget))  # type: ignore[arg-type]
    api = TestClient(make_turn_app(turns, service), raise_server_exceptions=False)
    session_id = str(api.post(SESSIONS, json={"language": "en"}).json()["id"])
    return api, stub, session_id


def _turn(api: TestClient, session_id: str, key: str, body: dict[str, Any]) -> Any:
    headers = {"Accept": "text/event-stream", "Idempotency-Key": key}
    return api.post(f"{SESSIONS}/{session_id}/messages", json=body, headers=headers)


def test_coach_a_spent_reply_model_ends_the_turn_calmly_and_the_session_stays_usable() -> None:
    clock = Clock()
    budget = make_budget(clock=clock)
    _closed(budget, "classification")
    api, stub, session_id = _turn_world(budget)
    key = "key-0123456789abcdef"

    _spent(_turn(api, session_id, key, {"language": "en"}))

    assert stub.calls == []
    assert api.get(f"{SESSIONS}/{session_id}").json()["messages"] == []
    # The quota day turns (00:00 Pacific is 08:00 UTC in November): the same key now works.
    clock.now = datetime(2026, 11, 13, 8, 30, tzinfo=UTC)
    assert _turn(api, session_id, key, {"language": "en"}).status_code == 200


def test_coach_the_coach_share_of_the_fast_model_ends_but_the_scam_share_is_untouched() -> None:
    budget = make_budget({"classification": 8})  # coach's share: 4 requests
    api, stub, session_id = _turn_world(budget)

    for number in range(4):
        stub.next_stream = ScriptedStream(["Thank you. ", "Next question."])
        body = {"language": "en"} if number == 0 else {"text": "Australia", "language": "en"}
        assert _turn(api, session_id, f"key-{number:016d}", body).status_code == 200
    refused = _turn(api, session_id, "key-0000000000000004", {"text": "Hello", "language": "en"})

    _spent(refused)
    assert len(stub.calls) == 4
    asyncio.run(budget.admit("scam", "classification"))  # scam still has its own share


def test_coach_with_the_reasoning_model_spent_the_plan_is_a_calm_try_later() -> None:
    clock = Clock()
    budget = make_budget(clock=clock)
    _closed(budget, "reasoning")
    writer = WritingGemini()
    plans, service, _, _, _ = make_plans(MARICEL, gemini=GatedGemini(writer, budget))  # type: ignore[arg-type]
    session_id = asyncio.run(reach_plan_stage(service, MARICEL))
    app = make_coach_app(service, uid=UID)
    app.dependency_overrides[get_coach_plans] = lambda: plans
    url = f"{SESSIONS}/{session_id}/plan"

    with TestClient(app, raise_server_exceptions=False) as client:
        _spent(client.post(url, json={"language": "en"}))
        assert writer.calls == []
        # Once the quota day turns the plan is made as a new one (201), so nothing was stored.
        clock.now = datetime(2026, 11, 13, 8, 30, tzinfo=UTC)
        assert client.post(url, json={"language": "en"}).status_code == 201


def test_the_error_the_worker_meets_is_a_gemini_rate_limit_so_every_fallback_applies() -> None:
    budget = make_budget({"reasoning": 4})
    asyncio.run(budget.admit("scam", "reasoning"))

    with pytest.raises(GeminiBudgetExhaustedError) as refused:
        asyncio.run(budget.admit("scam", "reasoning"))

    assert refused.value.daily is True
