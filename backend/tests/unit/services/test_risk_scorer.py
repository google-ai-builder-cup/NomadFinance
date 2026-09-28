from __future__ import annotations

import pytest

from app.schemas.contract_compare import ClauseRisk
from app.services.contract.risk_scorer import score_contract


@pytest.mark.parametrize(
    ("risks", "score", "level"),
    [
        (["safe"] * 12, 100, "safe"),
        (["safe", "caution"], 79, "caution"),
        (["caution"] * 3, 73, "caution"),
        (["caution"] * 30, 50, "caution"),  # never below the caution band
        (["safe"] * 20 + ["danger"], 49, "danger"),  # one illegal term is enough
        (["danger", "caution", "caution"], 45, "danger"),
        (["danger"] * 3, 29, "danger"),
        (["danger"] * 9, 0, "danger"),
    ],
)
def test_worst_risk_sets_the_band(risks: list[ClauseRisk], score: int, level: str) -> None:
    health_score, risk_level, _counts = score_contract(risks)

    assert (health_score, risk_level) == (score, level)


def test_counts_every_risk() -> None:
    _score, _level, counts = score_contract(["safe", "safe", "caution", "danger"])

    assert counts.model_dump() == {"safe": 2, "caution": 1, "danger": 1}
