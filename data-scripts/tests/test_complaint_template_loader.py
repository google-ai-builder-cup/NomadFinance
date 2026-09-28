from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from firebase_admin import firestore  # type: ignore[import-untyped]

from src.config import COMPLAINT_TEMPLATES_DIR
from src.loaders import complaint_templates
from src.loaders.complaint_templates import (
    load_country,
    load_templates,
    main,
    read_country_files,
)
from src.validators.complaint_template import ComplaintTemplateFile
from src.validators.labor_law import COUNTRIES


class _Doc:
    def __init__(self, doc_id: str) -> None:
        self.id = doc_id


class _Ref:
    def __init__(self, client: _FakeClient, path: str) -> None:
        self._client = client
        self.path = path

    def collection(self, name: str) -> _Ref:
        return _Ref(self._client, f"{self.path}/{name}")

    def document(self, doc_id: str) -> _Ref:
        return _Ref(self._client, f"{self.path}/{doc_id}")

    def stream(self) -> list[_Doc]:
        prefix = f"{self.path}/"
        return [
            _Doc(path.removeprefix(prefix))
            for path in self._client.store
            if path.startswith(prefix) and "/" not in path.removeprefix(prefix)
        ]


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
                self._client.store[path] = data
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


def _files(directory: Path = COMPLAINT_TEMPLATES_DIR) -> dict[str, ComplaintTemplateFile]:
    files, problems = read_country_files(directory)
    assert not problems
    return files


def _copy_data(tmp_path: Path) -> Path:
    target = tmp_path / "complaint-templates"
    target.mkdir()
    for path in COMPLAINT_TEMPLATES_DIR.glob("*.json"):
        shutil.copy(path, target / path.name)
    return target


def _no_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise AssertionError("Firestore must not be touched")

    monkeypatch.setattr(complaint_templates, "get_firestore_client", boom)


def test_first_load_writes_a_header_and_one_document_per_type() -> None:
    client = _FakeClient()

    results = load_templates(client, _files())  # type: ignore[arg-type]

    assert [r.country for r in results] == list(COUNTRIES)
    assert all(r.written == 1 and r.removed == 0 for r in results)
    assert len(client.store) == 6 * 2
    for country in COUNTRIES:
        assert client.store[f"complaint_templates/{country}"]["template_count"] == 1
        assert f"complaint_templates/{country}/types/general" in client.store


def test_type_documents_carry_country_type_language_and_schema_version() -> None:
    client = _FakeClient()
    load_templates(client, _files())  # type: ignore[arg-type]

    doc = client.store["complaint_templates/KR/types/general"]

    assert doc["country"] == "KR"
    assert doc["type"] == "general"
    assert doc["schema_version"] == 1
    assert doc["letter_language"] == "ko"
    assert doc["reviewed_on"] == "2026-09-28"
    assert isinstance(doc["channels"], list) and doc["channels"][0]["kind"]


def test_header_uses_a_server_timestamp() -> None:
    client = _FakeClient()
    load_templates(client, _files())  # type: ignore[arg-type]

    header = client.store["complaint_templates/SG"]

    assert header["country"] == "SG"
    assert header["updated_at"] == firestore.SERVER_TIMESTAMP


def test_each_country_is_written_in_one_batch() -> None:
    client = _FakeClient()

    load_templates(client, _files())  # type: ignore[arg-type]

    assert len(client.commits) == 6
    assert all(len(paths) == 2 for paths in client.commits)


def test_rerun_overwrites_in_place_without_duplicates() -> None:
    client = _FakeClient()
    files = _files()
    load_templates(client, files)  # type: ignore[arg-type]

    results = load_templates(client, files)  # type: ignore[arg-type]

    assert all(r.written == 1 and r.removed == 0 for r in results)
    assert len(client.store) == 6 * 2


def test_a_type_removed_from_the_file_is_deleted_in_the_same_batch() -> None:
    client = _FakeClient()
    client.store["complaint_templates/JP/types/old_type"] = {"type": "old_type"}

    result = load_country(client, _files()["JP"])  # type: ignore[arg-type]

    assert result.removed == 1
    assert "complaint_templates/JP/types/old_type" not in client.store
    assert "complaint_templates/JP/types/general" in client.store
    assert len(client.commits) == 1


def test_stale_types_of_another_country_are_left_alone() -> None:
    client = _FakeClient()
    client.store["complaint_templates/SG/types/old_type"] = {"type": "old_type"}

    load_country(client, _files()["JP"])  # type: ignore[arg-type]

    assert "complaint_templates/SG/types/old_type" in client.store


def test_writes_go_to_the_requested_collection() -> None:
    client = _FakeClient()

    load_templates(client, _files(), collection="staging")  # type: ignore[arg-type]

    assert client.store and all(p.startswith("staging/") for p in client.store)


def test_broken_and_mismatched_files_are_reported_not_loaded(tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    (data / "AU.json").write_text("{}", encoding="utf-8")
    kr = json.loads((data / "KR.json").read_text(encoding="utf-8"))
    kr["country"] = "JP"
    (data / "KR.json").write_text(json.dumps(kr), encoding="utf-8")
    (data / "MY.json").write_text("not json", encoding="utf-8")

    files, problems = read_country_files(data)

    assert set(files) == {"SG", "JP", "HK"}
    assert any("AU.json" in p for p in problems)
    assert any("KR.json" in p and "contains country JP" in p for p in problems)
    assert any("MY.json" in p for p in problems)


def test_only_filters_the_files_read(tmp_path: Path) -> None:
    files, problems = read_country_files(_copy_data(tmp_path), only=["SG", "JP"])

    assert set(files) == {"SG", "JP"} and not problems


def test_a_broken_file_stops_the_run_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _copy_data(tmp_path)
    (data / "SG.json").write_text('{"country": "SG"}', encoding="utf-8")
    _no_firestore(monkeypatch)

    assert main(["--input-dir", str(data)]) == 1


def test_an_empty_folder_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_firestore(monkeypatch)

    assert main(["--input-dir", str(tmp_path)]) == 1


def test_dry_run_validates_without_touching_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_firestore(monkeypatch)

    assert main(["--dry-run"]) == 0


def test_require_all_fails_when_a_country_file_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _copy_data(tmp_path)
    (data / "KR.json").unlink()
    _no_firestore(monkeypatch)

    assert main(["--input-dir", str(data), "--require-all", "--dry-run"]) == 1
    assert main(["--input-dir", str(data), "--dry-run"]) == 0


def test_only_limits_the_load_to_the_named_countries(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    monkeypatch.setattr(complaint_templates, "get_firestore_client", lambda: client)

    assert main(["--only", "SG", "JP"]) == 0

    assert {path.split("/")[1] for path in client.store} == {"SG", "JP"}


def test_main_writes_to_the_requested_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    monkeypatch.setattr(complaint_templates, "get_firestore_client", lambda: client)

    assert main(["--only", "HK", "--collection", "complaint_templates_staging"]) == 0

    assert client.store and all(p.startswith("complaint_templates_staging/") for p in client.store)
