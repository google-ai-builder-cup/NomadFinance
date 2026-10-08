from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from firebase_admin import firestore  # type: ignore[import-untyped]

from src.config import COST_BASELINES_DIR
from src.loaders import cost_baselines
from src.loaders.cost_baselines import content_hash, load_baseline_docs, main
from src.validators.cost_baselines import CostBaseline, load_baselines


class _Snapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self.exists = data is not None
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


class _Batch:
    def __init__(self, client: _FakeClient) -> None:
        self._client = client
        self._ops: list[tuple[str, dict[str, Any]]] = []

    def set(self, ref: _Ref, data: dict[str, Any]) -> None:
        self._ops.append((ref.path, data))

    def commit(self) -> None:
        self._client.commits.append([path for path, _ in self._ops])
        for path, data in self._ops:
            self._client.store[path] = copy.deepcopy(data)


class _FakeClient:
    """Stand-in for google.cloud.firestore.Client: path-keyed store, batches, commit log."""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.commits: list[list[str]] = []

    def collection(self, name: str) -> _Ref:
        return _Ref(self, name)

    def batch(self) -> _Batch:
        return _Batch(self)


def _baselines() -> dict[str, CostBaseline]:
    return load_baselines(only=["SG", "AU"])


def _load(client: _FakeClient, baselines: dict[str, CostBaseline] | None = None, **kw: Any) -> Any:
    return load_baseline_docs(client, baselines or _baselines(), **kw)  # type: ignore[arg-type]


def _no_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise AssertionError("Firestore must not be touched")

    monkeypatch.setattr(cost_baselines, "get_firestore_client", boom)


def _two_hosts(tmp_path: Path) -> Path:
    target = tmp_path / "cost-baselines"
    target.mkdir()
    for host in ("SG", "AU"):
        shutil.copy(COST_BASELINES_DIR / f"{host}.json", target / f"{host}.json")
    return target


def test_first_load_writes_both_countries_at_version_1_in_one_batch() -> None:
    client = _FakeClient()

    results = _load(client)

    assert [(r.host, r.version, r.status) for r in results] == [("SG", 1, "new"), ("AU", 1, "new")]
    assert set(client.store) == {"cost_baselines/SG", "cost_baselines/AU"}
    assert len(client.commits) == 1


def test_a_document_has_the_fields_the_collection_doc_lists() -> None:
    client = _FakeClient()
    _load(client)

    sg = client.store["cost_baselines/SG"]

    assert sg["host_country"] == "SG" and sg["currency"] == "SGD"
    assert set(sg["categories"]) == {
        "accommodation",
        "food",
        "transport",
        "phone_data",
        "mandatory_deductions",
    }
    assert sg["version"] == 1 and sg["schema_version"] == 1
    assert len(sg["content_hash"]) == 64
    assert sg["updated_at"] == firestore.SERVER_TIMESTAMP
    assert isinstance(sg["categories"]["food"]["source"]["retrieved_on"], str)
    assert sg["categories"]["accommodation"]["by_job_type"]["domestic_worker"]["high"] == 0


def test_a_field_the_curator_left_out_is_not_written_as_null() -> None:
    client = _FakeClient()
    _load(client)

    au = client.store["cost_baselines/AU"]

    assert "other_sources" not in au["categories"]["food"]
    assert "by_job_type" not in au["categories"]["food"]


def test_rerun_changes_nothing_and_makes_no_write_call() -> None:
    client = _FakeClient()
    _load(client)
    before = copy.deepcopy(client.store)

    results = _load(client)

    assert {(r.version, r.status) for r in results} == {(1, "unchanged")}
    assert client.store == before
    assert len(client.commits) == 1


def test_a_changed_figure_raises_that_countrys_version_only() -> None:
    client = _FakeClient()
    _load(client)
    changed = _baselines()
    changed["SG"].categories["food"].typical = 170

    results = {r.host: r for r in _load(client, changed)}

    assert (results["SG"].version, results["SG"].status) == (2, "changed")
    assert (results["AU"].version, results["AU"].status) == (1, "unchanged")
    assert client.commits[-1] == ["cost_baselines/SG"]
    assert client.store["cost_baselines/SG"]["categories"]["food"]["typical"] == 170


