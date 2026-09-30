from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest

from app.repositories.base import get_firestore_client
from app.repositories.radar_repo import RadarRepository
from app.schemas.radar import RadarReport, RadarValidation

pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
)


def _repo() -> RadarRepository:
    # A throwaway collection name, so a run never touches (or trusts) real documents.
    repo = RadarRepository(get_firestore_client())
    repo.collection_name = f"radar_reports_test_{uuid.uuid4().hex[:8]}"
    return repo


def _report(**over: object) -> RadarReport:
    values: dict[str, object] = {
        "entity_type": "employer",
        "entity_name": "Acme Pte Ltd",
        "entity_slug": "acme-pte-ltd",
        "violation_type": "passport_retention",
        "host_country": "SG",
        "description": "The employer keeps the worker's passport.",
        "language": "en",
        "cluster_id": "placeholder",
        "source": "contract_signal",
        "validation": RadarValidation(
            spam_score=0.0, category_confidence=1.0, model="contract_shield"
        ),
        "created_at": datetime.now(UTC),
    }
    return RadarReport.model_validate(values | over)


def test_new_report_id_gives_a_fresh_id_each_time() -> None:
    repo = _repo()

    ids = {repo.new_report_id() for _ in range(5)}

    assert len(ids) == 5
    assert all(isinstance(i, str) and i for i in ids)


def test_a_written_report_is_read_back_with_a_real_timestamp() -> None:
    repo = _repo()
    report_id = repo.new_report_id()
    report = _report(cluster_id=report_id)

    repo.create_report(report_id, report)
    stored = repo.get(report_id)

    assert stored is not None
    assert stored["entity_name"] == "Acme Pte Ltd"
    assert stored["source"] == "contract_signal"
    assert stored["created_at"].tzinfo is not None  # a real Firestore Timestamp, not a string


def test_a_null_field_is_never_written() -> None:
    repo = _repo()
    report_id = repo.new_report_id()
    report = _report(cluster_id=report_id, corridor_id=None, reporter_hash=None)

    repo.create_report(report_id, report)
    stored = repo.get(report_id)

    assert stored is not None
    assert "corridor_id" not in stored
    assert "reporter_hash" not in stored


def test_two_reports_from_the_same_new_id_call_never_collide() -> None:
    repo = _repo()
    first_id, second_id = repo.new_report_id(), repo.new_report_id()
    repo.create_report(first_id, _report(cluster_id=first_id, violation_type="passport_retention"))
    repo.create_report(second_id, _report(cluster_id=second_id, violation_type="illegal_deduction"))

    first, second = repo.get(first_id), repo.get(second_id)

    assert first is not None and second is not None
    assert first["violation_type"] != second["violation_type"]
