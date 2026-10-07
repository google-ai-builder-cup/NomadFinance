"""How often workers reported an indicator: `indicators[].seen`, read when a check is shown."""

from __future__ import annotations

import hashlib
import logging

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPIError

from app.repositories.scam_indicator_repo import ScamIndicatorRepository
from app.schemas.scam import ScamIndicator, SeenCount

logger = logging.getLogger(__name__)


def indicator_doc_id(indicator: ScamIndicator) -> str:
    """The `scam_indicators` id: the first 32 hex characters of the indicator's key. The 8 the
    contract calls `id` are the first of the same key (scam.md, "The key of an indicator").

    The key is of the value in normal form, which for a sender is lowercase and trimmed (the
    other kinds already are, and a phone is digits): "LoanPH" and "loanph" are one sender.
    The report route (NF-SA-013) writes the documents with this same function, so a count it
    adds is the count a later check reads.
    """
    value = indicator.value.strip().lower()
    return hashlib.sha256(f"{indicator.kind}:{value}".encode()).hexdigest()[:32]


async def attach_seen(
    indicators: list[ScamIndicator], repo: ScamIndicatorRepository
) -> list[ScamIndicator]:
    """The same indicators with `seen` filled in for those workers have reported.

    Read live, because the count changes after a check is stored. A hidden indicator is treated
    as never reported (an operator removed it, D-107). If the lookup fails the answer is the
    indicators as they were: a missing count must not fail a check.
    """
    if not indicators:
        return indicators
    ids = {indicator.id: indicator_doc_id(indicator) for indicator in indicators}
    try:
        docs = await run_in_threadpool(repo.get_many, sorted(set(ids.values())))
    except GoogleAPIError as exc:
        logger.warning("scam_seen_unavailable error=%s", type(exc).__name__)
        return indicators
    result: list[ScamIndicator] = []
    for indicator in indicators:
        seen = _seen(docs.get(ids[indicator.id]))
        result.append(indicator.model_copy(update={"seen": seen}) if seen else indicator)
    return result


def _seen(doc: dict[str, object] | None) -> SeenCount | None:
    if not doc or doc.get("hidden") is True:
        return None
    reports, incidents, last = (
        doc.get("report_count"),
        doc.get("incident_count"),
        doc.get("last_reported_at"),
    )
    if not isinstance(reports, int) or reports < 1 or last is None:
        return None
    return SeenCount.model_validate(
        {
            "reports": reports,
            "incidents": incidents if isinstance(incidents, int) and incidents >= 1 else 1,
            "last_reported_at": last,
            "flagged": doc.get("flagged") is True,
        }
    )
