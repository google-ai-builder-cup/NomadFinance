from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.gemini import GeminiResponseError, GeminiUnavailableError, get_gemini_client
from app.main import create_app
from app.repositories.radar_repo import get_radar_repository
from app.schemas.radar import RadarReport
from app.schemas.radar_report import ExtractedEntity, ReportScreen, ViolationClassification
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/radar/report"

BODY: dict[str, Any] = {
    "entity_type": "money_transfer_operator",
    "entity_name": "Example Remit",
    "corridor_id": "SG-IN",
    "description": "They showed one rate and gave me a worse one at the counter.",
    "language": "en",
}

EXTRACTED = ExtractedEntity(
    entity_name="Example Remit",
    entity_name_normalized="example-remit",
    entity_type="money_transfer_operator",
    corridor_id="SG-IN",
    host_country=None,
    amount=50.0,
    currency="SGD",
)
SCREEN = ReportScreen(
    spam_score=0.02, reason="Real, specific account.", is_abusive=False, personal_data=[]
)
CLASSIFICATION = ViolationClassification(
    violation_type="hidden_fees",
    category_confidence=0.91,
    summary="Operator charged a worse rate than shown before sending.",
)


class FakeGemini:
    def __init__(self) -> None:
        self.outcomes: dict[str, Any] = {
            "ExtractedEntity": EXTRACTED,
            "ReportScreen": SCREEN,
            "ViolationClassification": CLASSIFICATION,
        }
        self.calls: list[dict[str, Any]] = []

    async def embed_text(self, text: str, *, operation: str) -> list[float]:
        return [0.6, 0.8]

    async def generate_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes[kwargs["response_model"].__name__]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeRadarRepo:
    def __init__(self) -> None:
        self.created: list[tuple[str, RadarReport]] = []
        self.entities: dict[str, dict[str, Any]] = {}

    def new_report_id(self) -> str:
        return "r_test01"

    def find_similar(self, embedding: list[float], corridor_id: str, limit: int) -> list[Any]:
        return []

    def create_embedding(self, report_id: str, embedding: list[float], **kwargs: Any) -> None:
        pass

    def create_report(self, report_id: str, report: RadarReport) -> None:
        self.created.append((report_id, report))

    def get_entity(self, slug: str) -> dict[str, Any] | None:
        return self.entities.get(slug)

    def set_entity(self, entity: Any) -> None:
        self.entities[entity.slug] = entity.model_dump()


@pytest.fixture
def fake_gemini() -> FakeGemini:
    return FakeGemini()


@pytest.fixture
def fake_radar() -> FakeRadarRepo:
    return FakeRadarRepo()


@pytest.fixture
def app(fake_gemini: FakeGemini, fake_radar: FakeRadarRepo) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_gemini_client] = lambda: fake_gemini
    app.dependency_overrides[get_radar_repository] = lambda: fake_radar
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_stores_the_report_and_returns_a_confirmation(
    api: TestClient, fake_radar: FakeRadarRepo
) -> None:
    response = api.post(URL, json=BODY)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["report_id"] == "r_test01"
    assert body["entity_name"] == "Example Remit"
    assert body["violation_type"] == "hidden_fees"
    assert body["corridor_id"] == "SG-IN"
    assert body["summary"] == CLASSIFICATION.summary
    assert len(fake_radar.created) == 1
    assert fake_radar.entities["example-remit"]["report_count"] == 1


def test_the_worker_never_names_the_violation_type(api: TestClient) -> None:
    response = api.post(URL, json=BODY | {"violation_type": "wage_theft"})

    # Extra, unknown fields are ignored, not stored: violation_type always comes from step 4.
    assert response.status_code == 201, response.text
    assert response.json()["violation_type"] == "hidden_fees"


def test_only_description_and_language_are_required(api: TestClient) -> None:
    response = api.post(URL, json={"description": BODY["description"], "language": "en"})

    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    "body",
    [
        {k: v for k, v in BODY.items() if k != "description"},
        {k: v for k, v in BODY.items() if k != "language"},
        BODY | {"description": "too short"},
        BODY | {"language": "fr"},
        BODY | {"corridor_id": "US-MX"},
    ],
)
def test_invalid_body_is_rejected_before_gemini(
    api: TestClient, fake_gemini: FakeGemini, body: dict[str, Any]
) -> None:
    response = api.post(URL, json=body)

    assert response.status_code == 422
    assert fake_gemini.calls == []


def test_no_entity_named_anywhere_is_a_422(api: TestClient, fake_gemini: FakeGemini) -> None:
    fake_gemini.outcomes["ExtractedEntity"] = ExtractedEntity(
        entity_name=None,
        entity_name_normalized=None,
        entity_type="money_transfer_operator",
        corridor_id="SG-IN",
        host_country=None,
        amount=None,
        currency=None,
    )

    response = api.post(URL, json={k: v for k, v in BODY.items() if k != "entity_name"})

    assert response.status_code == 422


def test_no_location_anywhere_is_a_422(api: TestClient, fake_gemini: FakeGemini) -> None:
    fake_gemini.outcomes["ExtractedEntity"] = ExtractedEntity(
        entity_name="Example Remit",
        entity_name_normalized="example-remit",
        entity_type="money_transfer_operator",
        corridor_id=None,
        host_country=None,
        amount=None,
        currency=None,
    )

    response = api.post(URL, json={k: v for k, v in BODY.items() if k != "corridor_id"})

    assert response.status_code == 422


def test_spam_is_rejected_and_never_stored(
    api: TestClient, fake_gemini: FakeGemini, fake_radar: FakeRadarRepo
) -> None:
    fake_gemini.outcomes["ReportScreen"] = ReportScreen(
        spam_score=0.95, reason="Advertising text.", is_abusive=False, personal_data=[]
    )

    response = api.post(URL, json=BODY)

    assert response.status_code == 422
    assert fake_radar.created == []


def test_personal_data_is_rejected_and_never_stored(
    api: TestClient, fake_gemini: FakeGemini, fake_radar: FakeRadarRepo
) -> None:
    fake_gemini.outcomes["ReportScreen"] = ReportScreen(
        spam_score=0.0, reason="ok", is_abusive=False, personal_data=["home_address"]
    )

    response = api.post(URL, json=BODY)

    assert response.status_code == 422
    assert fake_radar.created == []


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (GeminiUnavailableError("gemini-x: 503 UNAVAILABLE"), 503),
        (GeminiResponseError("gemini-x output did not match ExtractedEntity"), 502),
    ],
)
def test_gemini_failures_map_to_clean_errors(
    api: TestClient, fake_gemini: FakeGemini, error: Exception, status_code: int
) -> None:
    fake_gemini.outcomes["ExtractedEntity"] = error

    response = api.post(URL, json=BODY)

    assert response.status_code == status_code
    assert "gemini-x" not in response.text


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        assert client.post(URL, json=BODY).status_code == 401


def test_endpoint_is_documented_in_openapi(api: TestClient) -> None:
    operation = api.get("/openapi.json").json()["paths"][URL]["post"]

    assert {"401", "422", "429", "502", "503", "504"} <= set(operation["responses"])
