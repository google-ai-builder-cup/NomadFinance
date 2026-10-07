from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from src.config import SCAM_PATTERNS_DIR
from src.validators import scam_patterns
from src.validators.scam_golden import load_rows
from src.validators.scam_patterns import (
    CORRIDORS,
    LANGUAGES,
    PatternRow,
    check_library,
    load_all,
    load_patterns,
    script_of,
)
from src.validators.scam_taxonomy import load_taxonomy

EVALS = Path(__file__).resolve().parent.parent / "evals"


@pytest.fixture(scope="module")
def library() -> list[PatternRow]:
    rows, problems = load_all(SCAM_PATTERNS_DIR)
    assert problems == []
    return rows


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "fake_job_offer-en-001",
        "scam_type": "fake_job_offer",
        "language": "en",
        "tactics": ["urgency"],
        "text": "Hiring cleaners now, send your passport copy to [EMAIL] today to get a contract.",
        "corridor_id": "SG-PH",
        "curator": "DD",
    }
    base.update(overrides)
    return base


def _problem(**overrides: Any) -> str:
    with pytest.raises(ValueError) as caught:
        PatternRow.model_validate(_row(**overrides))
    return str(caught.value)


# ---------------------------------------------------------------- the committed library


def test_library_passes_every_check(library: list[PatternRow]) -> None:
    assert check_library(library) == []


def test_every_taxonomy_type_has_at_least_sixty_templates(library: list[PatternRow]) -> None:
    per_type = Counter(r.scam_type for r in library)
    assert set(per_type) == set(load_taxonomy().types)
    assert min(per_type.values()) >= 60


def test_every_language_is_covered_in_every_type(library: list[PatternRow]) -> None:
    for scam_type in load_taxonomy().types:
        languages = Counter(r.language for r in library if r.scam_type == scam_type)
        assert set(languages) == set(LANGUAGES)
        assert min(languages.values()) >= 10


def test_every_corridor_is_covered_in_every_type(library: list[PatternRow]) -> None:
    for scam_type in load_taxonomy().types:
        corridors: Counter[str | None] = Counter(
            r.corridor_id for r in library if r.scam_type == scam_type
        )
        for corridor in CORRIDORS:
            assert corridors[corridor] >= 3, (scam_type, corridor)


def test_no_template_names_a_place_outside_scope(library: list[PatternRow]) -> None:
    banned = re.compile(r"korea|seoul|dubai|\buae\b|emirates|qatar|saudi", re.IGNORECASE)
    assert [r.id for r in library if banned.search(r.text)] == []


def test_romanised_hindi_nepali_and_bengali_are_present(library: list[PatternRow]) -> None:
    for scam_type in load_taxonomy().types:
        for language, wanted in (("hi", 2), ("ne", 1), ("bn", 1)):
            latin = [
                r
                for r in library
                if r.scam_type == scam_type
                and r.language == language
                and script_of(r.text, language) == "latin"
            ]
            assert len(latin) >= wanted, (scam_type, language)


def test_a_template_is_not_a_copy_of_a_golden_message(library: list[PatternRow]) -> None:
    """The golden scams are the held-out queries of the neighbour check: a template written from
    one would make the check measure memory, not retrieval."""
    word = re.compile(r"\w+", re.UNICODE)
    golden = []
    for path in sorted(EVALS.glob("scam_golden_*.jsonl")):
        rows, _ = load_rows(path)
        golden += [frozenset(word.findall(r.text.lower())) for r in rows]
    for row in library:
        words = frozenset(word.findall(row.text.lower()))
        for other in golden:
            overlap = len(words & other) / len(words | other)
            assert overlap < 0.6, f"{row.id} is {overlap:.0%} the same as a golden message"


def test_ids_are_the_documented_shape(library: list[PatternRow]) -> None:
    for row in library:
        assert re.fullmatch(rf"{row.scam_type}-{row.language}-\d{{3}}", row.id)


def test_every_row_names_a_curator_and_no_row_is_self_reviewed(library: list[PatternRow]) -> None:
    assert all(r.curator for r in library)
    assert all(r.reviewed_by != r.curator for r in library)


# ---------------------------------------------------------------- one row


