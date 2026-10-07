from __future__ import annotations

import pytest

from src.loaders.scam_patterns_calibrate import golden_rows
from src.scam_eval.metrics import (
    BENIGN,
    LANGUAGE_F1_MIN,
    LANGUAGES,
    OVERALL_F1_MIN,
    Counts,
    GateCheck,
    Prediction,
    evaluate,
    fingerprint,
    gate,
)
from src.validators.scam_golden import GoldenRow
from src.validators.scam_taxonomy import load_taxonomy


def classes() -> tuple[str, ...]:
    types = load_taxonomy().types
    return (*(n for n, e in sorted(types.items(), key=lambda i: i[1].order)), BENIGN)


def oracle(rows: list[GoldenRow]) -> dict[str, Prediction]:
    """A classifier that is always right."""
    return {r.id: Prediction(r.is_scam, r.scam_type, 0.9) for r in rows}


def first(rows: list[GoldenRow], *, scam: bool, language: str = "en") -> GoldenRow:
    return next(r for r in rows if r.is_scam == scam and r.language == language)


@pytest.fixture(scope="module")
def rows() -> list[GoldenRow]:
    return golden_rows()


def test_the_bar_is_the_one_the_tracker_and_the_golden_set_page_name() -> None:
    assert OVERALL_F1_MIN == 0.85
    assert LANGUAGE_F1_MIN == 0.75
    assert LANGUAGES == ("en", "hi", "tl", "id", "ne", "bn")


def test_precision_recall_and_f1_come_from_the_counts() -> None:
    counts = Counts(tp=8, fp=2, fn=4, tn=6)

    assert counts.total == 20
    assert counts.precision == 0.8
    assert counts.recall == pytest.approx(8 / 12)
    assert counts.f1 == pytest.approx(16 / 22)


def test_f1_that_is_exactly_the_bar_is_not_lost_to_rounding() -> None:
    # 34 right out of 40 is 0.85: it must meet a bar of 0.85, not fall a hair under it.
    assert Counts(tp=17, fp=3, fn=3).f1 == 0.85
    assert GateCheck("overall", 40, Counts(tp=17, fp=3, fn=3).f1, OVERALL_F1_MIN).met
    assert not GateCheck("overall", 40, 0.8499, OVERALL_F1_MIN).met


def test_a_question_nobody_answered_scores_zero_not_an_error() -> None:
    assert Counts().f1 == Counts().precision == Counts().recall == 0.0
    assert Counts(tn=5).f1 == 0.0


def test_a_group_with_no_messages_cannot_meet_the_bar() -> None:
    assert not GateCheck("hi", 0, 1.0, LANGUAGE_F1_MIN).met


def test_right_answers_everywhere_meet_the_bar(rows: list[GoldenRow]) -> None:
    evaluation = evaluate(rows, oracle(rows), classes())

    assert (evaluation.overall.tp, evaluation.overall.tn) == (84, 36)
    assert evaluation.overall.f1 == 1.0
    assert evaluation.mistakes == []
    assert set(evaluation.by_language) == set(LANGUAGES)
    assert all(c.met for c in gate(evaluation))
    assert [c.name for c in gate(evaluation)] == ["overall", *LANGUAGES]
    for name in evaluation.classes:
        row = evaluation.confusion[name]
        assert row[name] == sum(row.values()) > 0  # only the diagonal is filled


def test_a_classifier_that_calls_everything_benign_fails_every_part_of_the_bar(
    rows: list[GoldenRow],
) -> None:
    calm = {r.id: Prediction(False, None, 0.9) for r in rows}

    evaluation = evaluate(rows, calm, classes())

    assert evaluation.overall.f1 == 0.0
    assert [c.met for c in gate(evaluation)] == [False] * 7
    assert {m.kind for m in evaluation.mistakes} == {"missed"}
    assert len(evaluation.mistakes) == 84


