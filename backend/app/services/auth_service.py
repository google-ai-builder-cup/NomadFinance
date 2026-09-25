"""Account lifecycle: deleting a user and everything stored about them (NF-P1-023)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from firebase_admin.exceptions import FirebaseError  # type: ignore[import-untyped]
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore import Client

logger = logging.getLogger(__name__)


class FileStore(Protocol):
    """What the service needs from Cloud Storage."""

    def delete_user_files(self, uid: str) -> int: ...


class AccountDeletionError(Exception):
    """A backing service failed part-way. Nothing is lost by running the deletion again."""


@dataclass(frozen=True)
class DeletionResult:
    documents_deleted: int
    files_deleted: int
    auth_user_deleted: bool


class AccountService:
    """Deletes an account in the only safe order: data first, the sign-in account last."""

    def __init__(
        self, db: Client, files: FileStore, delete_auth_user: Callable[[str], bool]
    ) -> None:
        self._db = db
        self._files = files
        self._delete_auth_user = delete_auth_user

    def delete_account(self, uid: str) -> DeletionResult:
        """Delete `users/{uid}` with all subcollections, the user's files, then the Auth user.

        The Auth user goes last on purpose: while it exists the person can still sign in and
        retry after a failure. Every step can be repeated, so a retry finishes the job.
        `radar_reports` the user filed are kept: they hold only a salted hash, never the uid
        (docs/data-model/collections/users.md).
        """
        try:
            documents = self._db.recursive_delete(self._db.collection("users").document(uid))
            files = self._files.delete_user_files(uid)
            auth_deleted = self._delete_auth_user(uid)
        except (GoogleAPICallError, FirebaseError) as exc:
            raise AccountDeletionError("Account deletion did not finish") from exc
        logger.info(
            "account_deleted documents=%d files=%d auth_user=%s", documents, files, auth_deleted
        )
        return DeletionResult(documents, files, auth_deleted)
