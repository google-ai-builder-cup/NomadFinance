"""The stress set (evals/scam_stress_en_hi.jsonl, NF-SA-023): messages the golden sets do not have.

The golden sets passed 120 of 120, so they cannot show a weakness. This file holds the cases they
under-test: legitimate messages that look like scams, and scams that avoid the obvious words. It
uses the golden row format and its per-row checks, and is held to its own shape here.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from src.loaders.scam_patterns_calibrate import golden_rows
from src.validators.scam_golden import GoldenRow, load_rows

PATH = Path(__file__).resolve().parents[1] / "evals" / "scam_stress_en_hi.jsonl"


@pytest.fixture(scope="module")
def stress() -> list[GoldenRow]:
    rows, problems = load_rows(PATH)
    assert problems == []
    return rows


def test_it_is_thirty_messages_twenty_english_and_ten_hindi(stress: list[GoldenRow]) -> None:
    assert len(stress) == 30
    assert Counter(r.language for r in stress) == {"en": 20, "hi": 10}


def test_more_than_half_are_harmless_look_alikes_of_at_least_six_kinds_of_scam(
    stress: list[GoldenRow],
) -> None:
    benign = [r for r in stress if not r.is_scam]

    assert len(benign) == 16 and len(stress) - len(benign) == 14
    assert len({r.resembles for r in benign}) >= 6
    assert all(r.resembles for r in benign)


def test_the_scams_cover_most_types_and_all_three_risk_levels(stress: list[GoldenRow]) -> None:
    scams = [r for r in stress if r.is_scam]

    assert len({r.scam_type for r in scams}) >= 6
    assert {r.risk_level for r in scams} == {"low", "medium", "high"}


def test_ids_start_at_101_and_none_clashes_with_the_golden_sets_ids_or_texts(
    stress: list[GoldenRow],
) -> None:
    golden = golden_rows()
    assert min(int(r.id[-3:]) for r in stress) == 101
    assert not {r.id for r in stress} & {r.id for r in golden}
    seen = {" ".join(r.text.lower().split()) for r in golden}
    assert not {" ".join(r.text.lower().split()) for r in stress} & seen
    assert len({r.id for r in stress}) == 30


def test_a_second_person_is_named_as_reviewer_and_it_is_not_the_curator(
    stress: list[GoldenRow],
) -> None:
    assert {(r.curator, r.reviewed_by) for r in stress} == {("NF", "PP")}
