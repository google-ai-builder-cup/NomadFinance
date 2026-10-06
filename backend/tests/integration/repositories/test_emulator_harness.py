"""Sample tests for the emulator fixtures (NF-F0-014): copy one for a new repository test."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from google.cloud.firestore import Client

from app.repositories.labor_law_repo import LaborLawRepository


def test_a_test_starts_from_an_empty_database_and_seeds_what_it_needs(
    clean_firestore: Client,
    seed_documents: Callable[[Mapping[str, dict[str, Any]]], None],
) -> None:
    seed_documents(
        {
            "users/u1": {"preferred_language": "hi"},
            "users/u1/income/i1": {"amount": 650, "currency": "SGD"},
        }
    )

    income = [doc.to_dict() for doc in clean_firestore.collection("users/u1/income").stream()]

    assert income == [{"amount": 650, "currency": "SGD"}]
    assert [doc.id for doc in clean_firestore.collection("users").stream()] == ["u1"]


def test_clearing_removes_what_an_earlier_test_left(clean_firestore: Client) -> None:
    # The test above wrote users/u1; this one starts clean again.
    assert list(clean_firestore.collection("users").stream()) == []


def test_the_real_curated_data_is_loaded_for_the_five_countries(
    clean_firestore: Client, seeded_reference_data: tuple[str, ...]
) -> None:
    repo = LaborLawRepository(clean_firestore)

    for country in seeded_reference_data:
        assert repo.get_version(country) is not None
        assert clean_firestore.document(f"complaint_templates/{country}").get().exists
    assert len(repo.get_rules("SG")) == 15


def test_asking_for_the_data_again_leaves_it_unchanged(
    firestore_client: Client, seeded_reference_data: tuple[str, ...]
) -> None:
    before = LaborLawRepository(firestore_client).get_version("SG")

    # A second ask finds every country present and writes nothing.
    assert before == LaborLawRepository(firestore_client).get_version("SG")
