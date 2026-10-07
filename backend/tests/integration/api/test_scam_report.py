"""NF-SA-013 through the API: `POST /api/v2/scam/checks/{id}/report`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.schemas.scam import ScamCheckDetail, ScamReportResponse
from tests.fixtures.fake_gemini import FakeGemini
from tests.fixtures.scam_app import assert_envelope, make_app
from tests.fixtures.scam_checks import mock_check, put_check
from tests.fixtures.scam_classify import MOCKS
from tests.fixtures.scam_report import ReportWorld

UID = "worker-a"
PHONE_ID, URL_ID = "8c83cb97", "f2c46aad"


class Setup:
    def __init__(self, case: str = "high", **world_options: Any) -> None:
        self.world = ReportWorld(**world_options)
        self.check_id = put_check(self.world.checks, UID, mock_check(case))
        self.report_url = f"/api/v2/scam/checks/{self.check_id}/report"

    def client(self, uid: str = UID, **options: Any) -> TestClient:
        app = make_app(
            FakeGemini(), store=self.world.store, uid=uid, reporter=self.world.reporter, **options
        )
        return TestClient(app, raise_server_exceptions=False)


def _body(**changes: Any) -> dict[str, Any]:
    return {"indicator_ids": [PHONE_ID, URL_ID]} | changes


def _mock(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((MOCKS / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


@pytest.fixture
def setup() -> Setup:
    return Setup()


# ---------------------------------------------------------------- created and repeated


def test_a_confirmed_report_is_a_201_with_the_contracts_answer(setup: Setup) -> None:
    with setup.client() as api:
        response = api.post(setup.report_url, json=_body())

    assert response.status_code == 201
    answer = response.json()
    ScamReportResponse.model_validate(answer)
    mock = _mock("report-01-created")["body"]
    assert set(answer) == set(mock)
    assert answer["already_reported"] is False
    assert answer["entity_slug"] == mock["entity_slug"] == "scam-illegal-recruitment-fee"
    assert answer["entity_name"] == mock["entity_name"]


def test_a_second_tap_is_a_200_with_the_same_report_and_nothing_counted_again(
    setup: Setup,
) -> None:
    with setup.client() as api:
        first = api.post(setup.report_url, json=_body()).json()
        counts = json.dumps(setup.world.indicators.docs, default=str, sort_keys=True)
        second = api.post(setup.report_url, json=_body(indicator_ids=[]))

    assert second.status_code == 200
    answer = second.json()
    ScamReportResponse.model_validate(answer)
    assert set(answer) == set(_mock("report-02-already-reported")["body"])
    assert answer["already_reported"] is True and answer["report_id"] == first["report_id"]
    assert answer["created_at"] == first["created_at"]
    assert len(setup.world.radar.reports) == 1
    assert json.dumps(setup.world.indicators.docs, default=str, sort_keys=True) == counts


def test_a_report_with_every_indicator_unticked_is_still_created(setup: Setup) -> None:
    with setup.client() as api:
        response = api.post(setup.report_url, json={"indicator_ids": []})

    assert response.status_code == 201 and setup.world.indicators.docs == {}


def test_the_text_defaults_to_the_masked_message_and_is_masked_again_when_sent(
    setup: Setup,
) -> None:
    with setup.client() as api:
        api.post(setup.report_url, json=_body(description="Ring +65 9123 4567 about it"))

    stored = setup.world.radar.reports["r_01"]["description"]
    assert "[PHONE]" in stored and "9123 4567" not in stored


def test_nothing_that_identifies_the_worker_is_in_the_answer_or_the_stored_report(
    setup: Setup,
) -> None:
    with setup.client() as api:
        response = api.post(setup.report_url, json=_body())

    stored = json.dumps(setup.world.radar.reports["r_01"], default=str)
    for forbidden in (UID, setup.check_id, "reporter_hash"):
        assert forbidden not in response.text
        assert forbidden not in stored


# ---------------------------------------------------------------- the check shows it


def test_the_check_then_shows_it_was_reported_and_its_indicators_how_often(setup: Setup) -> None:
    with setup.client() as api:
        report = api.post(setup.report_url, json=_body()).json()
        detail = api.get(f"/api/v2/scam/checks/{setup.check_id}").json()
        history = api.get("/api/v2/scam/checks").json()

    ScamCheckDetail.model_validate(detail)
    assert (detail["reported"], detail["report_id"]) == (True, report["report_id"])
    assert history["items"][0]["reported"] is True
    # The counters this task writes are what the check now reads: the indicator `seen`.
    by_kind = {i["kind"]: i for i in detail["indicators"]}
    assert by_kind["phone"]["seen"]["reports"] == 1
    assert by_kind["phone"]["seen"]["flagged"] is False
    assert by_kind["url"]["seen"]["reports"] == 1


def test_a_second_workers_check_of_the_same_number_now_shows_it_was_reported(
    setup: Setup,
) -> None:
    other = put_check(setup.world.checks, "worker-b", mock_check("high"))
    with setup.client() as api:
        api.post(setup.report_url, json=_body())
    with setup.client("worker-b") as api:
        detail = api.get(f"/api/v2/scam/checks/{other}").json()

    assert detail["reported"] is False
    assert {i["kind"]: i["seen"]["reports"] for i in detail["indicators"]} == {
        "phone": 1,
        "url": 1,
    }


# ---------------------------------------------------------------- refusals


def test_a_message_judged_safe_is_a_409_not_a_scam() -> None:
    setup = Setup("benign")
    with setup.client() as api:
        response = api.post(setup.report_url, json={"indicator_ids": []})

    envelope = assert_envelope(response, 409, "not_a_scam")
    assert envelope.message == _mock("report-error-not-a-scam")["body"]["message"]
    assert setup.world.radar.reports == {}


def test_an_unknown_indicator_is_a_422_that_names_the_field(setup: Setup) -> None:
    with setup.client() as api:
        response = api.post(setup.report_url, json=_body(indicator_ids=[PHONE_ID, "0badc0de"]))

    envelope = assert_envelope(response, 422, "validation_failed")
    assert envelope.details is not None
    assert (envelope.details[0].field, envelope.details[0].issue) == (
        "body.indicator_ids",
        "Unknown indicator: 0badc0de",
    )
    assert setup.world.radar.reports == {}


@pytest.mark.parametrize(
    "body",
    [
        {"indicator_ids": [PHONE_ID, PHONE_ID]},  # a repeat
        {"indicator_ids": [f"{i:08x}" for i in range(11)]},  # more than 10
        {"indicator_ids": ["not-hex!"]},
        {"indicator_ids": [], "description": "   "},  # empty once trimmed
        {"indicator_ids": [], "description": "x" * 1001},  # over 1,000 characters
        {"description": "a text but no indicator list"},
        {},
    ],
)
def test_a_bad_request_is_a_422_and_writes_nothing(setup: Setup, body: dict[str, Any]) -> None:
    with setup.client() as api:
        response = api.post(setup.report_url, json=body)

    assert_envelope(response, 422, "validation_failed")
    assert setup.world.radar.reports == {} and setup.world.reports.calls == 0


@pytest.mark.parametrize("check_id", ["0" * 32, "nope", "x" * 70])
def test_a_check_that_is_not_there_is_a_404(setup: Setup, check_id: str) -> None:
    with setup.client() as api:
        response = api.post(f"/api/v2/scam/checks/{check_id}/report", json=_body())

    assert_envelope(response, 404, "not_found")


def test_another_workers_check_is_the_same_404(setup: Setup) -> None:
    with setup.client("worker-b") as api:
        response = api.post(setup.report_url, json=_body())

    assert_envelope(response, 404, "not_found")
    assert setup.world.radar.reports == {}


def test_no_token_is_a_401_and_flag_off_is_a_404(setup: Setup) -> None:
    with setup.client(signed_in=False) as api:
        assert_envelope(api.post(setup.report_url, json=_body()), 401, "unauthenticated")
    with setup.client(flag_on=False) as api:
        assert_envelope(api.post(setup.report_url, json=_body()), 404, "not_found")
    assert setup.world.radar.reports == {}


def test_the_ai_budget_applies_because_a_report_embeds_its_text(setup: Setup) -> None:
    with setup.client() as api:
        statuses = [api.post(setup.report_url, json=_body()).status_code for _ in range(11)]

    assert statuses[0] == 201 and statuses[1:10] == [200] * 9
    assert statuses[10] == 429


def test_the_route_is_in_the_openapi_with_its_four_outcomes() -> None:
    app = make_app(FakeGemini())
    operation = app.openapi()["paths"]["/api/v2/scam/checks/{check_id}/report"]["post"]

    assert {"200", "201", "404", "409", "422", "429"} <= set(operation["responses"])


def test_the_mocks_folder_has_the_four_samples_the_contract_lists() -> None:
    names = {p.name for p in Path(MOCKS).glob("report-*.json")}

    assert names == {
        "report-01-created.json",
        "report-02-already-reported.json",
        "report-error-not-a-scam.json",
        "report-error-validation.json",
    }