def test_a_changed_note_raises_the_version_because_a_plan_may_quote_it() -> None:
    client = _FakeClient()
    _load(client)
    changed = _baselines()
    changed["AU"].categories["food"].notes = "Food and groceries in Sydney, rewritten wording."

    results = {r.host: r for r in _load(client, changed)}

    assert (results["AU"].version, results["AU"].status) == (2, "changed")


def test_a_new_source_is_stored_without_raising_the_version() -> None:
    client = _FakeClient()
    _load(client)
    rechecked = _baselines()
    rechecked["SG"].categories["food"].source.publisher = "TWC2, checked again"
    rechecked["SG"].categories["food"].curator = "XY"

    results = {r.host: r for r in _load(client, rechecked)}

    assert (results["SG"].version, results["SG"].status) == (1, "refreshed")
    stored = client.store["cost_baselines/SG"]["categories"]["food"]
    assert stored["source"]["publisher"] == "TWC2, checked again" and stored["curator"] == "XY"


def test_source_curator_and_other_sources_stay_out_of_the_hash() -> None:
    original = content_hash(_baselines()["SG"])
    edited = _baselines()["SG"]
    figure = edited.categories["accommodation"]
    figure.curator = "XY"
    figure.source.publisher = "Another publisher"
    assert figure.other_sources is not None
    figure.other_sources[0].publisher = "Another publisher too"

    assert content_hash(edited) == original


def test_a_figure_or_a_job_type_override_changes_the_hash() -> None:
    original = content_hash(_baselines()["SG"])
    figure_changed = _baselines()["SG"]
    figure_changed.categories["transport"].high = 140
    override_changed = _baselines()["SG"]
    by_job = override_changed.categories["food"].by_job_type
    assert by_job is not None
    by_job["domestic_worker"].high = 50

    assert content_hash(figure_changed) != original
    assert content_hash(override_changed) != original


def test_other_countries_and_collections_are_left_alone() -> None:
    client = _FakeClient()
    client.store["cost_baselines/KR"] = {"host_country": "KR", "version": 4, "content_hash": "x"}
    client.store["scam_taxonomy/_meta"] = {"version": 2}

    _load(client)

    assert client.store["cost_baselines/KR"]["version"] == 4
    assert "scam_taxonomy/_meta" in client.store


def test_writes_go_to_the_requested_collection() -> None:
    client = _FakeClient()

    _load(client, collection="staging_baselines")

    assert client.store and all(p.startswith("staging_baselines/") for p in client.store)


def test_dry_run_validates_without_touching_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_firestore(monkeypatch)

    assert main(["--only", "SG", "AU", "--dry-run"]) == 0


def test_a_broken_file_stops_the_run_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _two_hosts(tmp_path)
    path = directory / "AU.json"
    broken = json.loads(path.read_text(encoding="utf-8"))
    broken["categories"]["food"]["low"] = 9999
    path.write_text(json.dumps(broken), encoding="utf-8")
    _no_firestore(monkeypatch)

    assert main(["--input-dir", str(directory)]) == 1


def test_only_skips_a_file_that_is_not_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _two_hosts(tmp_path)
    (directory / "AU.json").write_text("{}", encoding="utf-8")
    client = _FakeClient()
    monkeypatch.setattr(cost_baselines, "get_firestore_client", lambda: client)

    assert main(["--input-dir", str(directory), "--only", "SG"]) == 0

    assert set(client.store) == {"cost_baselines/SG"}


def test_a_host_without_a_file_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_firestore(monkeypatch)

    assert main(["--input-dir", str(_two_hosts(tmp_path)), "--only", "KR"]) == 1


def test_a_missing_folder_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_firestore(monkeypatch)

    assert main(["--input-dir", str(tmp_path / "nope")]) == 1


def test_main_writes_to_the_requested_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _FakeClient()
    monkeypatch.setattr(cost_baselines, "get_firestore_client", lambda: client)

    assert main(["--input-dir", str(_two_hosts(tmp_path)), "--collection", "baselines_x"]) == 0

    assert set(client.store) == {"baselines_x/SG", "baselines_x/AU"}