def test_a_good_row_is_accepted() -> None:
    assert PatternRow.model_validate(_row()).id == "fake_job_offer-en-001"


def test_id_must_match_type_and_language() -> None:
    assert "must be" in _problem(id="lottery-en-001")
    assert "must be" in _problem(id="fake_job_offer-hi-001")
    assert "must be" in _problem(id="fake_job_offer-en-1")


def test_type_and_tactics_must_be_in_the_taxonomy() -> None:
    assert "taxonomy" in _problem(id="made_up-en-001", scam_type="made_up")
    assert "tactic" in _problem(tactics=["greed"])
    assert "tactic" in _problem(tactics=["urgency", "urgency"])
    assert "tactics" in _problem(tactics=[])


def test_an_unknown_placeholder_is_refused() -> None:
    assert "unknown placeholder" in _problem(text="Pay [FEE] to [ACCOUNT] before the end of today.")


def test_real_looking_contacts_are_refused() -> None:
    assert "link" in _problem(text="Open https://fast-hire.com now to claim the job slot today.")
    assert "address" in _problem(text="Write to hr@agency.com with your passport copy today now.")
    assert "could be real" in _problem(
        text="Call +65 9123 4567 to confirm your job slot right now."
    )


def test_a_place_outside_the_six_corridors_is_refused() -> None:
    assert "outside" in _problem(
        text="Hiring drivers in Seoul, send your passport copy to [EMAIL]."
    )
    assert "outside" in _problem(
        text="Jobs in Dubai for cleaners, send your passport copy to [EMAIL]."
    )


def test_a_word_that_only_contains_a_banned_name_is_fine() -> None:
    # "pondohan" holds "doha"; matching must be on whole words
    PatternRow.model_validate(
        _row(
            language="tl",
            id="fake_job_offer-tl-001",
            text="Pondohan ang account mo para magsimula, [ACCOUNT].",
        )
    )


def test_script_must_fit_the_language() -> None:
    assert "Latin" in _problem(
        text="नौकरी चाहिए तो अपना पासपोर्ट [EMAIL] पर आज ही भेज दीजिए जल्दी।"
    )


def test_text_is_one_trimmed_line_and_not_a_todo() -> None:
    assert "one trimmed line" in _problem(
        text="Send your passport copy to [EMAIL]\nand pay [AMOUNT] today."
    )
    assert "TODO" in _problem(text="TODO write this template properly and add the placeholders")


def test_reviewer_is_not_the_curator() -> None:
    assert "different person" in _problem(reviewed_by="DD")


def test_extra_fields_are_refused() -> None:
    assert "extra" in _problem(risk="high").lower()


def test_corridor_must_be_one_of_the_six() -> None:
    assert "corridor_id" in _problem(corridor_id="KR-NP")
    assert "corridor_id" in _problem(corridor_id="AE-IN")


# ---------------------------------------------------------------- the library as a whole


