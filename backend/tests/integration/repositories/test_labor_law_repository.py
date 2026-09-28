from __future__ import annotations

import os
import uuid

import pytest

from app.repositories.base import get_firestore_client
from app.repositories.labor_law_repo import LaborLawRepository

# Real Firestore reads: only against the emulator (docs/runbooks/NF-P1-001-local-dev-setup.md).
pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
)


def _fake_country() -> str:
    # A country id that cannot collide with the six real ones or another test run.
    return f"ZZ{uuid.uuid4().hex[:6]}"


def test_get_version_and_get_rules_read_what_the_loader_writes() -> None:
    client = get_firestore_client()
    repo = LaborLawRepository(client)
    country = _fake_country()

    client.document(f"labor_laws/{country}").set({"country": country, "name": "Test Country"})
    client.document(f"labor_laws/{country}/_meta/current").set(
        {"version": 2, "content_hash": "abc"}
    )
    client.document(f"labor_laws/{country}/rules/working_hours").set(
        {"country": country, "category": "working_hours", "coverage": "regulated"}
    )
    client.document(f"labor_laws/{country}/rules/minimum_wage").set(
        {"country": country, "category": "minimum_wage", "coverage": "not_regulated"}
    )

    assert repo.get_version(country) == 2
    rules = repo.get_rules(country)
    assert set(rules) == {"working_hours", "minimum_wage"}
    assert rules["working_hours"]["coverage"] == "regulated"


def test_a_country_never_loaded_returns_no_version_and_no_rules() -> None:
    client = get_firestore_client()
    repo = LaborLawRepository(client)
    country = _fake_country()

    assert repo.get_version(country) is None
    assert repo.get_rules(country) == {}
