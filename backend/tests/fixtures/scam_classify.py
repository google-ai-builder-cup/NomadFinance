"""Shared pieces of the Scam Analyzer's classify tests (NF-SA-007).

The taxonomy is the real curated one from `data-scripts/data/source/scam-taxonomy/`, so a test
fails if an id it uses is renamed. The four cases are the analyze mocks of `docs/mocks/scam/`:
the model's answer is rebuilt from each mock's verdict, so the endpoint is checked against the
very JSON the frontend builds on.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.repositories.scam_taxonomy_repo import ScamTaxonomy

REPO = Path(__file__).resolve().parents[3]
MOCKS = REPO / "docs" / "mocks" / "scam"
TAXONOMY_DIR = REPO / "data-scripts" / "data" / "source" / "scam-taxonomy"

MOCK_FILES = {
    "high": "analyze-01-high-risk.json",
    "medium": "analyze-02-medium-risk.json",
    "low": "analyze-03-low-risk.json",
    "benign": "analyze-04-benign.json",
}


def load_taxonomy(version: int = 1) -> ScamTaxonomy:
    def entries(name: str) -> dict[str, dict[str, Any]]:
        document = json.loads((TAXONOMY_DIR / name).read_text(encoding="utf-8"))
        return {
            doc_id: {"kind": document["kind"], **data}
            for doc_id, data in document["entries"].items()
        }

    return ScamTaxonomy(
        version=version, types=entries("types.json"), tactics=entries("tactics.json")
    )


def load_mock_body(case: str) -> dict[str, Any]:
    mock = json.loads((MOCKS / MOCK_FILES[case]).read_text(encoding="utf-8"))
    body: dict[str, Any] = mock["body"]
    return body


def model_answer(body: dict[str, Any]) -> dict[str, Any]:
    """What the classifier model would have returned for the mock's message."""
    details = body["details"]
    amount = details.get("amount_requested") or {}
    return {
        **body["verdict"],
        "message_language": body["message_language"],
        "details": {
            "claimed_identity": details.get("claimed_identity"),
            "contact_channel": details.get("contact_channel"),
            "payment_requested": details.get("payment_requested"),
            "amount": amount.get("amount"),
            "currency": amount.get("currency"),
            "deadline_stated": details.get("deadline_stated"),
        },
    }


def classify_recording(answer: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "structured", "response": answer}
