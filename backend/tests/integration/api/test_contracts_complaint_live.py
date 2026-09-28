"""End-to-end: real request through the app to real Gemini; auth faked, templates read from the
repo's curated files (the same data the data-scripts loader writes to Firestore), so
production is not touched.

Opt-in because it needs GEMINI_API_KEY in .env.local and uses quota (5 reasoning calls):

    RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_contracts_complaint_live.py -v -s

`-s` prints each call's duration and the letters, for a person to read (NF-P2-006).
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.repositories.complaint_template_repo import get_complaint_template_repository
from app.schemas.user import AuthenticatedUser

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
)

URL = "/api/v1/contracts/complaint"
CURATED = (
    Path(__file__).resolve().parents[4] / "data-scripts" / "data" / "source" / "complaint-templates"
)


class CuratedFileRepo:
    """The template repository, read from the curated source files instead of Firestore."""

    def get_template(self, country: str, template_type: str) -> dict[str, Any] | None:
        file = json.loads((CURATED / f"{country}.json").read_text(encoding="utf-8"))
        template: dict[str, Any] = file["types"][template_type]
        return template | {"country": country, "type": template_type}


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="live-test")
    app.dependency_overrides[get_complaint_template_repository] = CuratedFileRepo
    with TestClient(app) as client:
        yield client


def _clause(
    index: int, text: str, category: str, reference: str | None, why: str
) -> dict[str, Any]:
    return {
        "index": index,
        "number": str(index),
        "page": 1,
        "text": text,
        "category": category,
        "risk": "danger",
        "law_reference": reference,
        "explanation": why,
        "recommendation": "Ask for this term to be removed.",
        "block_ids": [index],
    }


PASSPORT = _clause(
    1,
    "The Employer shall keep the Worker's passport for safekeeping during the contract.",
    "passport_retention",
    "Passports Act, s. 47",
    "The employer may not keep your passport; only you may hold it.",
)
DEDUCTION = _clause(
    2,
    "The Employer may deduct up to 40% of the monthly salary for food and lodging.",
    "salary_deductions",
    None,
    "A deduction this large is above what the law allows for food and lodging.",
)
SAFE = _clause(3, "Salary is paid monthly.", "salary_payment", "Some Act, s. 1", "Fine.") | {
    "risk": "safe",
    "recommendation": None,
}
FACTS = {"employer_name": "Acme Pte Ltd", "salary_amount": 650, "salary_currency": "SGD"}


def complain(api: TestClient, country: str, language: str) -> dict[str, Any]:
    body = {
        "host_country": country,
        "clauses": [PASSPORT, DEDUCTION, SAFE],
        "contract_facts": FACTS,
        "worker_language": language,
    }
    started = time.perf_counter()
    response = api.post(URL, json=body)
    result: dict[str, Any] = response.json()
    elapsed = time.perf_counter() - started
    print(f"\n[{country} -> {language}] {response.status_code} in {elapsed:.1f}s")
    print(result.get("letter_text"))
    print("--- worker copy ---")
    print(result.get("worker_copy"))
    assert response.status_code == 200, result
    return result


def check_letter(result: dict[str, Any], authority_words: str) -> None:
    letter = result["letter_text"]
    assert "{{" not in letter and "}}" not in letter
    assert authority_words in letter
    assert "[" in letter, "the worker's own details should be left as bracketed blanks"
    assert "Acme Pte Ltd" in letter
    assert re.search(r"40\s?%|40 percent|４０", letter), "the 40% deduction should be quoted"
    assert result["violation_count"] == 2
    assert "Salary is paid monthly" not in letter, "a safe term is not a violation"


def test_singapore_letter_in_english_with_a_hindi_copy(api: TestClient) -> None:
    result = complain(api, "SG", "hi")

    check_letter(result, "Manpower")
    assert result["letter_language"] == "en"
    assert re.search(r"[ऀ-ॿ]", result["worker_copy"]), "the copy should be in Hindi"


def test_singapore_letter_for_an_english_reader_has_no_copy(api: TestClient) -> None:
    result = complain(api, "SG", "en")

    check_letter(result, "Manpower")
    assert result["worker_copy"] is None


def test_korean_letter_with_a_nepali_copy(api: TestClient) -> None:
    result = complain(api, "KR", "ne")

    assert result["letter_language"] == "ko"
    assert re.search(r"[가-힯]", result["letter_text"]), "the letter should be in Korean"
    assert "{{" not in result["letter_text"] and "[" in result["letter_text"]
    assert re.search(r"[ऀ-ॿ]", result["worker_copy"]), "the copy should be in Nepali"
    assert "Acme Pte Ltd" in result["letter_text"]


def test_malaysian_letter_in_malay_with_an_indonesian_copy(api: TestClient) -> None:
    result = complain(api, "MY", "id")

    assert result["letter_language"] == "ms"
    assert "{{" not in result["letter_text"] and "[" in result["letter_text"]
    assert "Acme Pte Ltd" in result["letter_text"]
    assert result["worker_copy"] and "{{" not in result["worker_copy"]


def test_japanese_letter_with_an_english_copy(api: TestClient) -> None:
    result = complain(api, "JP", "en")

    assert result["letter_language"] == "ja"
    assert re.search(r"[぀-ヿ一-鿿]", result["letter_text"])
    assert "{{" not in result["letter_text"] and "[" in result["letter_text"]
    assert result["worker_copy"] and "Acme Pte Ltd" in result["worker_copy"]
