"""Shared pieces of the Scam Analyzer's similar-scam tests (NF-SA-010).

`FakeFinder` stands in for `SimilarScamFinder` where a test is about the endpoint, not about the
search: it returns what it was given and keeps what it was asked. The search itself is tested
with fake repositories in `tests/unit/services/test_scam_retrieval.py`.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from app.schemas.scam import CorridorId
from app.services.scam.retrieval import NOTHING_FOUND, Retrieval, SimilarMatch


class FakeFinder:
    def __init__(self, retrieval: Retrieval = NOTHING_FOUND) -> None:
        self._retrieval = retrieval
        self.calls: list[dict[str, Any]] = []

    async def find(
        self, redacted_text: str, corridor_id: CorridorId | None, known_types: Collection[str]
    ) -> Retrieval:
        self.calls.append(
            {"text": redacted_text, "corridor_id": corridor_id, "known_types": set(known_types)}
        )
        return self._retrieval


def retrieval_from_mock(body: dict[str, Any]) -> Retrieval:
    """What the search would have found for the mock's message."""
    return Retrieval(
        similar=[
            SimilarMatch(s["source"], f"mock-{i}", s["scam_type"], s["score"])
            for i, s in enumerate(body["similar"])
        ],
        corridor_report_count=body["corridor_report_count"],
    )
