from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from firebase_admin import firestore  # type: ignore[import-untyped]

from src.config import LABOR_LAWS_DIR
from src.loaders import ilo_natlex
from src.loaders.ilo_natlex import (
    content_hash,
    load_labor_laws,
    main,
    read_country_files,
)
from src.validators.labor_law import CATEGORY_IDS, COUNTRIES, LaborLawFile


class _Snapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self.exists = data is not None
        self._data = data

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


class _Ref:
    def __init__(self, store: dict[str, dict[str, Any]], path: str) -> None:
        self._store = store
        self.path = path

    def collection(self, name: str) -> _Ref:
        return _Ref(self._store, f"{self.path}/{name}")

    def document(self, doc_id: str) -> _Ref:
        return _Ref(self._store, f"{self.path}/{doc_id}")

    def get(self) -> _Snapshot:
        return _Snapshot(self._store.get(self.path))


class _Batch:
    def __init__(self, client: _FakeClient) -> None:
        self._client = client
        self._ops: list[tuple[str, dict[str, Any]]] = []

    def set(self, ref: _Ref, data: dict[str, Any]) -> None:
        self._ops.append((ref.path, data))

    def commit(self) -> None:
        self._client.commits.append([path for path, _ in self._ops])
        for path, data in self._ops:
            self.store_write(path, data)

    def store_write(self, path: str, data: dict[str, Any]) -> None:
        self._client.store[path] = data


class _FakeClient:
    """Stand-in for google.cloud.firestore.Client: path-keyed store, batches, commit log."""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.commits: list[list[str]] = []

    def collection(self, name: str) -> _Ref:
        return _Ref(self.store, name)

    def batch(self) -> _Batch:
        return _Batch(self)


def _files(directory: Path = LABOR_LAWS_DIR) -> dict[str, LaborLawFile]:
    files, skipped, problems = read_country_files(directory)
    assert not skipped and not problems
    return files


def _copy_data(tmp_path: Path) -> Path:
    target = tmp_path / "labor-laws"
    target.mkdir()
    for path in LABOR_LAWS_DIR.glob("*.json"):
        shutil.copy(path, target / path.name)
    return target


def _no_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise AssertionError("Firestore must not be touched")

    monkeypatch.setattr(ilo_natlex, "get_firestore_client", boom)


def test_first_load_writes_header_15_rules_and_meta_for_all_six() -> None:
    client = _FakeClient()

    results = load_labor_laws(client, _files())  # type: ignore[arg-type]

    assert [r.country for r in results] == list(COUNTRIES)
    assert all(r.version == 1 and r.status == "new" for r in results)
    assert len(client.store) == 6 * (1 + 15 + 1)
    for country in COUNTRIES:
        assert client.store[f"labor_laws/{country}"]["rule_count"] == 15
        for category in CATEGORY_IDS:
            assert f"labor_laws/{country}/rules/{category}" in client.store


def test_rule_documents_carry_country_category_and_schema_version() -> None:
    client = _FakeClient()
    load_labor_laws(client, _files())  # type: ignore[arg-type]

    rule = client.store["labor_laws/JP/rules/working_hours"]

    assert rule["country"] == "JP"
    assert rule["category"] == "working_hours"
    assert rule["schema_version"] == 1
    assert rule["coverage"] == "regulated"
    assert rule["variants"][0]["applies_to"] == ["all"]
    assert rule["last_verified_on"] == "2026-09-25"


def test_meta_document_has_the_documented_fields() -> None:
    client = _FakeClient()
    files = _files()
    load_labor_laws(client, files)  # type: ignore[arg-type]

    meta = client.store["labor_laws/SG/_meta/current"]

    assert meta["version"] == 1
    assert meta["category_ids"] == list(CATEGORY_IDS)
    assert meta["content_hash"] == content_hash(files["SG"])
    assert len(meta["content_hash"]) == 64
    assert meta["curated_by"] == files["SG"].curated_by
    assert meta["last_verified_on"] == files["SG"].last_verified_on.isoformat()
    assert meta["updated_at"] == firestore.SERVER_TIMESTAMP
    assert meta["schema_version"] == 1


def test_each_country_is_written_in_one_batch() -> None:
    client = _FakeClient()

    load_labor_laws(client, _files())  # type: ignore[arg-type]

    assert len(client.commits) == 6
    assert all(len(paths) == 17 for paths in client.commits)


