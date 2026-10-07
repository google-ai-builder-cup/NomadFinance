from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import pytest
from google.api_core.exceptions import FailedPrecondition

from app.integrations.gemini import GeminiRateLimitError, GeminiUnavailableError
from app.repositories.radar_repo import SimilarReport
from app.repositories.scam_pattern_repo import ScamPatternRepository, SimilarPattern
from app.services.scam import retrieval
from app.services.scam.retrieval import (
    EMBED_OPERATION,
    NOTHING_FOUND,
    PATTERN_MIN_SCORE,
    PATTERNS_FETCHED,
    REPORT_MIN_SCORE,
    REPORTS_FETCHED,
    SimilarScamFinder,
)

pytestmark = pytest.mark.anyio

TYPES = {"fake_job_offer", "illegal_recruitment_fee", "lottery", "loan_app_trap", "other_scam"}
VECTOR = [0.1] * 768
TEXT = "Pay the [AMOUNT] fee to [ACCOUNT] today"


class FakeEmbedder:
    def __init__(self, failure: Exception | None = None, delay: float = 0.0) -> None:
        self._failure = failure
        self._delay = delay
        self.calls: list[tuple[str, str]] = []

    async def embed_text(self, text: str, *, operation: str) -> list[float]:
        self.calls.append((text, operation))
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._failure:
            raise self._failure
        return VECTOR


class FakePatterns:
    def __init__(self, found: list[SimilarPattern] | Exception) -> None:
        self._found = found
        self.calls: list[tuple[list[float], int]] = []

    def find_similar(self, embedding: list[float], limit: int) -> list[SimilarPattern]:
        self.calls.append((embedding, limit))
        if isinstance(self._found, Exception):
            raise self._found
        return self._found


class FakeReports:
    def __init__(self, found: list[SimilarReport] | Exception) -> None:
        self._found = found
        self.calls: list[tuple[list[float], str, int]] = []

    def find_similar(
        self, embedding: list[float], corridor_id: str, limit: int
    ) -> list[SimilarReport]:
        self.calls.append((embedding, corridor_id, limit))
        if isinstance(self._found, Exception):
            raise self._found
        return self._found


def _firestore_error(message: str) -> Exception:
    """The error Firestore raises for a query that needs a vector index it does not have."""
    return FailedPrecondition(message)  # type: ignore[no-untyped-call]


def _pattern(pattern_id: str, scam_type: str, score: float) -> SimilarPattern:
    return SimilarPattern(pattern_id, scam_type, round(1 - score, 6))


def _report(report_id: str, slug: str, score: float) -> SimilarReport:
    return SimilarReport(report_id, slug, round(1 - score, 6))


def _finder(
    patterns: list[SimilarPattern] | Exception | None = None,
    reports: list[SimilarReport] | Exception | None = None,
    embedder: FakeEmbedder | None = None,
) -> tuple[SimilarScamFinder, FakeEmbedder, FakePatterns, FakeReports]:
    embedder = embedder or FakeEmbedder()
    fake_patterns = FakePatterns([] if patterns is None else patterns)
    fake_reports = FakeReports([] if reports is None else reports)
    finder = SimilarScamFinder(embedder, fake_patterns, fake_reports)  # type: ignore[arg-type]
    return finder, embedder, fake_patterns, fake_reports


async def _find(finder: SimilarScamFinder, corridor: Any = "SG-IN", text: str = TEXT) -> Any:
    return await finder.find(text, corridor, TYPES)


# ---------------------------------------------------------------- what is asked


async def test_the_redacted_text_is_embedded_once_and_both_searches_use_that_vector() -> None:
    finder, embedder, patterns, reports = _finder()

    await _find(finder)

    assert embedder.calls == [(TEXT, EMBED_OPERATION)] and EMBED_OPERATION == "scam.embed"
    assert patterns.calls == [(VECTOR, PATTERNS_FETCHED)]
    assert reports.calls == [(VECTOR, "SG-IN", REPORTS_FETCHED)]


async def test_without_a_corridor_reports_are_not_searched_and_not_counted() -> None:
    finder, _, patterns, reports = _finder(patterns=[_pattern("lottery-en-001", "lottery", 0.95)])

    result = await _find(finder, corridor=None)

    assert reports.calls == [] and len(patterns.calls) == 1
    assert result.corridor_report_count is None
    assert [m.scam_type for m in result.similar] == ["lottery"]


