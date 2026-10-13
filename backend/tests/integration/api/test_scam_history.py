"""NF-SA-012 through the API: the stored check, the cache, the hourly budget, history and detail."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.schemas.scam import ScamAnalyzeResponse, ScamCheckDetail, ScamCheckListResponse
from tests.fixtures.fake_gemini import FakeGemini
from tests.fixtures.scam_app import assert_envelope, make_app
from tests.fixtures.scam_checks import FakeCheckRepo, FakeIndicatorRepo, make_store
from tests.fixtures.scam_classify import load_mock_body
from tests.fixtures.scam_explain import recordings_for
from tests.fixtures.scam_images import chat_screenshot

ANALYZE = "/api/v2/scam/analyze"
CHECKS = "/api/v2/scam/checks"
UID = "test-user"


class Setup:
    """An app with its fake Gemini and storage in reach, and clients for one or two workers."""

    def __init__(self, case: str = "high", **gemini_overrides: Any) -> None:
        recordings = recordings_for(case) | gemini_overrides
        self.gemini = FakeGemini(recordings)
        self.repo = FakeCheckRepo()
        self.indicators = FakeIndicatorRepo()
        self.store = make_store(self.repo, self.indicators)

    def client(self, uid: str = UID, **options: Any) -> TestClient:
        app = make_app(self.gemini, store=self.store, uid=uid, **options)
        return TestClient(app, raise_server_exceptions=False)


def _body(text: str = "Pay the fee today", **changes: Any) -> dict[str, Any]:
    return {"text": text, "language": "hi", "corridor_id": "SG-IN"} | changes


@pytest.fixture
def world() -> Setup:
    return Setup()


# --- the cache ---------------------------------------------------------------------------------


def test_the_first_check_is_stored_and_the_answer_names_it(world: Setup) -> None:
    with world.client() as api:
        answer = api.post(ANALYZE, json=_body()).json()

    assert answer["cached"] is False
    stored = world.repo.mine(UID)
    assert len(stored) == 1
    assert answer["id"] == stored[0]["cache_key"][:32]
    assert stored[0]["check_count"] == 1


def test_a_repeated_message_is_answered_from_storage_with_no_gemini_call(world: Setup) -> None:
    with world.client() as api:
        first = api.post(ANALYZE, json=_body()).json()
        calls = len(world.gemini.calls)
        second = api.post(ANALYZE, json=_body()).json()

    assert len(world.gemini.calls) == calls, "a repeat must not call Gemini at all"
    assert second["cached"] is True and second["id"] == first["id"]
    ScamAnalyzeResponse.model_validate(second)
    assert {k: v for k, v in second.items() if k not in {"cached", "expires_at"}} == {
        k: v for k, v in first.items() if k not in {"cached", "expires_at"}
    }
    stored = world.repo.mine(UID)
    assert len(stored) == 1 and stored[0]["check_count"] == 2


def test_a_repeat_with_different_spacing_or_case_is_still_the_same_message(world: Setup) -> None:
    with world.client() as api:
        api.post(ANALYZE, json=_body("Pay the fee today"))
        calls = len(world.gemini.calls)
        again = api.post(ANALYZE, json=_body("  PAY   the fee\ttoday "))

    assert again.json()["cached"] is True
    assert len(world.gemini.calls) == calls


def test_the_same_message_in_another_language_is_a_new_check(world: Setup) -> None:
    with world.client() as api:
        first = api.post(ANALYZE, json=_body(language="hi")).json()
        second = api.post(ANALYZE, json=_body(language="en")).json()

    assert second["cached"] is False and second["id"] != first["id"]
    assert len(world.repo.mine(UID)) == 2


def test_the_same_message_after_a_change_of_route_is_checked_again_for_the_new_route(
    world: Setup,
) -> None:
    with world.client() as api:
        first = api.post(ANALYZE, json=_body(corridor_id="SG-IN")).json()
        calls = len(world.gemini.calls)
        second = api.post(ANALYZE, json=_body(corridor_id="SG-PH")).json()

    assert first["corridor_id"] == "SG-IN"
    assert second["cached"] is False and second["corridor_id"] == "SG-PH"
    assert len(world.gemini.calls) > calls
    # Still one stored check for the message: the newer one replaces it.
    stored = world.repo.mine(UID)
    assert len(stored) == 1 and stored[0]["corridor_id"] == "SG-PH"


def test_a_repeat_on_the_same_route_is_still_served_from_storage(world: Setup) -> None:
    with world.client() as api:
        api.post(ANALYZE, json=_body(corridor_id="SG-IN"))
        calls = len(world.gemini.calls)
        again = api.post(ANALYZE, json=_body(corridor_id="SG-IN")).json()

    assert again["cached"] is True and len(world.gemini.calls) == calls


def test_another_workers_check_is_never_served_to_this_one(world: Setup) -> None:
    with world.client("worker-a") as api:
        api.post(ANALYZE, json=_body())
        calls = len(world.gemini.calls)
    with world.client("worker-b") as api:
        answer = api.post(ANALYZE, json=_body()).json()

    assert answer["cached"] is False and len(world.gemini.calls) > calls
    assert len(world.repo.mine("worker-a")) == len(world.repo.mine("worker-b")) == 1


def test_a_check_without_an_explainer_is_not_served_so_the_next_try_makes_one() -> None:
    world = Setup(**{"scam.explain": {"kind": "structured", "error": "GeminiUnavailableError"}})
    with world.client() as api:
        first = api.post(ANALYZE, json=_body()).json()
        assert first["explainer_status"] == "unavailable"
        world.gemini._recordings["scam.explain"] = recordings_for("high")["scam.explain"]
        second = api.post(ANALYZE, json=_body()).json()

    assert second["cached"] is False and second["explainer_status"] == "ready"
    stored = world.repo.mine(UID)
    assert len(stored) == 1 and stored[0]["explainer"] is not None
    assert stored[0]["check_count"] == 2


def test_an_older_prompt_version_is_recomputed_but_keeps_the_report(world: Setup) -> None:
    with world.client() as api:
        first = api.post(ANALYZE, json=_body()).json()
        stored = world.repo.docs[(UID, first["id"])]
        stored["prompt_versions"] = {"scam.classify": 1, "scam.explain": 1}
        stored["reported_report_id"] = "r_42"
        calls = len(world.gemini.calls)
        second = api.post(ANALYZE, json=_body()).json()

    assert second["cached"] is False and len(world.gemini.calls) > calls
    assert second["reported"] is True and second["report_id"] == "r_42"
    assert world.repo.docs[(UID, first["id"])]["reported_report_id"] == "r_42"


def test_a_changed_taxonomy_is_recomputed(world: Setup) -> None:
    with world.client() as api:
        first = api.post(ANALYZE, json=_body()).json()
        world.repo.docs[(UID, first["id"])]["taxonomy_version"] = 99
        second = api.post(ANALYZE, json=_body()).json()

    assert second["cached"] is False


def test_a_failed_check_stores_nothing() -> None:
    world = Setup(**{"scam.classify": {"kind": "structured", "error": "GeminiUnavailableError"}})
    with world.client() as api:
        response = api.post(ANALYZE, json=_body())

    assert_envelope(response, 503, "ai_unavailable")
    assert world.repo.mine(UID) == []


def test_a_storage_outage_does_not_fail_the_check(world: Setup) -> None:
    world.repo.down = True
    with world.client() as api:
        response = api.post(ANALYZE, json=_body())

    assert response.status_code == 200 and response.json()["cached"] is False
    assert world.repo.saves == 0


# --- the hourly budget -------------------------------------------------------------------------


def test_the_21st_new_message_in_an_hour_is_refused_in_the_envelope(world: Setup) -> None:
    with world.client() as api:
        statuses = [
            api.post(ANALYZE, json=_body(f"Pay fee {i} today")).status_code for i in range(20)
        ]
        refused = api.post(ANALYZE, json=_body("Pay fee 21 today"))

    assert statuses == [200] * 20
    envelope = assert_envelope(refused, 429, "rate_limited")
    assert "hour" in envelope.message
    assert refused.headers["X-RateLimit-Limit"] == "20"
    assert refused.headers["X-RateLimit-Remaining"] == "0"
    assert int(refused.headers["Retry-After"]) > 0
    assert refused.headers["Retry-After"] == refused.headers["X-RateLimit-Reset"]
    assert len(world.repo.mine(UID)) == 20, "a refused message is not stored"


def test_a_repeat_costs_nothing_even_when_the_budget_is_gone(world: Setup) -> None:
    with world.client() as api:
        for i in range(20):
            api.post(ANALYZE, json=_body(f"Pay fee {i} today"))
        refused = api.post(ANALYZE, json=_body("A brand new message"))
        calls = len(world.gemini.calls)
        repeat = api.post(ANALYZE, json=_body("Pay fee 3 today"))

    assert refused.status_code == 429
    assert repeat.status_code == 200 and repeat.json()["cached"] is True
    assert len(world.gemini.calls) == calls


def test_a_hit_does_not_use_the_budget(world: Setup) -> None:
    with world.client() as api:
        api.post(ANALYZE, json=_body("Pay fee 0 today"))
        for _ in range(30):
            assert api.post(ANALYZE, json=_body("Pay fee 0 today")).status_code == 200
        # 19 more new messages still fit: the 30 repeats used nothing.
        statuses = [api.post(ANALYZE, json=_body(f"New {i}")).status_code for i in range(19)]

    assert statuses == [200] * 19


def test_the_budget_is_per_worker(world: Setup) -> None:
    with world.client("worker-a") as api:
        for i in range(20):
            api.post(ANALYZE, json=_body(f"Pay fee {i} today"))
        assert api.post(ANALYZE, json=_body("One more")).status_code == 429
    with world.client("worker-b") as api:
        assert api.post(ANALYZE, json=_body("One more")).status_code == 200


def test_the_old_per_minute_ai_limit_no_longer_applies_to_the_first_20(world: Setup) -> None:
    # 11 new messages in a minute used to be refused (10 a minute); the contract allows 20 an hour.
    with world.client() as api:
        statuses = [
            api.post(ANALYZE, json=_body(f"Pay fee {i} today")).status_code for i in range(11)
        ]

    assert statuses == [200] * 11


# --- what is stored ----------------------------------------------------------------------------

PHONE, ACCOUNT, EMAIL, LINK = (
    "+65 9123 4567",
    "123456789012",
    "a.b@example.org",
    "https://bit.ly/x9",
)
RAW_MESSAGE = (
    f"Pay the fee to account {ACCOUNT} today, call {PHONE}, mail {EMAIL} or open {LINK} now"
)


def test_the_stored_check_holds_no_raw_message_and_no_identifier_outside_the_indicators(
    world: Setup,
) -> None:
    with world.client() as api:
        answer = api.post(ANALYZE, json=_body(RAW_MESSAGE)).json()

    document = world.repo.docs[(UID, answer["id"])]
    assert "text" not in document
    everything_but_indicators = json.dumps(
        {k: v for k, v in document.items() if k != "indicators"}, default=str
    )
    for raw in (RAW_MESSAGE, PHONE, "9123", ACCOUNT, EMAIL, "bit.ly", LINK):
        assert raw not in everything_but_indicators, raw
    assert "[PHONE]" in document["redacted_text"] and "[ACCOUNT]" in document["redacted_text"]


def test_the_indicator_values_are_stored_as_the_data_model_allows(world: Setup) -> None:
    # Decision 2 of NF-F0-003: the scam's own contact points are kept, owner-only for 90 days.
    with world.client() as api:
        answer = api.post(ANALYZE, json=_body(RAW_MESSAGE)).json()

    stored = world.repo.docs[(UID, answer["id"])]["indicators"]
    assert {i["kind"] for i in stored} >= {"phone", "email", "url"}
    assert all(set(i) <= {"id", "kind", "value", "flags", "imitates"} for i in stored)


def test_a_screenshot_check_stores_the_text_read_and_never_the_image() -> None:
    reading = {
        "kind": "structured",
        "response": {
            "is_message": True,
            "message_text": f"Pay the fee to {ACCOUNT} today",
            "sender": "+65 9000 0001",
        },
    }
    world = Setup(**{"scam.read_screenshot": reading})
    image = chat_screenshot()
    with world.client() as api:
        response = api.post(
            ANALYZE,
            files={"image": ("shot.png", image, "image/png")},
            data={"language": "hi", "corridor_id": "SG-IN"},
        )

    assert response.status_code == 200
    document = world.repo.docs[(UID, response.json()["id"])]
    assert document["input_type"] == "screenshot" and "vision" in document["models"]
    rest = {k: v for k, v in document.items() if k != "indicators"}
    assert ACCOUNT not in json.dumps(rest, default=str)
    blob = json.dumps(document, default=str)
    assert "image" not in document and len(blob) < len(image)


def test_nothing_of_the_message_is_logged_on_a_hit_or_a_miss(
    world: Setup, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("DEBUG")
    with world.client() as api:
        api.post(ANALYZE, json=_body(RAW_MESSAGE))
        api.post(ANALYZE, json=_body(RAW_MESSAGE))

    for raw in (PHONE, "9123", ACCOUNT, EMAIL, "bit.ly"):
        assert raw not in caplog.text, raw
    assert "scam_cache result=miss" in caplog.text and "scam_cache result=hit" in caplog.text
    # The same two answers on the line the dashboard's hit-rate chart reads (NF-HR-010).
    assert "cache_lookup feature=scam name=check result=miss" in caplog.text
    assert "cache_lookup feature=scam name=check result=hit" in caplog.text


# --- history and detail ------------------------------------------------------------------------


def _make_history(world: Setup, n: int) -> list[str]:
    with world.client() as api:
        return [
            api.post(ANALYZE, json=_body(f"Pay the processing fee {i} today")).json()["id"]
            for i in range(n)
        ]


def test_the_history_lists_the_workers_checks_newest_first(world: Setup) -> None:
    ids = _make_history(world, 3)
    with world.client() as api:
        response = api.get(CHECKS)

    page = ScamCheckListResponse.model_validate(response.json())
    assert [item.id for item in page.items] == list(reversed(ids))
    assert page.next_cursor is None


def test_the_history_pages_with_a_cursor_and_no_repeats(world: Setup) -> None:
    ids = _make_history(world, 5)
    seen: list[str] = []
    cursor = None
    with world.client() as api:
        for _ in range(5):
            params: dict[str, Any] = {"limit": 2} | ({"cursor": cursor} if cursor else {})
            page = api.get(CHECKS, params=params).json()
            seen += [item["id"] for item in page["items"]]
            cursor = page["next_cursor"]
            if cursor is None:
                break

    assert seen == list(reversed(ids))


def test_another_workers_history_is_not_visible(world: Setup) -> None:
    _make_history(world, 2)
    with world.client("worker-b") as api:
        page = api.get(CHECKS).json()

    assert page == {"items": [], "next_cursor": None}


@pytest.mark.parametrize("limit", ["0", "101", "-1", "abc"])
def test_a_limit_outside_1_to_100_is_a_validation_error(world: Setup, limit: str) -> None:
    with world.client() as api:
        response = api.get(CHECKS, params={"limit": limit})

    assert_envelope(response, 422, "validation_failed")


def test_a_bad_cursor_is_invalid_cursor(world: Setup) -> None:
    with world.client() as api:
        response = api.get(CHECKS, params={"cursor": "not-a-cursor"})

    assert_envelope(response, 400, "invalid_cursor")


def test_a_cursor_issued_to_someone_else_is_invalid_cursor(world: Setup) -> None:
    _make_history(world, 3)
    with world.client("worker-b") as other:
        _ = other.get(CHECKS)
    with world.client() as api:
        cursor = api.get(CHECKS, params={"limit": 1}).json()["next_cursor"]
    with world.client("worker-b") as other:
        response = other.get(CHECKS, params={"cursor": cursor})

    assert_envelope(response, 400, "invalid_cursor")


def test_the_detail_is_the_analyze_answer_without_cached(world: Setup) -> None:
    with world.client() as api:
        answer = api.post(ANALYZE, json=_body(load_mock_body("high")["redacted_text"])).json()
        detail = api.get(f"{CHECKS}/{answer['id']}")

    assert detail.status_code == 200
    check = ScamCheckDetail.model_validate(detail.json())
    assert "cached" not in detail.json()
    assert check.model_dump(mode="json") == {k: v for k, v in answer.items() if k not in {"cached"}}


@pytest.mark.parametrize("check_id", ["0" * 32, "..", "a" * 200, "has space"])
def test_an_unknown_check_is_not_found(world: Setup, check_id: str) -> None:
    with world.client() as api:
        response = api.get(f"{CHECKS}/{check_id}")

    assert_envelope(response, 404, "not_found")


def test_someone_elses_check_is_exactly_as_not_found_as_one_that_does_not_exist(
    world: Setup,
) -> None:
    [check_id] = _make_history(world, 1)
    with world.client("worker-b") as stranger:
        theirs = stranger.get(f"{CHECKS}/{check_id}")
        nothing = stranger.get(f"{CHECKS}/{'0' * 32}")

    assert theirs.status_code == nothing.status_code == 404
    assert theirs.json()["code"] == nothing.json()["code"]
    assert theirs.json()["message"] == nothing.json()["message"]


def test_seen_is_read_live_when_the_check_is_shown(world: Setup) -> None:
    from app.schemas.scam import ScamIndicator
    from app.services.scam.indicator_seen import indicator_doc_id

    with world.client() as api:
        answer = api.post(ANALYZE, json=_body(RAW_MESSAGE)).json()
        phone = next(i for i in answer["indicators"] if i["kind"] == "phone")
        assert phone["seen"] is None
        world.indicators.docs[indicator_doc_id(ScamIndicator.model_validate(phone))] = {
            "report_count": 4,
            "incident_count": 2,
            "last_reported_at": world.repo.docs[(UID, answer["id"])]["created_at"],
            "flagged": True,
        }
        detail = api.get(f"{CHECKS}/{answer['id']}").json()
        cached = api.post(ANALYZE, json=_body(RAW_MESSAGE)).json()

    for shown in (detail, cached):
        seen = next(i for i in shown["indicators"] if i["kind"] == "phone")["seen"]
        assert (seen["reports"], seen["incidents"], seen["flagged"]) == (4, 2, True)


# --- the guards --------------------------------------------------------------------------------


@pytest.mark.parametrize("path", [CHECKS, f"{CHECKS}/{'0' * 32}"])
def test_the_history_needs_a_token_and_the_flag(world: Setup, path: str) -> None:
    with world.client(signed_in=False) as api:
        assert_envelope(api.get(path), 401, "unauthenticated")
    with world.client(flag_on=False) as api:
        assert_envelope(api.get(path), 404, "not_found")
