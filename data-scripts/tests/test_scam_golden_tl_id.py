from __future__ import annotations

from collections import Counter

import pytest

from src.config import EVALS_DIR
from src.validators.scam_golden import GoldenRow, check_set, load_rows, main
from src.validators.scam_taxonomy import load_taxonomy

GOLDEN = EVALS_DIR / "scam_golden_tl_id.jsonl"


def _rows() -> list[GoldenRow]:
    rows, problems = load_rows(GOLDEN)
    assert problems == []
    return rows


def test_the_committed_set_passes_every_check() -> None:
    rows = _rows()

    assert check_set(rows, GOLDEN) == []
    assert len(rows) == 40
    assert {r.language for r in rows} == {"tl", "id"}


def test_each_language_has_14_scams_and_6_look_alikes_with_the_planned_mix() -> None:
    rows = _rows()
    taxonomy = load_taxonomy()

    for language in ("tl", "id"):
        scams = [r for r in rows if r.language == language and r.is_scam]
        benign = [r for r in rows if r.language == language and not r.is_scam]
        assert (len(scams), len(benign)) == (14, 6)
        counts = Counter(r.scam_type for r in scams)
        assert {t: counts[t] for t in taxonomy.types if t not in ("lottery", "other_scam")} == {
            t: 2 for t in taxonomy.types if t not in ("lottery", "other_scam")
        }
        assert counts["lottery"] == 1 and counts["other_scam"] == 1
        assert Counter(r.risk_level for r in scams) == {"high": 10, "medium": 3, "low": 1}
        assert len({r.resembles for r in benign}) == 6


def test_every_tactic_is_used_and_every_look_alike_resembles_a_taxonomy_type() -> None:
    rows = _rows()
    taxonomy = load_taxonomy()

    assert {t for r in rows for t in r.tactics} == set(taxonomy.tactics)
    assert {r.resembles for r in rows if not r.is_scam} <= set(taxonomy.types)


def test_both_languages_are_written_in_their_own_script() -> None:
    rows = _rows()

    assert {r.script for r in rows} == {"native"}


def test_the_routes_left_for_this_set_are_used_and_the_corridors_are_valid() -> None:
    rows = _rows()
    routes = {r.corridor_id for r in rows}

    assert {"MY-ID", "JP-PH"} <= routes
    assert {r.corridor_id for r in rows if r.language == "id"} <= {"MY-ID", None}
    assert {r.corridor_id for r in rows if r.language == "tl"} <= {
        "SG-PH",
        "JP-PH",
        "AU-PH",
        None,
    }


def test_no_stretch_of_the_file_is_all_one_class() -> None:
    rows = _rows()

    for start in range(0, len(rows) - 3):
        assert len({r.is_scam for r in rows[start : start + 4]}) == 2


def test_the_set_is_all_curated_by_ab_and_not_yet_reviewed_by_the_curator() -> None:
    rows = _rows()

    assert {r.curator for r in rows} == {"AB"}
    assert all(r.reviewed_by != "AB" for r in rows)


def test_the_command_passes_on_the_committed_set(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(GOLDEN)]) == 0
    assert "OK   scam_golden_tl_id.jsonl: 40 rows, 28 scam, 12 benign" in capsys.readouterr().out


def test_the_spot_check_lists_ten_rows_from_both_languages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([str(GOLDEN), "--spot-check", "10"]) == 0
    out = capsys.readouterr().out

    assert sum(line.startswith("  gold-") for line in out.splitlines()) == 10
    assert "gold-tl-" in out and "gold-id-" in out
