from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.repositories.labor_law_repo import LaborLawRepository


def _doc(doc_id: str, data: dict[str, Any]) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.to_dict.return_value = data
    return doc


def _repo(rules: list[MagicMock]) -> tuple[LaborLawRepository, MagicMock]:
    client = MagicMock()
    stream = client.collection.return_value.document.return_value.collection.return_value.stream
    stream.return_value = rules
    return LaborLawRepository(client), stream


def test_same_version_is_read_from_firestore_once() -> None:
    repo, stream = _repo([_doc("working_hours", {"coverage": "regulated"})])

    first = repo.get_rules("SG", 3)
    second = repo.get_rules("SG", 3)

    assert first == second == {"working_hours": {"coverage": "regulated"}}
    assert stream.call_count == 1


def test_a_new_version_reads_the_rules_again() -> None:
    repo, stream = _repo([_doc("working_hours", {"coverage": "regulated"})])

    repo.get_rules("SG", 3)
    repo.get_rules("SG", 4)

    assert stream.call_count == 2


def test_without_a_version_nothing_is_cached() -> None:
    repo, stream = _repo([_doc("working_hours", {"coverage": "regulated"})])

    repo.get_rules("SG")
    repo.get_rules("SG")

    assert stream.call_count == 2


def test_a_caller_changing_its_copy_does_not_change_the_cache() -> None:
    repo, _ = _repo([_doc("working_hours", {"coverage": "regulated"})])

    repo.get_rules("SG", 3)["working_hours"]["coverage"] = "changed"

    assert repo.get_rules("SG", 3)["working_hours"]["coverage"] == "regulated"


def test_a_country_with_no_rules_is_not_cached() -> None:
    repo, stream = _repo([])

    assert repo.get_rules("SG", 3) == {}
    repo.get_rules("SG", 3)

    assert stream.call_count == 2
