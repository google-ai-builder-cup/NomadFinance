from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from firebase_admin import firestore  # type: ignore[import-untyped]

from src.config import SCAM_TAXONOMY_DIR
from src.loaders import scam_taxonomy
from src.loaders.scam_taxonomy import content_hash, load_taxonomy_docs, main
from src.validators.scam_taxonomy import Taxonomy, load_taxonomy


class _Snapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self.exists = data is not None
        self.id = ""
        self._data = data

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


class _Ref:
    def __init__(self, client: _FakeClient, path: str) -> None:
        self._client = client
        self.path = path

    def document(self, doc_id: str) -> _Ref:
        return _Ref(self._client, f"{self.path}/{doc_id}")

    def get(self) -> _Snapshot:
        return _Snapshot(self._client.store.get(self.path))

    def stream(self) -> list[_Snapshot]:
        prefix = f"{self.path}/"
        out = []
        for path in self._client.store:
            if path.startswith(prefix) and "/" not in path.removeprefix(prefix):
                snap = _Snapshot(self._client.store[path])
                snap.id = path.removeprefix(prefix)
                out.append(snap)
        return out


class _Batch:
    def __init__(self, client: _FakeClient) -> None:
        self._client = client
        self._ops: list[tuple[str, str, dict[str, Any] | None]] = []

    def set(self, ref: _Ref, data: dict[str, Any]) -> None:
        self._ops.append(("set", ref.path, data))

    def delete(self, ref: _Ref) -> None:
        self._ops.append(("delete", ref.path, None))

    def commit(self) -> None:
        self._client.commits.append([path for _, path, _ in self._ops])
        for action, path, data in self._ops:
            if action == "set" and data is not None:
                self._client.store[path] = copy.deepcopy(data)
            else:
                self._client.store.pop(path, None)


class _FakeClient:
    """Stand-in for google.cloud.firestore.Client: path-keyed store, batches, commit log."""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.commits: list[list[str]] = []

    def collection(self, name: str) -> _Ref:
        return _Ref(self, name)

    def batch(self) -> _Batch:
        return _Batch(self)


def _load(client: _FakeClient, taxonomy: Taxonomy | None = None, **kwargs: Any) -> Any:
    return load_taxonomy_docs(client, taxonomy or load_taxonomy(), **kwargs)  # type: ignore[arg-type]


def _no_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise AssertionError("Firestore must not be touched")

    monkeypatch.setattr(scam_taxonomy, "get_firestore_client", boom)


def test_first_load_writes_every_entry_and_meta_version_1() -> None:
    client = _FakeClient()

    result = _load(client)

    assert (result.types, result.tactics, result.version, result.status) == (8, 6, 1, "new")
    assert len(client.store) == 8 + 6 + 1
    meta = client.store["scam_taxonomy/_meta"]
    assert meta["version"] == 1
    assert meta["updated_at"] == firestore.SERVER_TIMESTAMP
    assert len(meta["content_hash"]) == 64


def test_documents_carry_kind_and_schema_version_and_omit_the_other_kinds_fields() -> None:
    client = _FakeClient()
    _load(client)

    job = client.store["scam_taxonomy/fake_job_offer"]
    urgency = client.store["scam_taxonomy/urgency"]

    assert job["kind"] == "type" and urgency["kind"] == "tactic"
    assert job["schema_version"] == 1 and urgency["schema_version"] == 1
    assert job["default_risk"] == "high" and "how_it_works" not in job
    assert "how_it_works" in urgency and "default_risk" not in urgency
    assert isinstance(job["sources"][0]["retrieved_on"], str)


def test_everything_is_written_in_one_batch() -> None:
    client = _FakeClient()

    _load(client)

    assert len(client.commits) == 1


def test_rerun_changes_nothing_and_keeps_the_version() -> None:
    client = _FakeClient()
    _load(client)
    before = copy.deepcopy(client.store)

    result = _load(client)

    assert (result.version, result.status, result.removed) == (1, "unchanged", 0)
    assert client.store == before
    assert "scam_taxonomy/_meta" not in client.commits[-1]


def test_a_wording_change_raises_the_version_by_one() -> None:
    client = _FakeClient()
    _load(client)
    changed = load_taxonomy()
    changed.types["lottery"].safe_response = "Do not pay anything to get a prize. Block the sender."

    result = _load(client, changed)

    assert (result.version, result.status) == (2, "changed")
    assert client.store["scam_taxonomy/_meta"]["version"] == 2


def test_source_and_curator_changes_do_not_change_the_hash() -> None:
    original = content_hash(load_taxonomy())
    edited = load_taxonomy()
    edited.types["lottery"].curator = "XY"
    edited.types["lottery"].sources[0].publisher = "Another publisher"

    assert content_hash(edited) == original


def test_removed_entries_are_deleted_but_meta_is_kept() -> None:
    client = _FakeClient()
    client.store["scam_taxonomy/old_type"] = {"kind": "type"}
    client.store["scam_taxonomy/_meta"] = {"version": 4, "content_hash": "x"}

    result = _load(client)

    assert result.removed == 1
    assert "scam_taxonomy/old_type" not in client.store
    assert client.store["scam_taxonomy/_meta"]["version"] == 5


def test_other_collections_are_left_alone() -> None:
    client = _FakeClient()
    client.store["scam_patterns/x"] = {"scam_type": "lottery"}

    _load(client)

    assert "scam_patterns/x" in client.store


def test_writes_go_to_the_requested_collection() -> None:
    client = _FakeClient()

    _load(client, collection="staging_taxonomy")

    assert client.store and all(p.startswith("staging_taxonomy/") for p in client.store)


def test_dry_run_validates_without_touching_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_firestore(monkeypatch)

    assert main(["--dry-run"]) == 0


def test_a_broken_file_stops_the_run_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "scam-taxonomy"
    shutil.copytree(SCAM_TAXONOMY_DIR, data)
    broken = json.loads((data / "types.json").read_text(encoding="utf-8"))
    broken["entries"]["lottery"]["signs"] = ["one", "two"]
    (data / "types.json").write_text(json.dumps(broken), encoding="utf-8")
    _no_firestore(monkeypatch)

    assert main(["--input-dir", str(data)]) == 1


def test_a_missing_folder_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_firestore(monkeypatch)

    assert main(["--input-dir", str(tmp_path)]) == 1


def test_main_writes_to_the_requested_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    monkeypatch.setattr(scam_taxonomy, "get_firestore_client", lambda: client)

    assert main(["--collection", "scam_taxonomy_staging"]) == 0

    assert client.store and all(p.startswith("scam_taxonomy_staging/") for p in client.store)