# ---------------------------------------------------------------- what is shown


async def test_only_neighbours_at_or_above_the_cutoff_are_shown_with_their_score() -> None:
    finder, *_ = _finder(
        patterns=[
            _pattern("fake_job_offer-en-001", "fake_job_offer", 0.93),
            _pattern("lottery-en-001", "lottery", PATTERN_MIN_SCORE),
            _pattern("loan_app_trap-en-001", "loan_app_trap", PATTERN_MIN_SCORE - 0.01),
        ]
    )

    result = await _find(finder)

    assert [(m.source, m.scam_type, m.score) for m in result.similar] == [
        ("scam_pattern", "fake_job_offer", 0.93),
        ("scam_pattern", "lottery", PATTERN_MIN_SCORE),
    ]


async def test_copies_of_one_template_in_other_languages_are_one_finding() -> None:
    finder, *_ = _finder(
        patterns=[
            _pattern("lottery-ne-001", "lottery", 0.95),
            _pattern("lottery-bn-001", "lottery", 0.94),
            _pattern("lottery-bn-010", "lottery", 0.93),
            _pattern("fake_job_offer-hi-001", "fake_job_offer", 0.92),
            _pattern("lottery-hi-002", "lottery", 0.91),
        ]
    )

    result = await _find(finder)

    assert [(m.scam_type, m.match_id, m.score) for m in result.similar] == [
        ("lottery", "lottery-ne-001", 0.95),
        ("fake_job_offer", "fake_job_offer-hi-001", 0.92),
    ]


async def test_at_most_three_are_shown_closest_first_across_both_sources() -> None:
    finder, *_ = _finder(
        patterns=[
            _pattern("a-en-001", "fake_job_offer", 0.90),
            _pattern("b-en-001", "illegal_recruitment_fee", 0.89),
            _pattern("c-en-001", "lottery", 0.88),
            _pattern("d-en-001", "loan_app_trap", 0.87),
        ],
        reports=[_report("r1", "scam-fake-job-offer", 0.95)],
    )

    result = await _find(finder)

    assert len(result.similar) == 3
    assert [m.score for m in result.similar] == [0.95, 0.90, 0.89]
    assert result.similar[0].source == "radar_report"


async def test_a_scam_report_has_its_type_read_from_its_slug_and_others_have_none() -> None:
    finder, *_ = _finder(
        reports=[
            _report("r1", "scam-illegal-recruitment-fee", 0.93),
            _report("r2", "example-remit", 0.92),
            _report("r3", "scam-not-a-real-type", 0.91),
        ]
    )

    result = await _find(finder)

    # r2 and r3 both have no type, so they are one finding: the closer one.
    assert [(m.match_id, m.scam_type) for m in result.similar] == [
        ("r1", "illegal_recruitment_fee"),
        ("r2", None),
    ]


async def test_the_score_is_a_similarity_between_zero_and_one() -> None:
    finder, *_ = _finder(
        patterns=[
            SimilarPattern("x-en-001", "lottery", -0.2),
            SimilarPattern("y-en-001", "other_scam", 1.4),
        ]
    )

    result = await _find(finder)

    assert [m.score for m in result.similar] == [1.0]  # a distance over 1 is a score of 0


# ---------------------------------------------------------------- the count


async def test_the_corridor_count_is_the_reports_above_the_cutoff_among_those_fetched() -> None:
    finder, *_ = _finder(
        reports=[
            _report("r1", "scam-lottery", 0.97),
            _report("r2", "scam-lottery", 0.90),
            _report("r3", "example-remit", REPORT_MIN_SCORE),
            _report("r4", "example-remit", REPORT_MIN_SCORE - 0.05),
        ]
    )

    result = await _find(finder)

    assert result.corridor_report_count == 3


async def test_no_reports_on_the_corridor_is_a_count_of_zero_not_unknown() -> None:
    finder, *_ = _finder(reports=[])

    result = await _find(finder)

    assert result.corridor_report_count == 0 and result.similar == []


# ---------------------------------------------------------------- when it fails


