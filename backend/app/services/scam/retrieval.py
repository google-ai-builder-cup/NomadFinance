from __future__ import annotations

import asyncio
import logging
from collections.abc import Collection
from dataclasses import dataclass

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPIError

from app.integrations.gemini import GeminiClient, GeminiError
from app.repositories.radar_repo import RadarRepository, SimilarReport
from app.repositories.scam_pattern_repo import ScamPatternRepository, SimilarPattern
from app.schemas.scam import CorridorId, SimilarSource

logger = logging.getLogger(__name__)

EMBED_OPERATION = "scam.embed"

# How close a neighbour must be to be shown (cosine similarity, 0 to 1). First values, to be
# confirmed from `python -m src.loaders.scam_patterns_check --calibrate` in data-scripts, which
# scores the golden scams against the golden benign look-alikes (D-137). A cutoff set too low
# calls a safe message "seen before"; too high, and a real scam shows nothing. Reports are
# a worker's own words, not a template, and may need a lower one.
PATTERN_MIN_SCORE = 0.85
REPORT_MIN_SCORE = 0.85

# Several copies of one template in different languages are all near; five are fetched so the
# three shown can be of different types.
PATTERNS_FETCHED = 5
REPORTS_FETCHED = 10
MAX_SIMILAR = 3
# The verdict takes a few seconds; the neighbours must never make the worker wait for them.
TIMEOUT_SECONDS = 8.0

_SCAM_REPORT_SLUG = "scam-"  # `radar_entities` slug of a scam report: scam-<type with hyphens>


@dataclass(frozen=True)
class SimilarMatch:
    """A neighbour as the answer shows it, plus the id the check store will keep (scam.md)."""

    source: SimilarSource
    match_id: str
    scam_type: str | None
    score: float


@dataclass(frozen=True)
class Retrieval:
    """What the search found. `corridor_report_count` is None when it could not be counted."""

    similar: list[SimilarMatch]
    corridor_report_count: int | None


NOTHING_FOUND = Retrieval(similar=[], corridor_report_count=None)


def _score(distance: float) -> float:
    return round(min(1.0, max(0.0, 1.0 - distance)), 3)


def _report_type(slug: str, known_types: Collection[str]) -> str | None:
    """The scam type of a scam report, read from its entity slug; None for any other report."""
    if not slug.startswith(_SCAM_REPORT_SLUG):
        return None
    candidate = slug.removeprefix(_SCAM_REPORT_SLUG).replace("-", "_")
    return candidate if candidate in known_types else None


def _pick(matches: list[SimilarMatch]) -> list[SimilarMatch]:
    """The best of each source and type, then the best few: three Hindi, Nepali and Bengali
    copies of one lottery template are one finding, not three."""
    best: dict[tuple[str, str | None], SimilarMatch] = {}
    for match in sorted(matches, key=lambda m: m.score, reverse=True):
        best.setdefault((match.source, match.scam_type), match)
    return list(best.values())[:MAX_SIMILAR]


class SimilarScamFinder:
    """Finds the known scams and Radar reports a message resembles (design 5.2, step 7).

    Runs alongside the classifier and its answer is not fed into it, so a poisoned template
    cannot steer the verdict. It never raises: a search that fails is an empty answer.
    """

    def __init__(
        self,
        gemini: GeminiClient,
        patterns: ScamPatternRepository,
        reports: RadarRepository,
    ) -> None:
        self._gemini = gemini
        self._patterns = patterns
        self._reports = reports

    async def find(
        self,
        redacted_text: str,
        corridor_id: CorridorId | None,
        known_types: Collection[str],
    ) -> Retrieval:
        """Neighbours of `redacted_text` above the similarity cutoff, and the report count.

        Args:
            redacted_text: The message after `redact_text`: it is sent to Gemini to be embedded.
            corridor_id: The worker's route. Radar reports are searched on it, so without one
                there is no count and no report neighbour.
            known_types: Taxonomy type ids; a report is given a type only if it is one of these.

        Returns:
            At most 3 matches, closest first, and the number of Radar reports on the corridor
            among the nearest 10 that are above the cutoff (None if not counted). Empty
            and None on any failure.
        """
        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                vector = await self._gemini.embed_text(redacted_text, operation=EMBED_OPERATION)
                patterns, reports = await asyncio.gather(
                    self._search_patterns(vector), self._search_reports(vector, corridor_id)
                )
        except TimeoutError:
            logger.warning("scam_similar_unavailable reason=timeout")
            return NOTHING_FOUND
        except GeminiError as exc:
            logger.warning("scam_similar_unavailable reason=%s", type(exc).__name__)
            return NOTHING_FOUND

        matches = [
            SimilarMatch("scam_pattern", p.pattern_id, p.scam_type, _score(p.distance))
            for p in patterns or []
            if _score(p.distance) >= PATTERN_MIN_SCORE
        ]
        close_reports = [r for r in reports or [] if _score(r.distance) >= REPORT_MIN_SCORE]
        matches += [
            SimilarMatch(
                "radar_report",
                r.report_id,
                _report_type(r.entity_slug, known_types),
                _score(r.distance),
            )
            for r in close_reports
        ]
        found = _pick(matches)
        logger.info(
            "scam_similar patterns=%s reports=%s shown=%d",
            "failed" if patterns is None else len(patterns),
            "skipped_or_failed" if reports is None else len(reports),
            len(found),
        )
        return Retrieval(found, None if reports is None else len(close_reports))

    async def _search_patterns(self, vector: list[float]) -> list[SimilarPattern] | None:
        try:
            return await run_in_threadpool(self._patterns.find_similar, vector, PATTERNS_FETCHED)
        except GoogleAPIError as exc:
            # Most likely the vector index is not deployed (D-114) or the collection is not
            # loaded (D-135). The other search and the verdict carry on.
            logger.warning("scam_similar_patterns_failed reason=%s", type(exc).__name__)
            return None

    async def _search_reports(
        self, vector: list[float], corridor_id: CorridorId | None
    ) -> list[SimilarReport] | None:
        if corridor_id is None:
            return None
        try:
            return await run_in_threadpool(
                self._reports.find_similar, vector, corridor_id, REPORTS_FETCHED
            )
        except GoogleAPIError as exc:
            logger.warning("scam_similar_reports_failed reason=%s", type(exc).__name__)
            return None
