"""Exploitation Radar steps 5 and 6 (NF-P3-002): embed a report, find its cluster.

`cluster_id` counts unique incidents (radar.md): a report that describes the same event as an
earlier one on the same business joins that report's cluster instead of starting a new one.
"""

from __future__ import annotations

import logging

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.integrations.gemini import GeminiClient, GeminiError
from app.repositories.radar_repo import RadarRepository

logger = logging.getLogger(__name__)

# Cosine similarity of 0.85. A first guess, not calibrated: re-tune once the demo seed data
# (NF-P3-005) gives real near-duplicates and unrelated reports to compare.
MAX_MATCH_DISTANCE = 0.15
# Neighbours fetched before filtering by business: a corridor has many businesses, and the
# nearest may be someone else's similar-sounding story.
NEIGHBOURS = 5


async def embed_report(description: str, gemini: GeminiClient) -> list[float] | None:
    """Step 5: the description's vector, or None if Gemini could not produce one.

    A Gemini outage must not lose a worker's report, so the caller stores it as its own
    cluster without an embedding rather than failing the submission.
    """
    try:
        return await gemini.embed_text(description, operation="radar.embed")
    except GeminiError as exc:
        logger.warning("radar_embed_skipped error=%s: %s", type(exc).__name__, exc)
        return None


async def find_cluster(
    embedding: list[float] | None,
    corridor_id: str | None,
    entity_slug: str,
    report_id: str,
    radar: RadarRepository,
) -> str:
    """Step 6: the cluster this report joins, or `report_id` when it starts a new one.

    Only the same business on the same corridor can match. Without a corridor there is no
    filter to search under (the vector index is per corridor), so the report starts its own
    cluster.
    """
    if embedding is None or corridor_id is None:
        return report_id
    try:
        neighbours = await run_in_threadpool(radar.find_similar, embedding, corridor_id, NEIGHBOURS)
        for neighbour in neighbours:
            if neighbour.entity_slug == entity_slug and neighbour.distance <= MAX_MATCH_DISTANCE:
                cluster_id = await run_in_threadpool(radar.get_cluster_id, neighbour.report_id)
                if cluster_id is not None:
                    return cluster_id
    except GoogleAPICallError:
        # A missing vector index (FailedPrecondition) or a Firestore blip must not lose the
        # report; the traceback keeps a missing index visible in the logs.
        logger.exception("radar_similarity_search_failed corridor=%s", corridor_id)
    return report_id
