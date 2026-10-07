from __future__ import annotations

import pytest

from src.loaders.scam_patterns_calibrate import (
    SHOWN_THRESHOLDS,
    best_scores,
    golden_rows,
    report,
    share_at_or_above,
    suggest_cutoff,
)
from tests.test_scam_patterns_loader import HashEmbedder


def test_every_golden_row_is_loaded_scams_and_benign() -> None:
    rows = golden_rows()

    scams = [r for r in rows if r.is_scam]
    benign = [r for r in rows if not r.is_scam]
    assert len(rows) == 120 and len(scams) == 84 and len(benign) == 36
    assert [r.id for r in rows] == sorted(r.id for r in rows)


def test_a_share_is_the_fraction_at_or_above_the_cutoff() -> None:
    assert share_at_or_above([0.5, 0.8, 0.9, 0.95], 0.85) == 0.5
    assert share_at_or_above([0.85], 0.85) == 1.0
    assert share_at_or_above([], 0.85) == 0.0


def test_the_suggested_cutoff_separates_two_groups_that_do_not_overlap() -> None:
    scams = [0.88, 0.91, 0.95, 0.97]
    benign = [0.60, 0.70, 0.78, 0.82]

    cutoff = suggest_cutoff(scams, benign)

    assert 0.82 < cutoff <= 0.88
    assert share_at_or_above(scams, cutoff) == 1.0 and share_at_or_above(benign, cutoff) == 0.0


def test_when_the_groups_overlap_the_cutoff_trades_scams_for_false_alarms_sensibly() -> None:
    scams = [0.80, 0.86, 0.90, 0.92, 0.95, 0.96]
    benign = [0.70, 0.75, 0.88, 0.89]

    cutoff = suggest_cutoff(scams, benign)

    # Showing 4 of 6 scams and no safe message beats showing all six and two safe ones.
    assert cutoff > 0.89
    assert share_at_or_above(benign, cutoff) == 0.0


def test_a_tie_goes_to_the_higher_cutoff() -> None:
    assert suggest_cutoff([0.9], [0.5]) > 0.5  # every cutoff in 0.505..0.9 separates them
    assert suggest_cutoff([0.9], [0.5]) == 0.9


def test_best_scores_gives_each_row_its_closest_templates_id_and_similarity() -> None:
    embedder = HashEmbedder()
    texts = {
        "lottery-en-001": "you won the lottery prize draw today",
        "a-en-001": "unrelated words",
    }
    library = list(zip(texts, embedder.embed(list(texts.values())), strict=True))
    rows = [r for r in golden_rows() if r.is_scam][:3]

    scored = best_scores(rows, embedder, library, lambda t: t)

    assert [r.id for r, _, _ in scored] == [r.id for r in rows]
    assert all(pattern_id in texts and -1.0 <= score <= 1.0 for _, pattern_id, score in scored)


def test_the_report_prints_the_table_the_hard_cases_and_a_suggestion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    embedder = HashEmbedder()
    library = list(zip(["lottery-en-001"], embedder.embed(["you won the prize"]), strict=True))
    scored = best_scores(golden_rows(), embedder, library, lambda t: t)

    cutoff = report(scored)

    out = capsys.readouterr().out
    assert "scams:" in out and "benign:" in out
    for threshold in SHOWN_THRESHOLDS:
        assert f"{threshold:.2f}" in out
    assert "safe messages closest to a known scam" in out
    assert "scams furthest from any template" in out
    assert f"Suggested cutoff: {cutoff:.3f}" in out