def test_a_false_alarm_costs_precision_in_its_own_language_only(rows: list[GoldenRow]) -> None:
    benign = first(rows, scam=False, language="hi")
    answers = oracle(rows)
    answers[benign.id] = Prediction(True, benign.resembles, 0.8)

    evaluation = evaluate(rows, answers, classes())

    assert evaluation.by_language["hi"].fp == 1
    assert evaluation.by_language["hi"].precision < 1.0
    assert all(c.fp == 0 for lang, c in evaluation.by_language.items() if lang != "hi")
    assert evaluation.confusion[BENIGN][benign.resembles or ""] == 1
    [mistake] = evaluation.mistakes
    assert (mistake.kind, mistake.row.id, mistake.confidence) == ("false_alarm", benign.id, 0.8)


def test_a_scam_called_by_the_wrong_type_is_still_caught_but_counts_against_both_types(
    rows: list[GoldenRow],
) -> None:
    scam = first(rows, scam=True)
    other = "lottery" if scam.scam_type != "lottery" else "loan_app_trap"
    answers = oracle(rows)
    answers[scam.id] = Prediction(True, other, 0.7)

    evaluation = evaluate(rows, answers, classes())

    assert evaluation.overall.f1 == 1.0  # scam against benign does not see the type
    assert evaluation.per_class(scam.scam_type or "").fn == 1
    assert evaluation.per_class(other).fp == 1
    [mistake] = evaluation.mistakes
    assert mistake.kind == "wrong_type"


def test_per_class_counts_add_up_for_every_class(rows: list[GoldenRow]) -> None:
    answers = oracle(rows)
    answers[first(rows, scam=True).id] = Prediction(False, None, 0.6)
    answers[first(rows, scam=False, language="tl").id] = Prediction(True, "other_scam", 0.6)

    evaluation = evaluate(rows, answers, classes())

    for name in evaluation.classes:
        assert evaluation.per_class(name).total == len(rows)
    benign = evaluation.per_class(BENIGN)
    assert (benign.tp, benign.fp, benign.fn) == (
        35,
        1,
        1,
    )  # one scam called benign, one the reverse


def test_a_scam_with_no_type_is_filed_as_other_scam(rows: list[GoldenRow]) -> None:
    benign = first(rows, scam=False)
    answers = oracle(rows)
    answers[benign.id] = Prediction(True, None, 0.5)

    evaluation = evaluate(rows, answers, classes())

    assert evaluation.confusion[BENIGN]["other_scam"] == 1


def test_a_language_missing_from_the_rows_fails_the_bar(rows: list[GoldenRow]) -> None:
    without_hindi = [r for r in rows if r.language != "hi"]

    checks = {c.name: c for c in gate(evaluate(without_hindi, oracle(without_hindi), classes()))}

    assert checks["hi"].messages == 0 and not checks["hi"].met
    assert checks["overall"].met and checks["en"].met


def test_a_row_without_an_answer_is_an_error(rows: list[GoldenRow]) -> None:
    answers = oracle(rows)
    del answers[rows[0].id]

    with pytest.raises(ValueError, match=rows[0].id):
        evaluate(rows, answers, classes())


def test_a_class_outside_the_list_is_an_error(rows: list[GoldenRow]) -> None:
    answers = oracle(rows)
    answers[first(rows, scam=True).id] = Prediction(True, "made_up_type", 0.9)

    with pytest.raises(ValueError, match="made_up_type"):
        evaluate(rows, answers, classes())


def test_the_fingerprint_follows_what_is_scored_and_nothing_else(rows: list[GoldenRow]) -> None:
    row = rows[0]
    base = fingerprint(rows)

    assert base == fingerprint(list(reversed(rows)))  # the order of the files does not matter
    assert len(base) == 12
    reviewed = row.model_copy(update={"reviewed_by": "ZZ", "rationale": "A different reason."})
    assert fingerprint([reviewed, *rows[1:]]) == base
    for change in ({"text": row.text + " Reply now."}, {"is_scam": not row.is_scam}):
        assert fingerprint([row.model_copy(update=change), *rows[1:]]) != base
    retyped = "lottery" if row.scam_type != "lottery" else "loan_app_trap"
    assert fingerprint([row.model_copy(update={"scam_type": retyped}), *rows[1:]]) != base
