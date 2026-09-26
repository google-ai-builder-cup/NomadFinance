from __future__ import annotations

from typing import Any

import pytest
from firebase_admin.exceptions import FirebaseError  # type: ignore[import-untyped]
from google.api_core.exceptions import NotFound, ServiceUnavailable

from app.integrations.cloud_storage import UserFileStore
from app.services.auth_service import AccountDeletionError, AccountService

# google-api-core's exception constructors have no type hints; build this one once.
_UNAVAILABLE: Exception = ServiceUnavailable("down")  # type: ignore[no-untyped-call]


class _FakeDb:
    def __init__(self, log: list[str], fail: Exception | None = None) -> None:
        self._log = log
        self._fail = fail

    def collection(self, name: str) -> _FakeDb:
        self._name = name
        return self

    def document(self, doc_id: str) -> str:
        return f"{self._name}/{doc_id}"

    def recursive_delete(self, ref: str) -> int:
        self._log.append(f"firestore:{ref}")
        if self._fail is not None:
            raise self._fail
        return 7


class _FakeFiles:
    def __init__(self, log: list[str], fail: Exception | None = None) -> None:
        self._log = log
        self._fail = fail

    def delete_user_files(self, uid: str) -> int:
        self._log.append(f"files:{uid}")
        if self._fail is not None:
            raise self._fail
        return 3


def _service(
    log: list[str],
    *,
    db_fail: Exception | None = None,
    files_fail: Exception | None = None,
    auth_result: bool | Exception = True,
) -> AccountService:
    def delete_auth(uid: str) -> bool:
        log.append(f"auth:{uid}")
        if isinstance(auth_result, Exception):
            raise auth_result
        return auth_result

    return AccountService(_FakeDb(log, db_fail), _FakeFiles(log, files_fail), delete_auth)  # type: ignore[arg-type]


def test_deletes_data_then_files_then_the_sign_in_account_last() -> None:
    log: list[str] = []

    result = _service(log).delete_account("u1")

    assert log == ["firestore:users/u1", "files:u1", "auth:u1"]
    assert (result.documents_deleted, result.files_deleted, result.auth_user_deleted) == (
        7,
        3,
        True,
    )


def test_an_account_that_is_already_gone_is_not_an_error() -> None:
    log: list[str] = []

    result = _service(log, auth_result=False).delete_account("u1")

    assert result.auth_user_deleted is False
    assert log[-1] == "auth:u1"


@pytest.mark.parametrize(
    ("db_fail", "files_fail", "auth_result", "expected_log"),
    [
        (_UNAVAILABLE, None, True, ["firestore:users/u1"]),
        (None, _UNAVAILABLE, True, ["firestore:users/u1", "files:u1"]),
        (
            None,
            None,
            FirebaseError("internal", "down"),
            ["firestore:users/u1", "files:u1", "auth:u1"],
        ),
    ],
)
def test_a_failure_stops_the_run_and_the_sign_in_account_is_kept_until_the_end(
    db_fail: Exception | None,
    files_fail: Exception | None,
    auth_result: bool | Exception,
    expected_log: list[str],
) -> None:
    log: list[str] = []

    with pytest.raises(AccountDeletionError):
        _service(
            log, db_fail=db_fail, files_fail=files_fail, auth_result=auth_result
        ).delete_account("u1")

    # Auth is attempted only after the data steps succeeded, so a person whose data step
    # failed can still sign in and try again.
    assert log == expected_log


class _Blob:
    def __init__(self, name: str, store: list[str], missing: bool = False) -> None:
        self.name = name
        self._store = store
        self._missing = missing

    def delete(self) -> None:
        if self._missing:
            raise NotFound("gone")  # type: ignore[no-untyped-call]
        self._store.remove(self.name)


class _Bucket:
    def __init__(self, names: list[str], already_gone: set[str] | None = None) -> None:
        self.names = names
        self._gone = already_gone or set()

    def list_blobs(self, prefix: str) -> Any:
        return iter(
            [
                _Blob(n, self.names, n in self._gone)
                for n in list(self.names)
                if n.startswith(prefix)
            ]
        )


def test_only_this_users_files_are_deleted_from_the_three_folders() -> None:
    names = [
        "contracts/u1/a.pdf",
        "contracts/u1/b.jpg",
        "bills/u1/c.png",
        "exports/u1/report.pdf",
        "contracts/u10/keep.pdf",  # another user whose id starts with the same letters
        "contracts/u2/keep.pdf",
        "radar-evidence/u1/keep.jpg",  # not a user folder
    ]
    bucket = _Bucket(names)

    deleted = UserFileStore(bucket).delete_user_files("u1")

    assert deleted == 4
    assert sorted(bucket.names) == [
        "contracts/u10/keep.pdf",
        "contracts/u2/keep.pdf",
        "radar-evidence/u1/keep.jpg",
    ]


def test_a_file_that_vanished_meanwhile_is_skipped() -> None:
    bucket = _Bucket(["contracts/u1/a.pdf", "bills/u1/b.png"], already_gone={"contracts/u1/a.pdf"})

    assert UserFileStore(bucket).delete_user_files("u1") == 1


@pytest.mark.parametrize("uid", ["", "a/b", "../other", "u1/"])
def test_a_uid_that_could_reach_other_folders_is_refused(uid: str) -> None:
    bucket = _Bucket(["contracts/other/x.pdf"])

    with pytest.raises(ValueError):
        UserFileStore(bucket).delete_user_files(uid)

    assert bucket.names == ["contracts/other/x.pdf"]
