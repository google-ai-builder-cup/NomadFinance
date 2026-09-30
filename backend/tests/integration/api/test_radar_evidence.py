from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_current_user
from app.integrations.cloud_storage import get_radar_evidence_store
from app.main import create_app
from app.repositories.radar_repo import get_radar_repository
from app.schemas.user import AuthenticatedUser
from app.services.radar.evidence import MAX_EVIDENCE_FILES
from app.utils.hashing import hash_reporter

SECRET = "test-reporter-hash-secret"  # matches tests/conftest.py's RADAR_REPORTER_HASH_SECRET
UID = "worker-uid"
REPORT_ID = "abcdefghijklmnopqrst"  # 20 chars, matches the path pattern
URL = f"/api/v1/radar/report/{REPORT_ID}/evidence"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"x" * 20


class FakeStore:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, bytes, str]] = []

    def upload(self, report_id: str, filename: str, data: bytes, content_type: str) -> str:
        self.uploads.append((report_id, filename, data, content_type))
        return f"radar-evidence/{report_id}/{filename}"


class FakeRadar:
    def __init__(self, report: dict[str, Any] | None) -> None:
        self.report = report
        self.added: list[tuple[str, str]] = []

    def get(self, report_id: str) -> dict[str, Any] | None:
        return self.report

    def add_evidence_path(self, report_id: str, path: str) -> None:
        self.added.append((report_id, path))
        if self.report is not None:
            self.report = self.report | {
                "evidence_paths": [*self.report.get("evidence_paths", []), path]
            }


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def radar() -> FakeRadar:
    return FakeRadar({"reporter_hash": hash_reporter(UID, SECRET), "evidence_paths": []})


@pytest.fixture
def app(store: FakeStore, radar: FakeRadar) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid=UID)
    app.dependency_overrides[get_radar_evidence_store] = lambda: store
    app.dependency_overrides[get_radar_repository] = lambda: radar
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def upload(api: TestClient, data: bytes = PNG_BYTES, content_type: str = "image/png") -> Any:
    return api.post(URL, files={"file": ("evidence.png", data, content_type)})


def test_a_valid_upload_is_accepted_and_recorded(
    api: TestClient, store: FakeStore, radar: FakeRadar
) -> None:
    response = upload(api)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["report_id"] == REPORT_ID
    assert len(body["evidence_paths"]) == 1
    assert body["evidence_paths"][0].startswith(f"radar-evidence/{REPORT_ID}/")
    assert len(store.uploads) == 1
    assert len(radar.added) == 1


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        response = client.post(URL, files={"file": ("a.png", PNG_BYTES, "image/png")})

    assert response.status_code == 401


def test_a_report_id_of_the_wrong_shape_is_a_422(api: TestClient) -> None:
    response = api.post(
        "/api/v1/radar/report/not-a-valid-id/evidence",
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 422


def test_no_such_report_is_a_404(api: TestClient, radar: FakeRadar) -> None:
    radar.report = None

    assert upload(api).status_code == 404


def test_a_contract_signal_report_with_no_reporter_is_a_404(
    api: TestClient, radar: FakeRadar
) -> None:
    radar.report = {"reporter_hash": None, "evidence_paths": []}

    assert upload(api).status_code == 404


def test_a_different_workers_token_is_rejected(app: FastAPI) -> None:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="someone-else")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(URL, files={"file": ("a.png", PNG_BYTES, "image/png")})

    assert response.status_code == 403


def test_the_cap_is_enforced(api: TestClient, radar: FakeRadar) -> None:
    radar.report = radar.report | {"evidence_paths": [f"p{n}" for n in range(MAX_EVIDENCE_FILES)]}

    response = upload(api)

    assert response.status_code == 422


def test_missing_file_is_rejected(api: TestClient) -> None:
    assert api.post(URL).status_code == 422


def test_empty_file_is_rejected(api: TestClient) -> None:
    assert upload(api, b"").status_code == 400


def test_file_over_limit_is_rejected_before_upload(
    app: FastAPI, api: TestClient, store: FakeStore
) -> None:
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={"upload_max_bytes": 1000}
    )

    response = upload(api, PNG_BYTES + b"x" * 1000)

    assert response.status_code == 413
    assert store.uploads == []


def test_unsupported_file_type_is_rejected(api: TestClient, store: FakeStore) -> None:
    response = upload(api, b"not a real image", "image/png")

    assert response.status_code == 415
    assert store.uploads == []


def test_endpoint_is_documented_in_openapi(api: TestClient) -> None:
    paths = api.get("/openapi.json").json()["paths"]
    operation = paths["/api/v1/radar/report/{report_id}/evidence"]["post"]

    assert {"401", "403", "404", "413", "415", "422"} <= set(operation["responses"])
