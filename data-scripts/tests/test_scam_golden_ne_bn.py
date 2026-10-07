from __future__ import annotations

import re
from collections import Counter

import pytest

from src.config import EVALS_DIR
from src.validators.scam_golden import GoldenRow, check_set, load_rows, main
from src.validators.scam_taxonomy import load_taxonomy

GOLDEN = EVALS_DIR / "scam_golden_ne_bn.jsonl"

# The danda (U+0964, U+0965) ends sentences in both languages, so it counts as neither.
DEVANAGARI = re.compile("[\u0900-\u0963\u0966-\u097f]")
BENGALI = re.compile("[\u0980-\u09ff]")

# The six host countries (docs/design-doc: SG, KR, MY, JP, HK, AU) as the messages spell them.
HOST_NAMES = {
    "SG": ("सिंगापुर", "সিঙ্গাপুর", "Singapore"),
    "KR": ("कोरिया", "কোরিয়া", "Korea"),
    "MY": ("मलेसिया", "মালয়েশিয়া", "Malaysia"),
    "JP": ("जापान", "टोकियो", "Japan"),
    "HK": ("हङकङ", "হংকং", "Hong Kong"),
    "AU": ("अष्ट्रेलिया", "অস্ট্রেলিয়া", "Australia"),
}


def _rows() -> list[GoldenRow]:
    rows, problems = load_rows(GOLDEN)
    assert problems == []
    return rows


def test_the_committed_set_passes_every_check() -> None:
    rows = _rows()

    assert check_set(rows, GOLDEN) == []
    assert len(rows) == 40
    assert {r.language for r in rows} == {"ne", "bn"}


def test_each_language_has_14_scams_and_6_look_alikes_with_the_planned_mix() -> None:
    rows = _rows()
    taxonomy = load_taxonomy()
    two_each = [t for t in taxonomy.types if t not in ("lottery", "other_scam")]

    for language in ("ne", "bn"):
        scams = [r for r in rows if r.language == language and r.is_scam]
        benign = [r for r in rows if r.language == language and not r.is_scam]
        assert (len(scams), len(benign)) == (14, 6)
        counts = Counter(r.scam_type for r in scams)
        assert {t: counts[t] for t in two_each} == {t: 2 for t in two_each}
        assert counts["lottery"] == 1 and counts["other_scam"] == 1
        assert Counter(r.risk_level for r in scams) == {"high": 10, "medium": 3, "low": 1}
        assert len({r.resembles for r in benign}) == 6


def test_every_tactic_is_used_and_every_look_alike_resembles_a_taxonomy_type() -> None:
    rows = _rows()
    taxonomy = load_taxonomy()

    assert {t for r in rows for t in r.tactics} == set(taxonomy.tactics)
    assert {r.resembles for r in rows if not r.is_scam} <= set(taxonomy.types)


def test_each_language_has_three_messages_typed_in_latin_letters_as_workers_really_write() -> None:
    rows = _rows()

    for language in ("ne", "bn"):
        scripts = Counter(r.script for r in rows if r.language == language)
        assert scripts == {"native": 17, "latin": 3}


def test_a_native_row_is_in_its_own_script_and_a_latin_row_has_none_of_it() -> None:
    # The two scripts are easy to mix up when writing both languages in one sitting.
    own = {"ne": DEVANAGARI, "bn": BENGALI}
    other = {"ne": BENGALI, "bn": DEVANAGARI}
    for row in _rows():
        if row.script == "native":
            assert own[row.language].search(row.text), row.id
        else:
            assert not DEVANAGARI.search(row.text) and not BENGALI.search(row.text), row.id
        assert not other[row.language].search(row.text), row.id


def test_corridors_are_used_only_where_the_story_fits_one() -> None:
    rows = _rows()

    # No corridor starts in Nepal or Bangladesh (D-102): Nepali rows carry none, and a Bengali row
    # carries one only for a worker from West Bengal.
    assert {r.corridor_id for r in rows if r.language == "ne"} == {None}
    assert {r.corridor_id for r in rows if r.language == "bn"} <= {"SG-IN", "AU-IN", None}
    assert {r.corridor_id for r in rows if r.language == "bn"} >= {"SG-IN", "AU-IN"}


def test_all_six_host_countries_appear_in_the_messages() -> None:
    text = " ".join(r.text for r in _rows())

    for host, names in HOST_NAMES.items():
        assert any(name in text for name in names), host


def test_no_stretch_of_the_file_is_all_one_class() -> None:
    rows = _rows()

    for start in range(0, len(rows) - 3):
        assert len({r.is_scam for r in rows[start : start + 4]}) == 2


def test_the_set_is_curated_by_pp_and_never_reviewed_by_its_own_curator() -> None:
    rows = _rows()

    assert {r.curator for r in rows} == {"PP"}
    assert all(r.reviewed_by != "PP" for r in rows)


def test_the_command_passes_on_the_committed_set(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(GOLDEN)]) == 0
    assert "OK   scam_golden_ne_bn.jsonl: 40 rows, 28 scam, 12 benign" in capsys.readouterr().out


def test_the_spot_check_lists_ten_rows_from_both_languages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([str(GOLDEN), "--spot-check", "10"]) == 0
    out = capsys.readouterr().out

    assert sum(line.startswith("  gold-") for line in out.splitlines()) == 10
    assert "gold-ne-" in out and "gold-bn-" in out
