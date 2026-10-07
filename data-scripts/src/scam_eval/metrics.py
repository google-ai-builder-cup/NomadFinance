"""Scoring for the Scam Analyzer eval (NF-SA-014): the classifier's answers against the labels.

Plain arithmetic over golden rows and predictions, so it runs with no backend, key or network.

Two questions are scored. *Is it a scam* (scam is the positive class) is what the bar is set on:
F1 of at least 0.85 overall and 0.75 in every language (docs/evals/scam-golden-set.md). *Which
class* (one scam type, or benign) is reported beside it as per-class figures and a confusion
matrix, but not gated: a type has 6 to 12 messages in the whole set, so one message moves its
figures by 8 points or more (D-129).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, get_args

from src.validators.scam_golden import GoldenRow, Language

BENIGN = "benign"
# The backend files a scam under this when the model names no type that exists.
FALLBACK_TYPE = "other_scam"

OVERALL_F1_MIN = 0.85
LANGUAGE_F1_MIN = 0.75
LANGUAGES: tuple[str, ...] = get_args(Language)

MistakeKind = Literal["false_alarm", "missed", "wrong_type"]


@dataclass(frozen=True)
class Prediction:
    """What the classifier said about one message."""

    is_scam: bool
    scam_type: str | None
    confidence: float


@dataclass(frozen=True)
class Counts:
    """Right and wrong answers to one yes/no question, e.g. "is it a scam"."""

    tp: int = 0  # said yes, and it is
    fp: int = 0  # said yes, and it is not
    fn: int = 0  # said no, and it is
    tn: int = 0  # said no, and it is not

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.fn + self.tn

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        # From the counts, not from precision and recall: one division, so 34 right out of 40
        # is exactly the 0.85 the bar names and not a rounding of it.
        denominator = 2 * self.tp + self.fp + self.fn
        return 2 * self.tp / denominator if denominator else 0.0


@dataclass(frozen=True)
class Mistake:
    """A message the classifier got wrong as a class: a scam given the wrong type counts."""

    row: GoldenRow
    predicted: str
    confidence: float

    @property
    def kind(self) -> MistakeKind:
        if not self.row.is_scam:
            return "false_alarm"
        return "missed" if self.predicted == BENIGN else "wrong_type"


@dataclass(frozen=True)
class Evaluation:
    """Every figure of one run."""

    classes: tuple[str, ...]
    overall: Counts  # scam against benign
    by_language: dict[str, Counts]  # the same, per language present in the rows
    confusion: dict[str, dict[str, int]]  # confusion[label][what the classifier said]
    mistakes: list[Mistake]

    def per_class(self, name: str) -> Counts:
        """One class against all the others, read off the confusion matrix."""
        right = self.confusion[name][name]
        labelled = sum(self.confusion[name].values())
        said = sum(row[name] for row in self.confusion.values())
        return Counts(
            tp=right,
            fp=said - right,
            fn=labelled - right,
            tn=self.overall.total - labelled - said + right,
        )


@dataclass(frozen=True)
class GateCheck:
    """One line of the bar: a group of messages and the F1 it must reach."""

    name: str  # "overall" or a language code
    messages: int
    f1: float
    minimum: float

    @property
    def met(self) -> bool:
        # A language with no messages has not been scored, so it cannot have passed.
        return self.messages > 0 and self.f1 >= self.minimum


def true_class(row: GoldenRow) -> str:
    return (row.scam_type or FALLBACK_TYPE) if row.is_scam else BENIGN


def predicted_class(prediction: Prediction) -> str:
    return (prediction.scam_type or FALLBACK_TYPE) if prediction.is_scam else BENIGN


def _scam_counts(rows: Iterable[GoldenRow], predictions: Mapping[str, Prediction]) -> Counts:
    tp = fp = fn = tn = 0
    for row in rows:
        said_scam = predictions[row.id].is_scam
        if row.is_scam and said_scam:
            tp += 1
        elif said_scam:
            fp += 1
        elif row.is_scam:
            fn += 1
        else:
            tn += 1
    return Counts(tp, fp, fn, tn)


def evaluate(
    rows: Sequence[GoldenRow], predictions: Mapping[str, Prediction], classes: Sequence[str]
) -> Evaluation:
    """Score `predictions` (by message id) against the labels of `rows`.

    Args:
        rows: The golden messages that were run.
        predictions: One prediction per row id.
        classes: Every class a message can be labelled or called: the scam types, then benign.

    Raises:
        ValueError: A row has no prediction, or a label or prediction names a class that is not
            in `classes`.
    """
    missing = [row.id for row in rows if row.id not in predictions]
    if missing:
        raise ValueError(f"no answer for {len(missing)} message(s), first {missing[0]}")
    confusion = {label: dict.fromkeys(classes, 0) for label in classes}
    mistakes: list[Mistake] = []
    for row in rows:
        prediction = predictions[row.id]
        label, said = true_class(row), predicted_class(prediction)
        for name in (label, said):
            if name not in confusion:
                raise ValueError(f"{row.id}: {name!r} is not one of the classes {list(classes)}")
        confusion[label][said] += 1
        if label != said:
            mistakes.append(Mistake(row, said, prediction.confidence))
    by_language = {
        language: _scam_counts((r for r in rows if r.language == language), predictions)
        for language in LANGUAGES
        if any(r.language == language for r in rows)
    }
    return Evaluation(
        classes=tuple(classes),
        overall=_scam_counts(rows, predictions),
        by_language=by_language,
        confusion=confusion,
        mistakes=mistakes,
    )


def gate(evaluation: Evaluation) -> list[GateCheck]:
    """The bar, overall first and then each of the six languages."""
    checks = [GateCheck("overall", evaluation.overall.total, evaluation.overall.f1, OVERALL_F1_MIN)]
    for language in LANGUAGES:
        counts = evaluation.by_language.get(language, Counts())
        checks.append(GateCheck(language, counts.total, counts.f1, LANGUAGE_F1_MIN))
    return checks


def fingerprint(rows: Iterable[GoldenRow]) -> str:
    """Twelve hex digits that change when a message, its route or the label it is scored on does.

    Reviewer initials and rationales are left out: they do not change what is scored. Two reports
    with different fingerprints measured different benchmarks (docs/evals/scam-golden-set.md,
    "Changing a set").
    """
    canonical = json.dumps(
        [
            [r.id, r.language, r.text, r.corridor_id, r.is_scam, r.scam_type]
            for r in sorted(rows, key=lambda r: r.id)
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
