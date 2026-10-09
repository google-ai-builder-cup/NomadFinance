"""Cloud Storage access through the Firebase Admin SDK, for files that belong to a user."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Any

from firebase_admin import storage  # type: ignore[import-untyped]
from google.api_core.exceptions import NotFound
from google.auth.transport import requests as google_requests
from google.oauth2 import service_account

from app.config import get_settings
from app.core.security import get_firebase_app

# Folder names follow frontend/storage.rules: each holds one sub-folder per uid.
USER_FILE_FOLDERS = ("contracts", "bills", "exports")


class UserFileStore:
    """Finds and deletes the files a user uploaded or exported."""

    def __init__(self, bucket: Any | None = None) -> None:
        self._bucket = bucket

    def _get_bucket(self) -> Any:
        if self._bucket is None:
            self._bucket = storage.bucket(
                get_settings().firebase_storage_bucket, app=get_firebase_app()
            )
        return self._bucket

    def delete_user_files(self, uid: str) -> int:
        """Delete every file under `<folder>/<uid>/` and return how many were removed.

        Safe to run again: a file that is already gone is skipped.
        """
        # A uid with a slash would widen the prefix to another user's files.
        if not uid or "/" in uid:
            raise ValueError("Not a valid user id")
        bucket = self._get_bucket()
        deleted = 0
        for folder in USER_FILE_FOLDERS:
            # List first: deleting while paging through the listing can skip files.
            for blob in list(bucket.list_blobs(prefix=f"{folder}/{uid}/")):
                try:
                    blob.delete()
                except NotFound:
                    continue
                deleted += 1
        return deleted


class RadarEvidenceStore:
    """Uploads report attachments to `radar-evidence/{report_id}/` (NF-P3-004).

    Not uid-scoped like `UserFileStore`: a report is anonymous (`reporter_hash`, never a
    uid), so evidence is filed by report id, never by who filed it. `storage.rules` denies
    all browser access to this folder; only the backend ever reads or writes it.
    """

    def __init__(self, bucket: Any | None = None) -> None:
        self._bucket = bucket

    def _get_bucket(self) -> Any:
        if self._bucket is None:
            self._bucket = storage.bucket(
                get_settings().firebase_storage_bucket, app=get_firebase_app()
            )
        return self._bucket

    def upload(self, report_id: str, filename: str, data: bytes, content_type: str) -> str:
        """Write one file under `radar-evidence/{report_id}/{filename}`; return its path."""
        path = f"radar-evidence/{report_id}/{filename}"
        self._get_bucket().blob(path).upload_from_string(data, content_type=content_type)
        return path


@lru_cache
def get_radar_evidence_store() -> RadarEvidenceStore:
    return RadarEvidenceStore()


class BillImageStore:
    """Uploads bill photos to `bills/{uid}/{entry_id}/` (NF-P3-011).

    The folder is one of `USER_FILE_FOLDERS`, so `storage.rules` lets the owner read the photo
    and account deletion removes it with the rest of the user's files.
    """

    def __init__(self, bucket: Any | None = None) -> None:
        self._bucket = bucket

    def _get_bucket(self) -> Any:
        if self._bucket is None:
            self._bucket = storage.bucket(
                get_settings().firebase_storage_bucket, app=get_firebase_app()
            )
        return self._bucket

    def upload(
        self, uid: str, entry_id: str, extension: str, data: bytes, content_type: str
    ) -> str:
        """Write the photo as `bills/{uid}/{entry_id}/bill.{extension}`; return its path."""
        # A uid with a slash would file the photo under another user's prefix.
        if not uid or "/" in uid:
            raise ValueError("Not a valid user id")
        path = f"bills/{uid}/{entry_id}/bill.{extension}"
        self._get_bucket().blob(path).upload_from_string(data, content_type=content_type)
        return path


@lru_cache
def get_bill_image_store() -> BillImageStore:
    return BillImageStore()


class ExportStore:
    """Stores the exported Financial Identity PDFs under `exports/{uid}/` (NF-P3-014).

    The folder is one of `USER_FILE_FOLDERS`: `storage.rules` lets the owner read it and
    account deletion removes it. A download link for someone else (a lender) is a signed URL.
    """

    def __init__(self, bucket: Any | None = None) -> None:
        self._bucket = bucket

    def _get_bucket(self) -> Any:
        if self._bucket is None:
            self._bucket = storage.bucket(
                get_settings().firebase_storage_bucket, app=get_firebase_app()
            )
        return self._bucket

    @staticmethod
    def _check(uid: str, path: str) -> None:
        # A uid with a slash, or a path outside the user's folder, would reach another
        # user's files.
        if not uid or "/" in uid or not path.startswith(f"exports/{uid}/") or ".." in path:
            raise ValueError("Not a valid export path")

    def upload(self, uid: str, filename: str, data: bytes) -> str:
        """Write the PDF as `exports/{uid}/{filename}`; return its path."""
        path = f"exports/{uid}/{filename}"
        self._check(uid, path)
        self._get_bucket().blob(path).upload_from_string(data, content_type="application/pdf")
        return path

    def read(self, uid: str, path: str) -> bytes | None:
        """The bytes of one export, or None if the file is gone."""
        self._check(uid, path)
        try:
            data: bytes = self._get_bucket().blob(path).download_as_bytes()
        except NotFound:
            return None
        return data

    def delete(self, uid: str, path: str) -> None:
        """Remove one export; a file that is already gone is not an error."""
        self._check(uid, path)
        try:
            self._get_bucket().blob(path).delete()
        except NotFound:
            return

    def signed_url(self, uid: str, path: str, expires: timedelta, download_name: str) -> str:
        """A V4 signed GET link that downloads the file as `download_name`.

        Cloud Run has no private key, so the link is signed through IAM as the service
        account itself (it needs `roles/iam.serviceAccountTokenCreator` on itself). A key file
        used locally signs directly.
        """
        self._check(uid, path)
        credentials = get_firebase_app().credential.get_credential()
        signing: dict[str, Any]
        if isinstance(credentials, service_account.Credentials):
            signing = {"credentials": credentials}
        else:
            if not credentials.valid:
                credentials.refresh(google_requests.Request())
            signing = {
                "service_account_email": credentials.service_account_email,
                "access_token": credentials.token,
            }
        return str(
            self._get_bucket()
            .blob(path)
            .generate_signed_url(
                version="v4",
                expiration=expires,
                method="GET",
                response_type="application/pdf",
                response_disposition=f'attachment; filename="{download_name}"',
                **signing,
            )
        )


@lru_cache
def get_export_store() -> ExportStore:
    return ExportStore()
