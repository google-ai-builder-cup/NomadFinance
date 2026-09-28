from __future__ import annotations

from collections.abc import Iterable

from app.schemas.contract_compare import ClauseCounts, ClauseRisk


def score_contract(risks: Iterable[ClauseRisk]) -> tuple[int, ClauseRisk, ClauseCounts]:
    """Contract Health Score from the terms' risks: `(health_score, risk_level, counts)`.

    The worst risk sets the band, so one illegal term is enough to put a contract in danger
    however many fair terms surround it:

    - any danger:   0 to 49, minus 10 per further danger and 2 per caution
    - caution only: 50 to 79, minus 3 per further caution
    - neither:      100

    Plain arithmetic on purpose: the report can explain every point of it.
    """
    counts = ClauseCounts()
    for risk in risks:
        setattr(counts, risk, getattr(counts, risk) + 1)

    if counts.danger:
        return max(0, 49 - 10 * (counts.danger - 1) - 2 * counts.caution), "danger", counts
    if counts.caution:
        return max(50, 79 - 3 * (counts.caution - 1)), "caution", counts
    return 100, "safe", counts
