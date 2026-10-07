from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.config import EVALS_DIR
from src.validators.scam_golden import (
    GoldenRow,
    check_set,
    load_rows,
    main,
    pick_spot_check,
    synthetic_problems,
)
from src.validators.scam_taxonomy import load_taxonomy

GOLDEN = EVALS_DIR / "scam_golden_en_hi.jsonl"


def _scam(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "gold-en-001",
        "language": "en",
        "script": "latin",
        "text": "Pay the agent fee of 1,800 SGD by tomorrow to account 0000-0000-1234.",
        "is_scam": True,
        "scam_type": "illegal_recruitment_fee",
        "tactics": ["urgency"],
        "risk_level": "high",
        "rationale": "Large fee demanded by a deadline, to an account, before any contract.",
        "resembles": None,
        "corridor_id": "SG-IN",
        "channel": "sms",
        "provenance": "synthetic",
        "curator": "DD",
        "reviewed_by": None,
    }
    return {**row, **changes}


def _benign(**changes: Any) -> dict[str, Any]:
    row = _scam(
        id="gold-en-002",
        text="Your one-time password is 482913. Never share this code with anyone.",
        is_scam=False,
        scam_type=None,
        tactics=[],
        risk_level="low",
        rationale="Genuine one-time password message that asks for nothing.",
        resembles="remittance_otp_phishing",
    )
    return {**row, **changes}


def _rows(path: Path = GOLDEN) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write(
    tmp_path: Path, rows: list[dict[str, Any]], name: str = "scam_golden_en_hi.jsonl"
) -> Path:
    path = tmp_path / name
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    return path


# --- the committed file -----------------------------------------------------------------


def test_the_committed_set_passes_every_check() -> None:
    rows, problems = load_rows(GOLDEN)

    assert problems == []
    assert check_set(rows, GOLDEN) == []
    assert len(rows) == 40


def test_the_committed_set_has_the_mix_the_tracker_asks_for() -> None:
    rows, _ = load_rows(GOLDEN)

    assert sum(r.is_scam for r in rows) == 28
    assert sum(not r.is_scam for r in rows) == 12
    assert {r.language for r in rows} == {"en", "hi"}
    for language in ("en", "hi"):
        in_language = [r for r in rows if r.language == language]
        assert len(in_language) == 20
        assert sum(r.is_scam for r in in_language) == 14


def test_every_scam_type_and_tactic_is_covered_and_every_benign_row_resembles_one() -> None:
    rows, _ = load_rows(GOLDEN)
    taxonomy = load_taxonomy()

    assert {r.scam_type for r in rows if r.is_scam} == set(taxonomy.types)
    assert {t for r in rows for t in r.tactics} == set(taxonomy.tactics)
    assert {r.resembles for r in rows if not r.is_scam} <= set(taxonomy.types)


def test_hindi_includes_messages_typed_in_latin_letters_as_workers_really_write_them() -> None:
    rows, _ = load_rows(GOLDEN)
    hindi = [r for r in rows if r.language == "hi"]

    assert 3 <= sum(r.script == "latin" for r in hindi) <= 6
    assert all(any("ऀ" <= ch <= "ॿ" for ch in r.text) for r in hindi if r.script == "native")


def test_no_stretch_of_the_file_is_all_one_class() -> None:
    rows, _ = load_rows(GOLDEN)

    for start in range(0, len(rows) - 3):
        assert len({r.is_scam for r in rows[start : start + 4]}) == 2


