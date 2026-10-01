from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound
from google.oauth2 import service_account

from app.integrations import cloud_storage
from app.integrations.cloud_storage import ExportStore

PATH = "exports/u1/financial-identity-20261002T090000Z.pdf"


def _store() -> tuple[ExportStore, MagicMock]:
    bucket = MagicMock()
    return ExportStore(bucket), bucket


def _credentials(monkeypatch: pytest.MonkeyPatch, credentials: Any) -> None:
    app = MagicMock()
    app.credential.get_credential.return_value = credentials
    monkeypatch.setattr(cloud_storage, "get_firebase_app", lambda: app)


def test_upload_writes_a_pdf_under_the_users_exports_folder() -> None:
    store, bucket = _store()

    path = store.upload("u1", "financial-identity-20261002T090000Z.pdf", b"%PDF-1.7")

    assert path == PATH
    bucket.blob.assert_called_once_with(PATH)
    bucket.blob.return_value.upload_from_string.assert_called_once_with(
        b"%PDF-1.7", content_type="application/pdf"
    )


def test_delete_removes_the_file_and_forgives_one_that_is_gone() -> None:
    store, bucket = _store()

    store.delete("u1", PATH)
    bucket.blob.return_value.delete.assert_called_once_with()

    bucket.blob.return_value.delete.side_effect = NotFound("gone")
    store.delete("u1", PATH)


@pytest.mark.parametrize(
    ("uid", "path"),
    [
        ("u1", "exports/u2/report.pdf"),
        ("u1", "contracts/u1/report.pdf"),
        ("u1", "exports/u1/../u2/report.pdf"),
        ("", "exports//report.pdf"),
        ("a/b", "exports/a/b/report.pdf"),
    ],
)
def test_a_path_outside_the_users_exports_folder_is_refused(uid: str, path: str) -> None:
    store, bucket = _store()

    with pytest.raises(ValueError):
        store.delete(uid, path)
    with pytest.raises(ValueError):
        store.signed_url(uid, path, timedelta(hours=1), "r.pdf")

    bucket.blob.assert_not_called()


def test_a_key_file_signs_the_link_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    store, bucket = _store()
    key = MagicMock(spec=service_account.Credentials)
    _credentials(monkeypatch, key)
    bucket.blob.return_value.generate_signed_url.return_value = "https://signed.example/x"

    url = store.signed_url("u1", PATH, timedelta(hours=24), "financial-identity-report.pdf")

    assert url == "https://signed.example/x"
    kwargs = bucket.blob.return_value.generate_signed_url.call_args.kwargs
    assert kwargs["credentials"] is key
    assert "access_token" not in kwargs
    assert kwargs["version"] == "v4"
    assert kwargs["method"] == "GET"
    assert kwargs["expiration"] == timedelta(hours=24)
    assert kwargs["response_type"] == "application/pdf"
    assert kwargs["response_disposition"] == 'attachment; filename="financial-identity-report.pdf"'


def test_cloud_run_credentials_sign_through_iam(monkeypatch: pytest.MonkeyPatch) -> None:
    store, bucket = _store()
    compute = MagicMock(valid=True, token="ya29.token", service_account_email="api@x.iam")
    _credentials(monkeypatch, compute)
    bucket.blob.return_value.generate_signed_url.return_value = "https://signed.example/y"

    store.signed_url("u1", PATH, timedelta(hours=1), "r.pdf")

    kwargs = bucket.blob.return_value.generate_signed_url.call_args.kwargs
    assert kwargs["service_account_email"] == "api@x.iam"
    assert kwargs["access_token"] == "ya29.token"
    assert "credentials" not in kwargs
    compute.refresh.assert_not_called()


def test_expired_cloud_run_credentials_are_refreshed_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, bucket = _store()
    compute = MagicMock(valid=False, token="t", service_account_email="api@x.iam")
    _credentials(monkeypatch, compute)

    store.signed_url("u1", PATH, timedelta(hours=1), "r.pdf")

    compute.refresh.assert_called_once()
