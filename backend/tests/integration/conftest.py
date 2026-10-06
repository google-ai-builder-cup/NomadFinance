"""Fixtures for tests that run against the Firestore emulator (NF-F0-014).

Existing emulator tests skip themselves with their own `skipif` and make up random ids so they
do not collide. New ones take these fixtures instead:

    def test_something(clean_firestore, seed_documents):
        seed_documents({"users/u1": {"name": "Priya"}, "users/u1/income/i1": {"amount": 1}})
        ...

Everything here refuses to touch anything that is not a local emulator: the emulator address must
be on this machine, and the clearing goes through the emulator's own endpoint, which a real
Firestore does not have.
"""

from __future__ import annotations

import importlib
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from google.cloud.firestore import Client

from app.repositories.base import get_firestore_client

_DATA_SCRIPTS = Path(__file__).resolve().parents[3] / "data-scripts"
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}

# The five hosts whose curated labor law and complaint templates the end-to-end tests need.
REFERENCE_COUNTRIES = ("SG", "AU", "KR", "MY", "JP")


@pytest.fixture(scope="session")
def emulator_host() -> str:
    """The emulator's `host:port`; the test is skipped without one, and fails if it is not local."""
    host = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if not host:
        pytest.skip("Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)")
    name = host.rsplit(":", 1)[0]
    if name not in _LOCAL_HOSTS:
        pytest.fail(f"FIRESTORE_EMULATOR_HOST is {host!r}: refusing to run against a remote host")
    return host


@pytest.fixture(scope="session")
def firestore_client(emulator_host: str) -> Client:
    """The app's own Firestore client, pointed at the emulator."""
    return get_firestore_client()


@pytest.fixture
def clean_firestore(emulator_host: str, firestore_client: Client) -> Client:
    """The emulator with every document deleted, so a test starts from nothing.

    Tests that need curated reference data ask for `seeded_reference_data` after this one; it
    loads again whatever the clearing removed.
    """
    url = (
        f"http://{emulator_host}/emulator/v1/projects/{firestore_client.project}"
        "/databases/(default)/documents"
    )
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="DELETE"), timeout=10).close()
    except urllib.error.URLError as exc:
        pytest.fail(f"could not clear the Firestore emulator at {emulator_host}: {exc}")
    return firestore_client


@pytest.fixture
def seed_documents(firestore_client: Client) -> Callable[[Mapping[str, dict[str, Any]]], None]:
    """Write documents by path, e.g. `{"users/u1/income/i1": {...}}`. Replaces what is there."""

    def seed(documents: Mapping[str, dict[str, Any]]) -> None:
        for path, data in documents.items():
            firestore_client.document(path).set(data)

    return seed


def _country_ready(client: Client, country: str) -> bool:
    return bool(
        client.document(f"labor_laws/{country}/_meta/current").get().exists
        and client.document(f"complaint_templates/{country}").get().exists
    )


@pytest.fixture
def seeded_reference_data(firestore_client: Client) -> tuple[str, ...]:
    """The curated labor law and complaint templates for SG, AU, KR, MY and JP, loaded if missing.

    These are the real files in `data-scripts/data/source/`, written by the same loader functions
    `python -m src.loaders.ilo_natlex` uses, so the tests exercise the real per-country data. It
    is safe to ask for many times: a country already there is left alone, and the loaders do not
    raise a version for unchanged content.
    """
    missing = [c for c in REFERENCE_COUNTRIES if not _country_ready(firestore_client, c)]
    if missing:
        sys.path.insert(0, str(_DATA_SCRIPTS))
        try:
            config = importlib.import_module("src.config")
            natlex = importlib.import_module("src.loaders.ilo_natlex")
            templates = importlib.import_module("src.loaders.complaint_templates")
        finally:
            sys.path.remove(str(_DATA_SCRIPTS))
        laws, _stubs, law_problems = natlex.read_country_files(config.LABOR_LAWS_DIR, missing)
        files, template_problems = templates.read_country_files(
            config.COMPLAINT_TEMPLATES_DIR, missing
        )
        assert not law_problems and not template_problems, (law_problems, template_problems)
        natlex.load_labor_laws(firestore_client, laws)
        templates.load_templates(firestore_client, files)
    return REFERENCE_COUNTRIES
