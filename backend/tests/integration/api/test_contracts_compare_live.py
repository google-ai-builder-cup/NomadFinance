"""End-to-end: real request through the app to real Gemini; auth faked, rules from the repo's
curated files (the same data NF-P1-018 loads into Firestore), so production is not touched.

Opt-in because it needs GEMINI_API_KEY in .env.local and uses free-tier quota:

    RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_contracts_compare_live.py -v -s

`-s` prints each call's duration and score (NF-P2-004 latency record).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.repositories.labor_law_repo import get_labor_law_repository
from app.schemas.user import AuthenticatedUser

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
)

URL = "/api/v1/contracts/compare"
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "contracts"
CURATED = Path(__file__).resolve().parents[4] / "data-scripts" / "data" / "source" / "labor-laws"


class CuratedFileRepo:
    """The labor-law repository, read from the curated source files instead of Firestore."""

    def get_version(self, country: str) -> int:
        return 1

    def get_rules(self, country: str) -> dict[str, dict[str, Any]]:
        rules: dict[str, dict[str, Any]] = json.loads(
            (CURATED / f"{country}.json").read_text(encoding="utf-8")
        )["rules"]
        return rules


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="live-test")
    app.dependency_overrides[get_labor_law_repository] = CuratedFileRepo
    with TestClient(app) as client:
        yield client


def compare(api: TestClient, fixture: str, country: str, job_type: str) -> dict[str, Any]:
    blocks = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    body = {"blocks": blocks, "host_country": country, "job_type": job_type}
    started = time.perf_counter()
    response = api.post(URL, json=body)
    result: dict[str, Any] = response.json()
    print(
        f"\n[{fixture}] {response.status_code} in {time.perf_counter() - started:.1f}s "
        f"score={result.get('health_score')} level={result.get('risk_level')} "
        f"counts={result.get('clause_counts')}"
    )
    assert response.status_code == 200, result
    return result


def clause_with(result: dict[str, Any], words: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = [
        c for c in result["clauses"] if words.lower() in c["text"].lower()
    ]
    assert matches, f"no clause mentions {words!r}"
    return matches[0]


def test_singapore_sample_is_danger_on_the_rules_it_breaks(api: TestClient) -> None:
    result = compare(api, "sample_contract_sg.blocks.json", "SG", "domestic_worker")

    assert result["risk_level"] == "danger"
    # One rest day a month; the SG rule requires one in every 7 days.
    rest_days = clause_with(result, "rest day")
    assert rest_days["risk"] == "danger"
    assert rest_days["law_reference"] and "Work Passes" in rest_days["law_reference"]
    # The curated SG rule covers the work permit and visit pass, and says it does not mention
    # the passport itself: without a rule, the passport clause can be flagged, never "illegal".
    assert clause_with(result, "passport for safekeeping")["risk"] == "caution"
    assert result["unassessed_block_ids"] == []


def test_malaysian_photo_in_indonesian_is_checked_against_malaysian_law(api: TestClient) -> None:
    result = compare(api, "sample_contract_my_id.blocks.json", "MY", "plantation_worker")

    assert result["risk_level"] == "danger"
    assert clause_with(result, "Pasport")["risk"] == "danger"
    assert clause_with(result, "yuran agensi")["risk"] != "safe"
    # Explanations are written in English, whatever the contract's language.
    assert "passport" in clause_with(result, "Pasport")["explanation"].lower()


def test_fair_contract_gets_no_danger(api: TestClient) -> None:
    result = compare(api, "fair_contract_sg.blocks.json", "SG", "domestic_worker")

    assert result["clause_counts"]["danger"] == 0
    assert result["risk_level"] in {"safe", "caution"}
    assert clause_with(result, "keeps her own passport")["risk"] == "safe"
