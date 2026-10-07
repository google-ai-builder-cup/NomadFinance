from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.loaders.scam_patterns_calibrate import golden_rows
from src.scam_eval.metrics import BENIGN, Prediction, evaluate, gate
from src.scam_eval.report import RunInfo, render_report
from src.validators.scam_golden import GoldenRow
from tests.test_scam_eval_metrics import classes, first, oracle

INFO = RunInfo(
    when=datetime(2026, 10, 30, 9, 15, tzinfo=UTC),
    model="gemini-test-model",
    prompt="scam.classify v2",
    taxonomy_hash="0a1b2c3d4e5f",
    golden_hash="9f8e7d6c5b4a",
)


@pytest.fixture(scope="module")
def rows() -> list[GoldenRow]:
    return golden_rows()


def report_for(rows: list[GoldenRow], answers: dict[str, Prediction]) -> str:
    evaluation = evaluate(rows, answers, classes())
    return render_report(evaluation, gate(evaluation), INFO)


def test_a_run_that_meets_the_bar_says_so_and_lists_no_wrong_answers(
    rows: list[GoldenRow],
) -> None:
    report = report_for(rows, oracle(rows))

    assert report.startswith("# Scam analyzer eval, 2026-10-30\n")
    assert "**Bar met.**" in report
    assert report.count("None.") == 3
    assert report.endswith("\n") and not report.endswith("\n\n")


def test_the_report_says_what_was_scored_and_with_what(rows: list[GoldenRow]) -> None:
    report = report_for(rows, oracle(rows))

    for fact in (
        "2026-10-30 09:15 UTC",
        "`gemini-test-model`, prompt `scam.classify v2`",
        "content hash `0a1b2c3d4e5f`",
        "120 messages (84 scams, 36 benign), fingerprint `9f8e7d6c5b4a`",
    ):
        assert fact in report


def test_every_language_and_every_class_has_a_line(rows: list[GoldenRow]) -> None:
    report = report_for(rows, oracle(rows))

    for language in ("en", "hi", "tl", "id", "ne", "bn"):
        assert f"| {language} | 20 |" in report
    for name in classes():
        assert f"| {name} | " in report
    assert "| Overall | 120 | 1.000 | 0.85 | met |" in report


def test_the_confusion_matrix_marks_the_diagonal_and_hides_the_zeros(
    rows: list[GoldenRow],
) -> None:
    report = report_for(rows, oracle(rows))

    assert "Classes: 1 = fake_job_offer," in report
    assert f", 9 = {BENIGN}." in report
    assert "| 9 benign | · | · | · | · | · | · | · | · | **36** |" in report


def test_a_run_below_the_bar_names_what_missed_it(rows: list[GoldenRow]) -> None:
    calm = {r.id: Prediction(False, None, 0.9) for r in rows}

    report = report_for(rows, calm)

    assert "**Bar not met:** overall F1 0.000 is under 0.85; en F1 0.000 is under 0.75" in report
    assert "**not met**" in report


def section(report: str, title: str) -> str:
    start = report.index(f"### {title}")
    end = report.find("\n### ", start + 1)
    return report[start:] if end == -1 else report[start:end]


def test_wrong_answers_are_listed_by_kind_with_the_labels_reason(rows: list[GoldenRow]) -> None:
    benign = first(rows, scam=False)
    missed = first(rows, scam=True, language="id")
    wrong_type = first(rows, scam=True, language="ne")
    answers = oracle(rows)
    answers[benign.id] = Prediction(True, "lottery", 0.91)
    answers[missed.id] = Prediction(False, None, 0.55)
    answers[wrong_type.id] = Prediction(True, "other_scam", 0.62)

    report = report_for(rows, answers)

    alarms = section(report, "False alarms: benign called a scam (1)")
    row = f"| {benign.id} | en | {benign.resembles} | lottery | 0.91 | {benign.rationale} |"
    assert row in alarms
    misses = section(report, "Missed scams: a scam called benign (1)")
    assert f"| {missed.id} | id | {missed.scam_type} | benign | 0.55 |" in misses
    types = section(report, "Called a scam, but the wrong type (1)")
    assert f"| {wrong_type.id} | ne | {wrong_type.scam_type} | other_scam | 0.62 |" in types


def test_a_pipe_in_a_reason_cannot_break_the_table(rows: list[GoldenRow]) -> None:
    benign = first(rows, scam=False)
    pipe = benign.model_copy(update={"rationale": "Asks for nothing | and says so."})
    changed = [pipe if r.id == benign.id else r for r in rows]
    answers = oracle(rows)
    answers[benign.id] = Prediction(True, "lottery", 0.9)

    report = report_for(changed, answers)

    assert "Asks for nothing \\| and says so." in report


def test_the_report_holds_ids_but_never_a_message(rows: list[GoldenRow]) -> None:
    benign = first(rows, scam=False)
    answers = oracle(rows)
    answers[benign.id] = Prediction(True, "lottery", 0.9)

    report = report_for(rows, answers)

    assert benign.id in report
    assert not [r.id for r in rows if r.text in report]


def test_the_same_run_gives_the_same_report(rows: list[GoldenRow]) -> None:
    assert report_for(rows, oracle(rows)) == report_for(rows, oracle(rows))