def test_the_command_passes_on_the_committed_set(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "OK   scam_golden_en_hi.jsonl: 40 rows, 28 scam, 12 benign" in capsys.readouterr().out


# --- one row ----------------------------------------------------------------------------


def test_a_good_scam_row_and_a_good_benign_row_pass() -> None:
    assert GoldenRow.model_validate(_scam()).is_scam
    assert GoldenRow.model_validate(_benign()).resembles == "remittance_otp_phishing"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"scam_type": None}, "needs a taxonomy type"),
        ({"scam_type": "pyramid"}, "needs a taxonomy type"),
        ({"tactics": []}, "at least one tactic"),
        ({"tactics": ["flattery"]}, "taxonomy tactic ids"),
        ({"tactics": ["urgency", "urgency"]}, "distinct"),
        ({"tactics": ["urgency", "fear", "authority", "scarcity"]}, "at most 3"),
        ({"resembles": "lottery"}, "benign messages"),
        ({"id": "gold-hi-001"}, "must be gold-en-NNN"),
        ({"id": "gold-1"}, "must be gold-en-NNN"),
        ({"script": "native"}, "Latin letters"),
        ({"rationale": "too short"}, "at least 20"),
        ({"rationale": "x" * 161}, "at most 160"),
        ({"rationale": "Two lines.\nIn one rationale, which is not allowed here."}, "one line"),
        ({"text": "TODO write this"}, "TODO"),
        ({"text": "x" * 4001}, "at most 4000"),
        ({"curator": "dd"}, "capital letters"),
        ({"reviewed_by": "DD"}, "different person"),
        ({"corridor_id": "SG-NP"}, "SG-PH"),
        ({"surprise": 1}, "Extra inputs"),
    ],
)
def test_a_bad_scam_row_is_refused_with_the_reason(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        GoldenRow.model_validate(_scam(**changes))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"scam_type": "lottery"}, "no type or tactics"),
        ({"tactics": ["urgency"]}, "no type or tactics"),
        ({"risk_level": "medium"}, "low risk"),
        ({"resembles": None}, "names the scam type"),
        ({"resembles": "pyramid"}, "names the scam type"),
    ],
)
def test_a_benign_row_has_no_type_no_tactics_low_risk_and_names_what_it_resembles(
    changes: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        GoldenRow.model_validate(_benign(**changes))


def test_a_reviewer_who_is_not_the_curator_is_accepted() -> None:
    assert GoldenRow.model_validate(_scam(reviewed_by="PP")).reviewed_by == "PP"


# --- invented data only -----------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Pay at https://remit-verify.example now",
        "WhatsApp +65 0000 0031 today",
        "account 0000-0000-1234",
        "mail hr@brightpath-hire.example",
        "UPI agent0000@example",
        "फोन +९१ ०००० ०००० ०१",
        "OTP 482913 is valid for 5 minutes",
        "Pay 1,50,000 rupees or 25,000 SGD, the 6-digit code",
    ],
)
def test_invented_links_numbers_and_addresses_are_accepted(text: str) -> None:
    assert synthetic_problems(text) == []


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("Open https://dbs-login.com/pay now", "not on a reserved name"),
        ("Open http://192.168.1.1/x", "not on a reserved name"),
        ("Visit www.mom.gov.sg for details", "not on a reserved name"),
        ("Mail help@gmail.com", "not on a reserved name"),
        ("Go to bit.ly now", "real domain"),
        ("Call +65 9123 4567", "could be real"),
        ("Pay account 012-345-678-9", "could be real"),
        ("फोन +९१ ९८७६५ ४३२१०", "could be real"),
    ],
)
def test_a_link_address_or_number_that_could_be_real_is_refused(text: str, fragment: str) -> None:
    problems = synthetic_problems(text)

    assert problems and fragment in problems[0]


def test_a_row_with_a_real_looking_number_does_not_pass() -> None:
    with pytest.raises(ValueError, match="could be real"):
        GoldenRow.model_validate(_scam(text="Send 100 SGD to +65 9123 4567 today please."))


def test_an_anonymised_row_is_not_held_to_the_invented_rules() -> None:
    row = GoldenRow.model_validate(
        _scam(provenance="anonymised", text="Call +65 [PHONE]-masked, 100 SGD today please.")
    )

    assert row.provenance == "anonymised"


# --- the whole set ----------------------------------------------------------------------


def _problems(tmp_path: Path, change: Any, name: str = "scam_golden_en_hi.jsonl") -> list[str]:
    rows = _rows()
    change(rows)
    path = _write(tmp_path, rows, name)
    parsed, problems = load_rows(path)
    return problems or check_set(parsed, path)


