"""Cloud Storage access through the Firebase Admin SDK, for files that belong to a user."""

from __future__ import annotations

from typing import Any

from firebase_admin import storage  # type: ignore[import-untyped]
from google.api_core.exceptions import NotFound

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
