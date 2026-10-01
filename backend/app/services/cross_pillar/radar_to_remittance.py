"""Exploitation Radar feeds Remittance X-Ray (design doc cross-pillar flow: "Radar flags
providers in the comparison").

A money transfer operator that workers keep reporting is marked on every comparison that
lists it (`ProviderResult.flagged`), and the recommendation (NF-P2-016) passes over it. The
ranking itself stays by price: a flagged service is still shown where its price puts it.
Matching is by slug, and by the slugs of the profile's aliases, the same way the frontend
badge matches (`frontend/src/utils/flaggedProviders.ts`).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.repositories.radar_repo import RadarRepository
from app.schemas.remittance_compare import RemittanceComparison
from app.utils.slugs import slugify

logger = logging.getLogger(__name__)

PROVIDER_TYPE = "money_transfer_operator"


def flagged_slugs(entities: list[dict[str, Any]]) -> dict[str, int]:
    """Slug (and alias slug) of each flagged operator -> its report count."""
    counts: dict[str, int] = {}
    for entity in entities:
        count = int(entity.get("report_count") or 0)
        names = [str(entity.get("slug") or "")]
        names += [slugify(str(alias)) for alias in entity.get("aliases") or []]
        for name in names:
            if name:
                counts[name] = max(counts.get(name, 0), count)
    return counts


def mark_flagged(comparison: RemittanceComparison, flagged: dict[str, int]) -> RemittanceComparison:
    """The comparison with `flagged` and `flag_report_count` set on each reported provider."""
    providers = []
    for provider in comparison.providers:
        count = flagged.get(slugify(provider.firm))
        if count is None:
            providers.append(provider)
        else:
            providers.append(
                provider.model_copy(update={"flagged": True, "flag_report_count": count})
            )
    return comparison.model_copy(update={"providers": providers})


async def flag_providers(
    comparison: RemittanceComparison, radar: RadarRepository
) -> RemittanceComparison:
    """Mark the flagged providers. Best effort: without Radar the comparison is still right."""
    try:
        entities = await run_in_threadpool(radar.flagged_entities, PROVIDER_TYPE)
    except GoogleAPICallError:
        logger.exception("radar_flags_read_failed corridor=%s", comparison.corridor_id)
        return comparison
    marked = mark_flagged(comparison, flagged_slugs(entities))
    flagged_count = sum(1 for p in marked.providers if p.flagged)
    if flagged_count:
        logger.info(
            "remittance_flagged corridor=%s providers=%d", comparison.corridor_id, flagged_count
        )
    return marked