def test_a_line_that_is_not_json_is_reported_with_its_number(tmp_path: Path) -> None:
    path = tmp_path / "scam_golden_en_hi.jsonl"
    path.write_text(GOLDEN.read_text(encoding="utf-8") + "{not json\n", encoding="utf-8")

    _, problems = load_rows(path)

    assert problems == ["line 41: not JSON (Expecting property name enclosed in double quotes)"]


def test_a_bad_field_is_reported_with_its_line_and_name(tmp_path: Path) -> None:
    problems = _problems(tmp_path, lambda rows: rows[2].update(risk_level="severe"))

    assert any(p.startswith("line 3: risk_level") for p in problems)


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (lambda rows: rows.pop(), "39 rows"),
        (
            lambda rows: rows.append(
                {**rows[0], "id": "gold-en-021", "text": rows[0]["text"] + " Now."}
            ),
            "41 rows",
        ),
        (lambda rows: rows[1].update(id=rows[0]["id"]), "ids are not unique"),
        (lambda rows: rows[1].update(text=rows[0]["text"]), "same text"),
        (
            lambda rows: [
                r.update(language="hi", id="gold-hi-" + r["id"][-3:])
                for r in rows
                if r["language"] == "en"
            ],
            "gap",
        ),
    ],
)
def test_a_set_of_the_wrong_size_or_with_repeats_is_refused(
    tmp_path: Path, change: Any, fragment: str
) -> None:
    assert any(fragment in p for p in _problems(tmp_path, change))


def test_dropping_a_scam_type_from_the_set_is_refused(tmp_path: Path) -> None:
    def drop(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            if row["scam_type"] == "lottery":
                row.update(scam_type="other_scam")

    assert any("lottery has 0 scam row(s)" in p for p in _problems(tmp_path, drop))


def test_a_set_where_every_scam_is_high_risk_is_refused(tmp_path: Path) -> None:
    def all_high(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            if row["is_scam"]:
                row["risk_level"] = "high"

    assert any("low, medium and high" in p for p in _problems(tmp_path, all_high))


def test_the_file_name_must_say_which_languages_it_holds(tmp_path: Path) -> None:
    problems = _problems(tmp_path, lambda rows: None, name="golden.jsonl")

    assert any("scam_golden_<lang>_<lang>.jsonl" in p for p in problems)
    problems = _problems(tmp_path, lambda rows: None, name="scam_golden_tl_id.jsonl")
    assert any("file name says" in p for p in problems)


# --- the spot check ---------------------------------------------------------------------


def test_the_spot_check_is_a_mixed_fixed_sample_of_the_asked_size() -> None:
    rows, _ = load_rows(GOLDEN)

    sample = pick_spot_check(rows, 10, seed=1)

    assert len(sample) == len({r.id for r in sample}) == 10
    assert sum(not r.is_scam for r in sample) >= 3
    assert {r.language for r in sample} == {"en", "hi"}
    assert sum(r.language == "en" for r in sample) in range(4, 7)
    assert len({r.scam_type for r in sample if r.is_scam}) >= 5
    assert [r.id for r in sample] == [r.id for r in pick_spot_check(rows, 10, seed=1)]
    assert [r.id for r in sample] != [r.id for r in pick_spot_check(rows, 10, seed=2)]


def test_the_command_lists_the_rows_to_review(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(GOLDEN), "--spot-check", "10"]) == 0

    out = capsys.readouterr().out
    assert out.count("  gold-") == 10 and out.count("why:") == 10


def test_the_review_requirement_fails_until_enough_rows_are_marked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = _rows()
    for row in rows:
        row["reviewed_by"] = None
    unreviewed = _write(tmp_path, rows)

    assert main([str(unreviewed), "--require-reviewed", "10"]) == 1
    assert "0 row(s) reviewed, 10 required" in capsys.readouterr().out

    for row in rows[:10]:
        row["reviewed_by"] = "PP"
    reviewed = _write(tmp_path, rows, name="scam_golden_en_hi.jsonl")

    assert main([str(reviewed), "--require-reviewed", "10"]) == 0
    assert main([str(reviewed), "--require-reviewed", "11"]) == 1