def _full(per_type: int = 60) -> list[PatternRow]:
    """A synthetic valid library: every type, language and corridor, distinct texts."""
    rows: list[PatternRow] = []
    words = [
        "alpha",
        "bravo",
        "charlie",
        "delta",
        "echo",
        "foxtrot",
        "golf",
        "hotel",
        "india",
        "juliet",
    ]
    for scam_type in sorted(load_taxonomy().types):
        for language in LANGUAGES:
            for n in range(1, per_type // 6 + 1):
                text = (
                    f"{words[n % 10]} {scam_type} {language} {n} "
                    f"{' '.join(f'{words[(n + k) % 10]}{k}' for k in range(8))} [AMOUNT]"
                )
                corridor = CORRIDORS[n % 6] if n <= 6 else None
                rows.append(
                    PatternRow.model_validate(
                        _row(
                            id=f"{scam_type}-{language}-{n:03d}",
                            scam_type=scam_type,
                            language=language,
                            text=text,
                            corridor_id=corridor,
                            tactics=["urgency"],
                        )
                    )
                )
    return rows


def test_a_complete_synthetic_library_passes() -> None:
    assert check_library(_full()) == []


def test_too_few_per_type_is_reported() -> None:
    rows = [
        r
        for r in _full()
        if not (r.scam_type == "lottery" and r.language == "en" and r.id.endswith("010"))
    ]
    assert any("lottery: 59 templates" in p for p in check_library(rows))


def test_a_missing_language_is_reported() -> None:
    rows = [r for r in _full() if not (r.scam_type == "lottery" and r.language == "bn")]
    assert any("lottery: 0 bn templates" in p for p in check_library(rows))


def test_a_corridor_with_too_few_templates_is_reported() -> None:
    rows = [
        (
            r.model_copy(update={"corridor_id": None})
            if r.scam_type == "other_scam" and r.corridor_id == "AU-PH"
            else r
        )
        for r in _full()
    ]
    assert any("other_scam: 0 template(s) for AU-PH" in p for p in check_library(rows))


def test_a_language_without_romanised_templates_is_reported() -> None:
    rows = _full()
    for i, row in enumerate(rows):
        if row.scam_type == "lottery" and row.language == "hi":
            n = int(row.id[-3:])
            text = f"नौकरी {n} के लिए अपना पासपोर्ट आज भेजिए {n * 7} और [AMOUNT] जमा कीजिए"
            rows[i] = row.model_copy(update={"text": text})
    assert any("lottery: 0 hi template(s) in Latin letters" in p for p in check_library(rows))


def test_duplicate_text_and_near_copies_are_reported() -> None:
    rows = _full()
    first = rows[0]
    rows[1] = rows[1].model_copy(update={"text": first.text})
    problems = check_library(rows)
    assert any("same text" in p for p in problems)
    assert any("near-copies" in p for p in problems)


def test_a_gap_in_ids_is_reported() -> None:
    rows = [r for r in _full() if r.id != "lottery-en-003"]
    assert any("lottery-en: ids must run 001 upwards" in p for p in check_library(rows))


# ---------------------------------------------------------------- files and command


def test_script_of() -> None:
    assert script_of("Apna passport bhej do", "hi") == "latin"
    assert script_of("अपना पासपोर्ट भेजिए", "hi") == "native"
    assert script_of("তোমার পাসপোর্ট পাঠাও", "bn") == "native"
    assert script_of("Padala mo na ang passport mo", "tl") == "latin"


def test_a_row_in_the_wrong_file_is_reported(tmp_path: Path) -> None:
    (tmp_path / "lottery.jsonl").write_text(json.dumps(_row()) + "\n", encoding="utf-8")
    _, problems = load_all(tmp_path)
    assert any("belongs in fake_job_offer.jsonl" in p for p in problems)


def test_a_bad_line_of_json_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "fake_job_offer.jsonl"
    path.write_text('{"id": \n', encoding="utf-8")
    _, problems = load_patterns(path)
    assert "not JSON" in problems[0]


def test_an_empty_folder_is_reported(tmp_path: Path) -> None:
    _, problems = load_all(tmp_path)
    assert "no *.jsonl" in problems[0]


def test_command_passes_on_the_committed_library(capsys: pytest.CaptureFixture[str]) -> None:
    assert scam_patterns.main([]) == 0
    assert "OK   480 templates, 8 types, 6 languages" in capsys.readouterr().out


def test_command_fails_on_a_bad_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "lottery.jsonl").write_text("not json\n", encoding="utf-8")
    assert scam_patterns.main(["--directory", str(tmp_path)]) == 1
    assert "FAIL" in capsys.readouterr().out


# ---------------------------------------------------------------- review


def test_spot_check_is_fixed_and_spans_every_type_and_language(library: list[PatternRow]) -> None:
    first = scam_patterns.pick_spot_check(library, 10)
    assert [r.id for r in first] == [r.id for r in scam_patterns.pick_spot_check(library, 10)]
    assert len({r.id for r in first}) == 10
    assert {r.scam_type for r in first} == set(load_taxonomy().types)
    assert {r.language for r in first} == set(LANGUAGES)


def test_require_reviewed_fails_until_initials_are_in(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert scam_patterns.main(["--require-reviewed", "10"]) == 1
    assert "0 row(s) reviewed, 10 required" in capsys.readouterr().out


def test_spot_check_prints_rows(capsys: pytest.CaptureFixture[str]) -> None:
    assert scam_patterns.main(["--spot-check", "10"]) == 0
    out = capsys.readouterr().out
    assert out.count("tactics=") == 10
