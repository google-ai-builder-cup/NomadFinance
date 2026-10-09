"""NF-FC-012 through the API: make the plan, read it, and every refusal."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient

from app.dependencies import get_coach_plans
from app.integrations.gemini import GeminiTimeoutError
from app.schemas.coach_plan import CoachPlanResponse
from app.schemas.errors import ErrorEnvelope
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_plan_data import (
    UID,
    TranslatingGemini,
    WritingGemini,
    make_plans,
    reach_plan_stage,
)
from tests.fixtures.coach_sessions import NOW, make_coach_app

MARICEL = next(p for p in load_personas().personas if p.id == "p01_sg_ph_maricel")


class World:
    def __init__(
        self,
        *,
        gemini: WritingGemini | None = None,
        rates: dict | None = None,  # type: ignore[type-arg]
        translator: TranslatingGemini | None = None,
    ) -> None:
        self.translator = translator or TranslatingGemini()
        self.plans, self.service, self.sessions, self.store, self.gemini = make_plans(
            MARICEL, gemini=gemini, rates=rates, translator=self.translator
        )
        self.session_id = asyncio.run(reach_plan_stage(self.service, MARICEL))

    def client(self, **options: Any) -> TestClient:
        app = make_coach_app(self.service, uid=UID, **options)
        app.dependency_overrides[get_coach_plans] = lambda: self.plans
        return TestClient(app, raise_server_exceptions=False)

    @property
    def url(self) -> str:
        return f"/api/v2/coach/sessions/{self.session_id}/plan"


def _error(response: Any, status: int, code: str) -> ErrorEnvelope:
    assert response.status_code == status, response.text
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.code == code and envelope.request_id == response.headers["X-Request-ID"]
    return envelope


def test_a_new_plan_is_201_and_the_contracts_response() -> None:
    world = World()
    api = world.client()

    response = api.post(world.url, json={"language": "en"})

    assert response.status_code == 201, response.text
    body = CoachPlanResponse.model_validate(response.json())
    assert body.score.total == 22 and len(body.plan.weeks) == 13
    assert body.plan.remittance.provider is not None


def test_asking_again_is_200_with_the_same_plan() -> None:
    world = World()
    api = world.client()
    first = api.post(world.url, json={"language": "en"}).json()

    again = api.post(world.url, json={"language": "en"})

    assert again.status_code == 200 and again.json()["id"] == first["id"]
    assert again.json()["plan"] == first["plan"] and len(world.gemini.calls) == 1


def test_a_plan_is_read_by_its_id_in_english_and_in_another_language() -> None:
    world = World()
    api = world.client()
    plan_id = api.post(world.url, json={"language": "hi"}).json()["id"]

    hindi = api.get(f"/api/v2/coach/plans/{plan_id}", params={"language": "hi"})
    bengali = api.get(f"/api/v2/coach/plans/{plan_id}", params={"language": "bn"})
    english = api.get(f"/api/v2/coach/plans/{plan_id}")

    assert english.status_code == 200 and CoachPlanResponse.model_validate(english.json())
    assert english.json()["language"] == "en" and english.json()["available_languages"] == [
        "en",
        "bn",
        "hi",
    ]
    assert hindi.json()["language"] == "hi" and hindi.json()["plan"]["summary"].startswith(
        "[Hindi]"
    )
    assert bengali.json()["language"] == "bn"
    assert len(world.translator.calls) == 2  # Hindi was made with the plan, Bengali on request
    figures = {k: english.json()["plan"][k] for k in ("monthly_budget", "remittance", "debt")}
    assert figures == {k: hindi.json()["plan"][k] for k in figures}


def test_the_pdf_is_the_file_through_the_api_with_its_headers(monkeypatch: Any) -> None:
    from app.services.coach import plan_files

    monkeypatch.setattr(plan_files, "render_plan_pdf", lambda r: b"%PDF-1.7 " + r.language.encode())
    world = World()
    api = world.client()
    plan_id = api.post(world.url, json={"language": "en"}).json()["id"]

    english = api.get(f"/api/v2/coach/plans/{plan_id}.pdf")
    tagalog = api.get(f"/api/v2/coach/plans/{plan_id}.pdf", params={"language": "tl"})

    assert english.status_code == 200 and english.content == b"%PDF-1.7 en"
    assert english.headers["content-type"] == "application/pdf"
    assert (
        english.headers["content-disposition"] == 'attachment; filename="nomadfinance-plan-en.pdf"'
    )
    assert english.headers["cache-control"] == "private, no-store"
    assert (
        tagalog.content == b"%PDF-1.7 tl"
        and "plan-tl.pdf" in tagalog.headers["content-disposition"]
    )
    assert len(world.translator.calls) == 1


def test_the_pdf_route_does_not_swallow_the_plan_route_or_the_other_way_round() -> None:
    world = World()
    api = world.client()
    plan_id = api.post(world.url, json={"language": "en"}).json()["id"]

    assert api.get(f"/api/v2/coach/plans/{plan_id}").headers["content-type"] == "application/json"
    _error(api.get("/api/v2/coach/plans/not-an-id.pdf"), 404, "not_found")
    _error(api.get("/api/v2/coach/plans/" + "0" * 20 + ".pdf"), 404, "not_found")
    _error(
        api.get(f"/api/v2/coach/plans/{plan_id}.pdf", params={"language": "xx"}),
        422,
        "validation_failed",
    )


def test_a_translation_that_fails_is_a_json_error_and_stores_nothing() -> None:
    from app.integrations.gemini import GeminiTimeoutError
    from tests.fixtures.coach_plan_data import TranslatingGemini

    world = World(
        translator=TranslatingGemini(GeminiTimeoutError("slow"), GeminiTimeoutError("slow"))
    )
    api = world.client()
    plan_id = api.post(world.url, json={"language": "en"}).json()["id"]

    _error(api.get(f"/api/v2/coach/plans/{plan_id}", params={"language": "hi"}), 504, "ai_timeout")
    _error(
        api.get(f"/api/v2/coach/plans/{plan_id}.pdf", params={"language": "hi"}), 504, "ai_timeout"
    )
    assert api.get(f"/api/v2/coach/plans/{plan_id}", params={"language": "hi"}).status_code == 200


def test_the_pdf_and_translations_are_the_workers_own_and_behind_the_flag() -> None:
    world = World()
    plan_id = world.client().post(world.url, json={"language": "en"}).json()["id"]
    stranger = TestClient(_app_for(world, "stranger"), raise_server_exceptions=False)

    _error(stranger.get(f"/api/v2/coach/plans/{plan_id}.pdf"), 404, "not_found")
    _error(world.client(flag_on=False).get(f"/api/v2/coach/plans/{plan_id}.pdf"), 404, "not_found")
    assert (
        world.client(signed_in=False).get(f"/api/v2/coach/plans/{plan_id}.pdf").status_code == 401
    )


def test_the_refusals() -> None:
    world = World()
    api = world.client()

    _error(api.post(world.url, json={"language": "xx"}), 422, "validation_failed")
    _error(api.post("/api/v2/coach/sessions/nope/plan", json={"language": "en"}), 404, "not_found")
    _error(
        api.post("/api/v2/coach/sessions/bad id!/plan", json={"language": "en"}), 404, "not_found"
    )
    _error(api.get("/api/v2/coach/plans/" + "0" * 20), 404, "not_found")
    _error(api.get("/api/v2/coach/plans/not-an-id"), 404, "not_found")
    _error(
        api.get("/api/v2/coach/plans/" + "0" * 20, params={"language": "xx"}),
        422,
        "validation_failed",
    )


def test_not_confirmed_is_409_plan_not_ready() -> None:
    world = World()
    started = asyncio.run(world.service.start("someone", "en", restart=False, now=NOW))
    api = TestClient(_app_for(world, "someone"), raise_server_exceptions=False)

    _error(
        api.post(f"/api/v2/coach/sessions/{started.session.id}/plan", json={"language": "en"}),
        409,
        "plan_not_ready",
    )


def _app_for(world: World, uid: str) -> Any:
    app = make_coach_app(world.service, uid=uid)
    app.dependency_overrides[get_coach_plans] = lambda: world.plans
    return app


def test_a_running_plan_is_409_with_retry_after() -> None:
    world = World()
    world.sessions.docs[(UID, world.session_id)]["plan_lock"] = {
        "hash": "x",
        "started_at": NOW.replace(year=2100),
    }

    response = world.client().post(world.url, json={"language": "en"})

    _error(response, 409, "request_in_progress")
    assert response.headers["Retry-After"] == "5"


def test_a_missing_rate_is_503_score_unavailable_with_retry_after() -> None:
    world = World(rates={})

    response = world.client().post(world.url, json={"language": "en"})

    _error(response, 503, "score_unavailable")
    assert response.headers["Retry-After"] == "30"
    assert world.gemini.calls == []


def test_gemini_failures_keep_their_codes() -> None:
    world = World(gemini=WritingGemini(GeminiTimeoutError("slow")))

    _error(world.client().post(world.url, json={"language": "en"}), 504, "ai_timeout")


def test_unusable_sentences_twice_are_502_and_nothing_is_stored() -> None:
    def invented(contents: str) -> Any:
        from tests.fixtures.coach_plan_data import compliant_text

        return compliant_text(contents).model_copy(update={"summary": "You will earn 99,999 SGD."})

    world = World(gemini=WritingGemini(invented, invented))

    _error(world.client().post(world.url, json={"language": "en"}), 502, "ai_bad_response")
    assert world.store.plans == {}


def test_the_flag_and_the_token_guard_both_routes() -> None:
    world = World()

    off = world.client(flag_on=False)
    _error(off.post(world.url, json={"language": "en"}), 404, "not_found")
    _error(off.get("/api/v2/coach/plans/" + "0" * 20), 404, "not_found")
    out = world.client(signed_in=False)
    assert out.post(world.url, json={"language": "en"}).status_code == 401
    assert out.get("/api/v2/coach/plans/" + "0" * 20).status_code == 401


def test_another_workers_session_and_plan_are_not_found() -> None:
    world = World()
    plan_id = world.client().post(world.url, json={"language": "en"}).json()["id"]
    stranger = TestClient(_app_for(world, "stranger"), raise_server_exceptions=False)

    _error(stranger.post(world.url, json={"language": "en"}), 404, "not_found")
    _error(stranger.get(f"/api/v2/coach/plans/{plan_id}"), 404, "not_found")
