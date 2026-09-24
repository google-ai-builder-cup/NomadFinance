from __future__ import annotations

import os
import uuid

import pytest

from app.repositories.base import FirestoreRepository

# Real Firestore read/write, run against the Firebase Emulator only. Skipped unless
# FIRESTORE_EMULATOR_HOST is set (see docs/runbooks/NF-P1-001-local-dev-setup.md
# section 6) so `pytest` still passes on a machine without the emulator running.
pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
)


class _SmokeTestRepository(FirestoreRepository):
    collection_name = "_nf_p1_005_smoke_tests"


def test_write_then_read_then_delete_round_trips_through_firestore() -> None:
    repo = _SmokeTestRepository()
    doc_id = f"smoke-{uuid.uuid4()}"

    assert repo.get(doc_id) is None

    repo.set(doc_id, {"pillar": "backend-firebase-admin", "ok": True})
    assert repo.get(doc_id) == {"pillar": "backend-firebase-admin", "ok": True}

    repo.set(doc_id, {"ok": False}, merge=True)
    assert repo.get(doc_id) == {"pillar": "backend-firebase-admin", "ok": False}

    repo.delete(doc_id)
    assert repo.get(doc_id) is None