def test_rerun_keeps_versions_and_does_not_rewrite_meta() -> None:
    client = _FakeClient()
    files = _files()
    load_labor_laws(client, files)  # type: ignore[arg-type]
    client.commits.clear()

    results = load_labor_laws(client, files)  # type: ignore[arg-type]

    assert all(r.version == 1 and r.status == "unchanged" for r in results)
    assert not any(p.endswith("/_meta/current") for paths in client.commits for p in paths)
    assert len(client.store) == 6 * 17


def test_changing_one_rule_bumps_only_that_country(tmp_path: Path) -> None:
    client = _FakeClient()
    load_labor_laws(client, _files())  # type: ignore[arg-type]
    data = _copy_data(tmp_path)
    path = data / "HK.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["rules"]["minimum_wage"]["summary"] += " Updated wording for the new rate."
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    results = {r.country: r for r in load_labor_laws(client, _files(data))}  # type: ignore[arg-type]

    assert results["HK"].version == 2 and results["HK"].status == "changed"
    assert all(r.version == 1 and r.status == "unchanged" for c, r in results.items() if c != "HK")
    assert client.store["labor_laws/HK/_meta/current"]["version"] == 2
    assert "Updated wording" in client.store["labor_laws/HK/rules/minimum_wage"]["summary"]


def test_hash_ignores_layout_reviewers_and_file_notes(tmp_path: Path) -> None:
    before = content_hash(_files()["MY"])
    data = _copy_data(tmp_path)
    path = data / "MY.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["reviewed_by"] = ["Aditya"]
    doc["notes"] = "Reviewed."
    path.write_text(json.dumps(doc, indent=4, ensure_ascii=False) + "\r\n", encoding="utf-8-sig")

    assert content_hash(_files(data)["MY"]) == before


def test_hash_changes_when_a_rule_changes(tmp_path: Path) -> None:
    before = content_hash(_files()["KR"])
    data = _copy_data(tmp_path)
    path = data / "KR.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["rules"]["annual_leave"]["variants"][0]["limits"]["annual_leave_maximum"]["value"] = 26
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    assert content_hash(_files(data)["KR"]) != before


def test_version_continues_from_what_firestore_holds() -> None:
    client = _FakeClient()
    client.store["labor_laws/AU/_meta/current"] = {"version": 5, "content_hash": "old"}

    results = load_labor_laws(client, _files())  # type: ignore[arg-type]

    au = next(r for r in results if r.country == "AU")
    assert au.version == 6 and au.status == "changed"
    assert client.store["labor_laws/AU/_meta/current"]["version"] == 6


def test_stub_files_are_skipped_and_broken_files_reported(tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    (data / "AU.json").write_text("{}\n", encoding="utf-8")
    broken = json.loads((data / "JP.json").read_text(encoding="utf-8"))
    del broken["rules"]["sick_leave"]
    (data / "JP.json").write_text(json.dumps(broken), encoding="utf-8")

    files, skipped, problems = read_country_files(data)

    assert skipped == ["AU"]
    assert "JP" not in files and len(files) == 4
    assert any("JP.json" in p for p in problems) and any("sick_leave" in p for p in problems)


def test_a_broken_file_stops_the_run_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _copy_data(tmp_path)
    (data / "SG.json").write_text('{"country": "SG"}', encoding="utf-8")
    _no_firestore(monkeypatch)

    assert main(["--input-dir", str(data)]) == 1


def test_dry_run_validates_without_touching_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_firestore(monkeypatch)

    assert main(["--dry-run"]) == 0


def test_require_all_fails_while_a_stub_remains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _copy_data(tmp_path)
    (data / "KR.json").write_text("{}\n", encoding="utf-8")
    _no_firestore(monkeypatch)

    assert main(["--input-dir", str(data), "--require-all", "--dry-run"]) == 1
    assert main(["--input-dir", str(data), "--dry-run"]) == 0


def test_only_limits_the_load_to_the_named_countries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClient()
    monkeypatch.setattr(ilo_natlex, "get_firestore_client", lambda: client)

    assert main(["--only", "SG", "JP"]) == 0

    countries = {path.split("/")[1] for path in client.store}
    assert countries == {"SG", "JP"}


def test_writes_go_to_the_requested_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    monkeypatch.setattr(ilo_natlex, "get_firestore_client", lambda: client)

    assert main(["--only", "HK", "--collection", "labor_laws_staging"]) == 0

    assert client.store and all(p.startswith("labor_laws_staging/") for p in client.store)