@pytest.mark.parametrize("failure", [GeminiUnavailableError("busy"), GeminiRateLimitError("quota")])
async def test_a_failed_embedding_is_an_empty_answer_not_an_error(
    failure: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    finder, _, patterns, reports = _finder(embedder=FakeEmbedder(failure))

    with caplog.at_level(logging.WARNING):
        result = await _find(finder)

    assert result is NOTHING_FOUND
    assert patterns.calls == [] and reports.calls == []
    assert f"reason={type(failure).__name__}" in caplog.text


async def test_a_search_that_takes_too_long_is_given_up_on(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(retrieval, "TIMEOUT_SECONDS", 0.05)
    finder, *_ = _finder(embedder=FakeEmbedder(delay=5))

    with caplog.at_level(logging.WARNING):
        result = await _find(finder)

    assert result is NOTHING_FOUND and "reason=timeout" in caplog.text


async def test_a_missing_pattern_index_still_gives_the_reports(
    caplog: pytest.LogCaptureFixture,
) -> None:
    missing_index = _firestore_error("The query requires a vector index")
    finder, *_ = _finder(patterns=missing_index, reports=[_report("r1", "scam-lottery", 0.96)])

    with caplog.at_level(logging.WARNING):
        result = await _find(finder)

    assert [m.source for m in result.similar] == ["radar_report"]
    assert result.corridor_report_count == 1
    assert "scam_similar_patterns_failed reason=FailedPrecondition" in caplog.text


async def test_a_failed_report_search_still_gives_the_patterns_and_no_count() -> None:
    finder, *_ = _finder(
        patterns=[_pattern("lottery-en-001", "lottery", 0.96)],
        reports=_firestore_error("no index"),
    )

    result = await _find(finder)

    assert [m.source for m in result.similar] == ["scam_pattern"]
    assert result.corridor_report_count is None


async def test_both_searches_failing_is_an_empty_answer() -> None:
    finder, *_ = _finder(patterns=_firestore_error("x"), reports=_firestore_error("y"))

    result = await _find(finder)

    assert result.similar == [] and result.corridor_report_count is None


async def test_an_unexpected_error_is_not_swallowed() -> None:
    # Only Firestore and Gemini failures are the search's to absorb: a bug must still be seen.
    finder, *_ = _finder(patterns=KeyError("a bug"))

    with pytest.raises(KeyError):
        await _find(finder)


async def test_the_log_counts_what_was_found_and_repeats_no_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    finder, *_ = _finder(patterns=[_pattern("lottery-en-001", "lottery", 0.96)])

    with caplog.at_level(logging.INFO):
        await _find(finder)

    assert "scam_similar patterns=1 reports=0 shown=1" in caplog.text
    assert "Pay the" not in caplog.text and "lottery-en-001" not in caplog.text


# ---------------------------------------------------------------- the pattern repository


@dataclass
class _Doc:
    id: str
    data: dict[str, Any]

    def get(self, field: str) -> Any:
        return self.data[field]


class _Query:
    def __init__(self, docs: list[_Doc]) -> None:
        self._docs = docs

    def stream(self) -> list[_Doc]:
        return self._docs


class _Collection:
    def __init__(self, docs: list[_Doc]) -> None:
        self._docs = docs
        self.kwargs: dict[str, Any] = {}

    def find_nearest(self, **kwargs: Any) -> _Query:
        self.kwargs = kwargs
        return _Query(self._docs)


class _Client:
    def __init__(self, collection: _Collection) -> None:
        self._collection = collection
        self.names: list[str] = []

    def collection(self, name: str) -> _Collection:
        self.names.append(name)
        return self._collection


def test_the_pattern_repository_asks_for_cosine_neighbours_and_keeps_only_what_it_may() -> None:
    from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
    from google.cloud.firestore_v1.vector import Vector

    docs = [
        _Doc(
            "lottery-en-001",
            {"scam_type": "lottery", "distance": 0.08, "text": "SECRET TEMPLATE TEXT"},
        )
    ]
    collection = _Collection(docs)
    client = _Client(collection)

    found = ScamPatternRepository(client).find_similar(VECTOR, 5)  # type: ignore[arg-type]

    assert client.names == ["scam_patterns"]
    kwargs = collection.kwargs
    assert kwargs["vector_field"] == "embedding" and kwargs["limit"] == 5
    assert kwargs["distance_measure"] == DistanceMeasure.COSINE
    assert kwargs["distance_result_field"] == "distance"
    assert isinstance(kwargs["query_vector"], Vector)
    assert found == [SimilarPattern("lottery-en-001", "lottery", 0.08)]
    assert not hasattr(found[0], "text")
