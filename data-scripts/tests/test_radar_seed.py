from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.config import RADAR_SEED_FILE
from src.loaders import radar_seed
from src.loaders.radar_seed import entity_documents, load_seed, main, report_document
from src.validators.radar_seed import CORRIDOR_IDS, SeedFile, load

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


class _Doc:
    def __init__(self, doc_id: str, data: dict[str, Any]) -> None:
        self.id = doc_id
        self._data = data

    def get(self, field: str) -> Any:
        return self._data.get(field)


class _Ref:
    def __init__(self, client: _FakeClient, path: str) -> None:
        self.client = client
        self.path = path

    def document(self, doc_id: str) -> _Ref:
        return _Ref(self.client, f"{self.path}/{doc_id}")

    def where(self, *, filter: Any) -> _Query:  # noqa: A002 - mirrors the SDK keyword
        return _Query(self, filter)


class _Query:
    def __init__(self, ref: _Ref, flt: Any) -> None:
        self._ref = ref
        self._flt = flt

    def stream(self) -> list[_Doc]:
        prefix = f"{self._ref.path}/"
        return [
            _Doc(path.removeprefix(prefix), data)
            for path, data in self._ref.client.store.items()
            if path.startswith(prefix) and data.get(self._flt.field_path) == self._flt.value
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
        self._client.commits += 1
        for op, path, data in self._ops:
            if op == "set" and data is not None:
                self._client.store[path] = data
            else:
                self._client.store.pop(path, None)


class _FakeClient:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.commits = 0

    def collection(self, name: str) -> _Ref:
        return _Ref(self, name)

    def batch(self) -> _Batch:
        return _Batch(self)


@pytest.fixture
def seed() -> SeedFile:
    return load()


def test_committed_file_is_valid_and_covers_every_corridor(seed: SeedFile) -> None:
    assert 15 <= len(seed.reports) <= 20
    assert {r.corridor_id for r in seed.reports} >= set(CORRIDOR_IDS)


def test_profiles_follow_the_backend_rules(seed: SeedFile) -> None:
    entities = entity_documents(seed, NOW)
    bayanihan = entities["bayanihan-overseas-recruitment"]
    assert bayanihan["incident_count"] == 5
    assert bayanihan["risk_level"] == "high"
    assert bayanihan["community_rating"] == 2.5
    merlion = entities["merlion-quicksend"]
    # seed_02 repeats seed_01's incident: 4 reports, 3 incidents
    assert (merlion["report_count"], merlion["incident_count"]) == (4, 3)
    assert entities["lantau-bay-household"]["community_rating"] is None
    assert entities["lantau-bay-household"]["flagged"] is False
    assert sum(e["report_count"] for e in entities.values()) == len(seed.reports)


def test_report_document_is_marked_seed_and_dated_from_now(seed: SeedFile) -> None:
    doc = report_document(seed.reports[0], NOW)
    assert doc["source"] == "seed"
    assert "reporter_hash" not in doc
    assert (NOW - doc["created_at"]).total_seconds() == seed.reports[0].hours_ago * 3600


def test_load_is_idempotent_and_removes_stale_seed_reports(seed: SeedFile) -> None:
    client = _FakeClient()
    client.store["radar_reports/seed_old"] = {"source": "seed", "entity_slug": "gone"}
    client.store["radar_reports/real_1"] = {"source": "user", "entity_slug": "elsewhere"}

    assert load_seed(client, seed, NOW) == (len(seed.reports), 8, 1)  # type: ignore[arg-type]
    first = dict(client.store)
    load_seed(client, seed, NOW)  # type: ignore[arg-type]

    assert client.store == first
    assert "radar_reports/seed_old" not in client.store
    assert "radar_reports/real_1" in client.store
    assert client.commits == 2  # one atomic batch per run


def test_profile_with_real_reports_is_left_alone(seed: SeedFile) -> None:
    client = _FakeClient()
    client.store["radar_reports/real_1"] = {"source": "user", "entity_slug": "merlion-quicksend"}
    client.store["radar_entities/merlion-quicksend"] = {"report_count": 99}

    _, written, _ = load_seed(client, seed, NOW)  # type: ignore[arg-type]

    assert written == 7
    assert client.store["radar_entities/merlion-quicksend"] == {"report_count": 99}


def _write_variant(tmp_path: Path, mutate: Any) -> Path:
    raw = json.loads(RADAR_SEED_FILE.read_text(encoding="utf-8"))
    mutate(raw["reports"])
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_validator_rejects_a_cluster_across_entities(tmp_path: Path) -> None:
    path = _write_variant(tmp_path, lambda r: r[1].update(cluster_id="seed_05"))
    with pytest.raises(ValidationError, match="same entity"):
        load(path)


def test_validator_rejects_an_unknown_corridor(tmp_path: Path) -> None:
    path = _write_variant(tmp_path, lambda r: r[0].update(corridor_id="SG-XX"))
    with pytest.raises(ValidationError, match="corridor_id"):
        load(path)


def test_validator_rejects_too_few_reports(tmp_path: Path) -> None:
    path = _write_variant(tmp_path, lambda r: r.__delitem__(slice(10, None)))
    with pytest.raises(ValidationError, match="expected 15-20"):
        load(path)


def test_main_dry_run_never_touches_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise AssertionError("dry run must not open a Firestore client")

    monkeypatch.setattr(radar_seed, "get_firestore_client", boom)
    assert main(["--dry-run"]) == 0


def test_main_stops_on_a_bad_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"reports": []}', encoding="utf-8")
    assert main(["--input", str(bad), "--dry-run"]) == 1
