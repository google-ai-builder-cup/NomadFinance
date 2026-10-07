from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.repositories.scam_taxonomy_repo import ScamTaxonomyRepository


def _doc(doc_id: str, data: dict[str, Any]) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.to_dict.return_value = data
    return doc


def _repo(
    docs: list[MagicMock], meta: dict[str, Any] | None
) -> tuple[ScamTaxonomyRepository, MagicMock, MagicMock]:
    client = MagicMock()
    collection = client.collection.return_value
    snapshot = collection.document.return_value.get.return_value
    snapshot.exists = meta is not None
    snapshot.to_dict.return_value = meta
    stream = collection.where.return_value.stream
    stream.return_value = docs
    return ScamTaxonomyRepository(client), stream, snapshot


DOCS = [
    _doc("urgency", {"kind": "tactic", "order": 1}),
    _doc("lottery", {"kind": "type", "order": 2}),
    _doc("fake_job_offer", {"kind": "type", "order": 1}),
]


def test_types_and_tactics_are_split_by_kind_and_ordered() -> None:
    repo, _, _ = _repo(list(DOCS), {"version": 3})

    taxonomy = repo.get_taxonomy()

    assert taxonomy is not None
    assert taxonomy.version == 3
    assert list(taxonomy.types) == ["fake_job_offer", "lottery"]
    assert list(taxonomy.tactics) == ["urgency"]


def test_same_version_is_read_from_firestore_once() -> None:
    repo, stream, _ = _repo(list(DOCS), {"version": 3})

    assert repo.get_taxonomy() is repo.get_taxonomy()
    assert stream.call_count == 1


def test_a_new_version_reads_the_taxonomy_again() -> None:
    repo, stream, snapshot = _repo(list(DOCS), {"version": 3})

    repo.get_taxonomy()
    snapshot.to_dict.return_value = {"version": 4}
    taxonomy = repo.get_taxonomy()

    assert taxonomy is not None and taxonomy.version == 4
    assert stream.call_count == 2


def test_never_loaded_is_none() -> None:
    repo, stream, _ = _repo([], None)

    assert repo.get_taxonomy() is None
    stream.assert_not_called()


def test_a_taxonomy_with_no_tactics_is_not_usable_and_not_cached() -> None:
    repo, stream, _ = _repo([_doc("lottery", {"kind": "type", "order": 1})], {"version": 1})

    assert repo.get_taxonomy() is None
    repo.get_taxonomy()

    assert stream.call_count == 2
