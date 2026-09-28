from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.contract_analysis import get_pipeline_deps
from app.dependencies import get_current_user
from app.integrations.gemini import GeminiUnavailableError, get_gemini_client
from app.main import create_app
from app.repositories.contract_repo import get_contract_repository
from app.schemas.contract import ExtractedContract
from app.schemas.user import AuthenticatedUser
from app.services.contract import letter, pipeline, report_store, upload
from app.services.contract.extractor import NotADocumentError
from app.services.contract.pipeline import PipelineDeps
from tests.fixtures.pipeline_fakes import FakeContracts, FakeLaws, FakeTemplates, FakeUsers, Steps

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "contracts"
PDF = (FIXTURES / "sample_contract_sg.pdf").read_bytes()


@pytest.fixture
def steps(monkeypatch: pytest.MonkeyPatch) -> Steps:
    fake = Steps()
    monkeypatch.setattr(upload, "extract_contract", fake.extract)
    monkeypatch.setattr(pipeline, "detect_contract", fake.detect)
    monkeypatch.setattr(pipeline, "compare_contract", fake.compare)
    monkeypatch.setattr(letter, "generate_complaint", fake.complaint)
    monkeypatch.setattr(report_store, "translate_report", fake.translate)
    return fake


@pytest.fixture
def contracts() -> FakeContracts:
    return FakeContracts()


@pytest.fixture
def app(steps: Steps, contracts: FakeContracts) -> FastAPI:
    app = create_app()
    deps = PipelineDeps(
        object(),  # type: ignore[arg-type]
        contracts,  # type: ignore[arg-type]
        FakeUsers({"host_country": "SG", "preferred_language": "hi"}),  # type: ignore[arg-type]
        FakeLaws(),  # type: ignore[arg-type]
        FakeTemplates(),  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="worker-1")
    app.dependency_overrides[get_pipeline_deps] = lambda: deps
    app.dependency_overrides[get_contract_repository] = lambda: contracts
    app.dependency_overrides[get_gemini_client] = lambda: object()
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def upload_file(api: TestClient, data: bytes = PDF) -> Any:
    return api.post("/api/v1/contracts", files={"file": ("contract.pdf", data, "application/pdf")})


def test_upload_creates_a_contract(api: TestClient) -> None:
    response = upload_file(api)

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["status"], body["reused"], body["legibility"]) == ("uploaded", False, "good")
    assert len(body["contract_id"]) == 20


def test_upload_uses_the_same_file_checks_as_extract(api: TestClient, steps: Steps) -> None:
    assert upload_file(api, b"").status_code == 400
    assert upload_file(api, b"not a pdf at all").status_code == 415
    assert steps.calls["extract"] == 0


def test_upload_of_a_non_document_is_a_422(
    api: TestClient, steps: Steps, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def not_a_document(*args: Any) -> ExtractedContract:
        raise NotADocumentError("selfie")

    monkeypatch.setattr(upload, "extract_contract", not_a_document)

    response = upload_file(api)

    assert response.status_code == 422
    assert "No readable document" in response.json()["detail"]


def test_analyze_returns_the_scores_and_the_report_languages(api: TestClient) -> None:
    contract_id = upload_file(api).json()["contract_id"]

    response = api.post(f"/api/v1/contracts/{contract_id}/analyze")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cached"] is False
    assert (body["risk_level"], body["health_score"]) == ("danger", 49)
    # The profile says Hindi: the English source plus the worker's report.
    assert (body["report_language"], body["report_languages"]) == ("hi", ["en", "hi"])


def test_analyze_takes_the_workers_choices(api: TestClient) -> None:
    contract_id = upload_file(api).json()["contract_id"]

    response = api.post(
        f"/api/v1/contracts/{contract_id}/analyze",
        json={"host_country": "MY", "job_type": "care_worker", "report_language": "en"},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["host_country"], body["job_type"], body["report_languages"]) == (
        "MY",
        "care_worker",
        ["en"],
    )


def test_a_stop_is_a_clear_message_and_is_stored(
    api: TestClient, steps: Steps, contracts: FakeContracts
) -> None:
    steps.detected = steps.detected.model_copy(update={"document_kind": "loan_agreement"})
    contract_id = upload_file(api).json()["contract_id"]

    response = api.post(f"/api/v1/contracts/{contract_id}/analyze")

    assert response.status_code == 422
    assert "employment contracts" in response.json()["detail"]
    assert contracts.contracts[("worker-1", contract_id)]["error"] == {
        "step": "compare",
        "code": "not_employment_contract",
    }


def test_a_gemini_failure_uses_the_usual_error_and_is_stored(
    api: TestClient, steps: Steps, contracts: FakeContracts
) -> None:
    steps.fail["detect"] = GeminiUnavailableError("gemini-x: 503")
    contract_id = upload_file(api).json()["contract_id"]

    response = api.post(f"/api/v1/contracts/{contract_id}/analyze")

    assert response.status_code == 503
    assert "gemini-x" not in response.text
    assert contracts.contracts[("worker-1", contract_id)]["error"]["code"] == "gemini_unavailable"


def test_analysis_already_running_is_a_409(api: TestClient, contracts: FakeContracts) -> None:
    contract_id = upload_file(api).json()["contract_id"]
    contracts.busy = True

    assert api.post(f"/api/v1/contracts/{contract_id}/analyze").status_code == 409


@pytest.mark.parametrize(
    ("contract_id", "status_code"),
    [("C0000000000000000404", 404), ("short", 422), ("../users/other-user", 404)],
)
def test_unknown_or_malformed_ids(api: TestClient, contract_id: str, status_code: int) -> None:
    assert api.post(f"/api/v1/contracts/{contract_id}/analyze").status_code == status_code


def test_report_in_another_language(api: TestClient, steps: Steps) -> None:
    contract_id = upload_file(api).json()["contract_id"]
    assert api.post(f"/api/v1/contracts/{contract_id}/reports/tl").status_code == 409

    api.post(f"/api/v1/contracts/{contract_id}/analyze", json={"report_language": "en"})
    response = api.post(f"/api/v1/contracts/{contract_id}/reports/tl")

    assert response.status_code == 200
    report = response.json()
    assert (report["language"], report["is_source"]) == ("tl", False)
    assert [c["risk"] for c in report["clauses"]] == ["danger"]
    assert api.post(f"/api/v1/contracts/{contract_id}/reports/fr").status_code == 422


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        assert client.post("/api/v1/contracts/C0000000000000000001/analyze").status_code == 401


def test_endpoints_are_documented_in_openapi(api: TestClient) -> None:
    paths = api.get("/openapi.json").json()["paths"]

    assert "post" in paths["/api/v1/contracts"]
    assert {"404", "409", "422", "503"} <= set(
        paths["/api/v1/contracts/{contract_id}/analyze"]["post"]["responses"]
    )
    assert "/api/v1/contracts/{contract_id}/reports/{language}" in paths
