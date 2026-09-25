from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from firebase_admin import firestore  # type: ignore[import-untyped]
from pydantic import ValidationError

from src.config import CORRIDORS, RPW_OUTPUT_FILE
from src.loaders.corridors import _document_payload, load_corridor_file, load_corridors


class _FakeDocument:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._store = store
        self._id = doc_id

    def set(self, data: dict[str, Any]) -> None:
        self._store[self._id] = data


class _FakeCollection:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def document(self, doc_id: str) -> _FakeDocument:
        return _FakeDocument(self._store, doc_id)


class _FakeClient:
    """Stand-in for google.cloud.firestore.Client; enough surface for load_corridors."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self.collections.setdefault(name, {}))


def test_load_corridors_writes_one_document_per_corridor_with_added_fields() -> None:
    output = load_corridor_file(RPW_OUTPUT_FILE)
    client = _FakeClient()

    written = load_corridors(output, client)  # type: ignore[arg-type]

    assert written == len(CORRIDORS)
    docs = client.collections["corridors"]
    assert set(docs) == {c.corridor_id for c in CORRIDORS}
    sg_ph = docs["SG-PH"]
    assert sg_ph["provider_count"] == len(sg_ph["providers"])
    assert sg_ph["source"] == {
        "name": output.source.name,
        "url": output.source.url,
        "attribution": output.source.attribution,
    }
    assert sg_ph["loaded_at"] == firestore.SERVER_TIMESTAMP


def test_load_corridors_is_idempotent_same_ids_replaced_not_duplicated() -> None:
    output = load_corridor_file(RPW_OUTPUT_FILE)
    client = _FakeClient()

    load_corridors(output, client)  # type: ignore[arg-type]
    load_corridors(output, client)  # type: ignore[arg-type]

    assert len(client.collections["corridors"]) == len(CORRIDORS)


def test_load_corridors_writes_to_the_requested_collection() -> None:
    output = load_corridor_file(RPW_OUTPUT_FILE)
    client = _FakeClient()

    load_corridors(output, client, collection="corridors_staging")  # type: ignore[arg-type]

    assert "corridors" not in client.collections
    assert len(client.collections["corridors_staging"]) == len(CORRIDORS)


def test_document_payload_carries_only_the_public_source_fields() -> None:
    output = load_corridor_file(RPW_OUTPUT_FILE)
    doc = output.corridors[0]

    payload = _document_payload(output.source, doc)

    assert payload["corridor_id"] == doc.corridor_id
    assert set(payload["source"]) == {"name", "url", "attribution"}
    assert payload["loaded_at"] == firestore.SERVER_TIMESTAMP


def test_load_corridor_file_rejects_a_file_that_fails_the_schema(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "a corridor file"}', encoding="utf-8")

    with pytest.raises(ValidationError):
        load_corridor_file(bad)
