from __future__ import annotations

import os
import uuid
from datetime import timedelta

import pytest

from app.repositories.base import get_firestore_client
from app.repositories.contract_repo import ContractRepository

# Real Firestore writes: only against the emulator (docs/runbooks/NF-P1-001-local-dev-setup.md).
pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
)


@pytest.fixture
def repo() -> ContractRepository:
    return ContractRepository(get_firestore_client())


@pytest.fixture
def uid() -> str:
    # A user no other test run can collide with.
    return f"test-{uuid.uuid4().hex[:10]}"


def _upload(repo: ContractRepository, uid: str, content_hash: str = "abc") -> str:
    contract_id = repo.new_id(uid)
    repo.save_upload(
        uid,
        contract_id,
        {"status": "uploaded", "content_hash": content_hash, "legibility": "good"},
        {
            "blocks": [{"page": 1, "kind": "clause", "number": "1", "text": "Pay."}],
            "text": "1 Pay.",
        },
    )
    return contract_id


def test_upload_writes_the_contract_and_its_extraction(repo: ContractRepository, uid: str) -> None:
    contract_id = _upload(repo, uid)

    contract = repo.get(uid, contract_id)
    assert contract is not None
    assert contract["status"] == "uploaded"
    assert contract["schema_version"] == 1
    assert contract["created_at"] is not None
    extraction = repo.get_extraction(uid, contract_id)
    assert extraction is not None and extraction["text"] == "1 Pay."
    assert len(contract_id) == 20 and contract_id.isalnum()


def test_find_by_hash_only_finds_this_users_file(repo: ContractRepository, uid: str) -> None:
    contract_id = _upload(repo, uid, content_hash="hash-1")
    _upload(repo, f"{uid}-other", content_hash="hash-2")

    found = repo.find_by_hash(uid, "hash-1")
    assert found is not None and found[0] == contract_id
    assert repo.find_by_hash(uid, "hash-2") is None


def test_update_with_none_removes_the_field(repo: ContractRepository, uid: str) -> None:
    contract_id = _upload(repo, uid)
    repo.update(uid, contract_id, {"step": "compare", "error": {"step": "law", "code": "x"}})

    repo.update(uid, contract_id, {"step": None, "error": None, "status": "completed"})

    contract = repo.get(uid, contract_id)
    assert contract is not None
    assert contract["status"] == "completed"
    assert "step" not in contract and "error" not in contract


def test_a_running_analysis_blocks_a_second_claim_until_stale(
    repo: ContractRepository, uid: str
) -> None:
    contract_id = _upload(repo, uid)

    assert repo.claim_for_analysis(uid, contract_id, timedelta(minutes=16)) is True
    contract = repo.get(uid, contract_id)
    assert contract is not None and (contract["status"], contract["step"]) == (
        "processing",
        "detect",
    )
    assert repo.claim_for_analysis(uid, contract_id, timedelta(minutes=16)) is False
    # An analysis whose request died is taken over once it counts as stale.
    assert repo.claim_for_analysis(uid, contract_id, timedelta(seconds=0)) is True


def test_reports_are_stored_per_language_and_listed_once(
    repo: ContractRepository, uid: str
) -> None:
    contract_id = _upload(repo, uid)

    repo.save_report(uid, contract_id, {"language": "en", "summary": "English."})
    repo.save_report(uid, contract_id, {"language": "hi", "summary": "Hindi."})
    repo.save_report(uid, contract_id, {"language": "hi", "summary": "Hindi, again."})

    report = repo.get_report(uid, contract_id, "hi")
    assert report is not None and report["summary"] == "Hindi, again."
    contract = repo.get(uid, contract_id)
    assert contract is not None and sorted(contract["report_languages"]) == ["en", "hi"]
    assert repo.get_report(uid, contract_id, "bn") is None
