"""The markdown report of one eval run: docs/evals/scam-eval-<date>.md (NF-SA-014).

The report names no message text, only ids: the messages are in data-scripts/evals/ and the rows
that were wrong are listed with the label's own one-line reason, so a reviewer can read the
false alarms by hand (D-129) without opening three files.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from src.scam_eval.metrics import (
    LANGUAGE_F1_MIN,
    LOW_CONFIDENCE,
    OVERALL_F1_MIN,
    Counts,
    Evaluation,
    GateCheck,
    Mistake,
)


@dataclass(frozen=True)
class RunInfo:
    """What was scored and with what, so two reports can be told apart later."""

    when: datetime
    model: str
    prompt: str  # e.g. "scam.classify v2"
    taxonomy_hash: str  # the loader's `_meta.content_hash`, first digits
    golden_hash: str  # `metrics.fingerprint` of the rows
    # Where the messages came from; the stress set is scored with the same report.
    source: str = "evals/scam_golden_*.jsonl"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines.extend("| " + " | ".join(_cell(c) for c in row) + " |" for row in rows)
    return lines


def _f(value: float) -> str:
    return f"{value:.3f}"


def _headline(checks: Sequence[GateCheck]) -> str:
    short = [
        (
            f"{c.name} F1 {_f(c.f1)} is under {c.minimum}"
            if c.messages
            else f"{c.name} has no messages"
        )
        for c in checks
        if not c.met
    ]
    if not short:
        return "**Bar met.** Every group reaches its F1."
    return "**Bar not met:** " + "; ".join(short) + "."


def _bar(checks: Sequence[GateCheck]) -> list[str]:
    rows = [
        [
            "Overall" if c.name == "overall" else c.name,
            str(c.messages),
            _f(c.f1),
            f"{c.minimum:.2f}",
            "met" if c.met else "**not met**",
        ]
        for c in checks
    ]
    return _table(["Group", "Messages", "F1", "Bar", ""], rows)


def _scam_row(name: str, counts: Counts) -> list[str]:
    return [
        name,
        str(counts.total),
        str(counts.tp),
        str(counts.fn),
        str(counts.fp),
        str(counts.tn),
        _f(counts.precision),
        _f(counts.recall),
        _f(counts.f1),
    ]


def _by_language(evaluation: Evaluation) -> list[str]:
    rows = [_scam_row("All", evaluation.overall)]
    rows += [_scam_row(lang, counts) for lang, counts in evaluation.by_language.items()]
    header = ["Language", "Messages", "Caught", "Missed", "False alarm", "Passed"]
    return _table(header + ["Precision", "Recall", "F1"], rows)


def _per_class(evaluation: Evaluation) -> list[str]:
    rows = []
    for name in evaluation.classes:
        counts = evaluation.per_class(name)
        labelled = counts.tp + counts.fn
        rows.append(
            [
                name,
                str(labelled),
                f"{counts.tp} of {labelled}",
                _f(counts.precision),
                _f(counts.recall),
                _f(counts.f1),
            ]
        )
    return _table(["Class", "Messages", "Called right", "Precision", "Recall", "F1"], rows)


def _confidence(evaluation: Evaluation) -> list[str]:
    if not evaluation.confidence:
        return ["Not recorded."]
    rows = [
        [g.name, str(g.count), _f(g.lowest), _f(g.median), str(g.under_low)]
        for g in evaluation.confidence
    ]
    return [
        f"How sure the classifier said it was. Below {LOW_CONFIDENCE} the check screen tells the "
        'worker "we are not fully sure": on a right answer that is a mild fault, and a wrong '
        "answer given with high confidence gives the worker no warning at all.",
        "",
        *_table(["Answers", "Messages", "Lowest", "Median", f"Under {LOW_CONFIDENCE}"], rows),
    ]


def _confusion(evaluation: Evaluation) -> list[str]:
    classes = evaluation.classes
    legend = ", ".join(f"{i} = {name}" for i, name in enumerate(classes, start=1))
    rows = []
    for i, label in enumerate(classes, start=1):
        cells = []
        for said in classes:
            count = evaluation.confusion[label][said]
            cells.append("·" if count == 0 else (f"**{count}**" if said == label else str(count)))
        rows.append([f"{i} {label}", *cells])
    header = ["Label \\ Called", *(str(i) for i in range(1, len(classes) + 1))]
    return [f"Classes: {legend}.", "", *_table(header, rows)]


def _wrong(title: str, mistakes: Sequence[Mistake], *, benign: bool) -> list[str]:
    lines = [f"### {title} ({len(mistakes)})", ""]
    if not mistakes:
        return [*lines, "None.", ""]
    # The reason is the label's own one-line rationale, in English, from the golden file.
    header = ["Message", "Language", "Resembles" if benign else "Label", "Called", "Confidence"]
    rows = [
        [
            m.row.id,
            m.row.language,
            (m.row.resembles if benign else m.row.scam_type) or "",
            m.predicted,
            f"{m.confidence:.2f}",
            m.row.rationale,
        ]
        for m in mistakes
    ]
    return [*lines, *_table([*header, "Why the label is right"], rows), ""]


def render_report(evaluation: Evaluation, checks: Sequence[GateCheck], info: RunInfo) -> str:
    """The whole report as markdown."""
    scams = evaluation.overall.tp + evaluation.overall.fn
    benign = evaluation.overall.fp + evaluation.overall.tn
    kinds = ("false_alarm", "missed", "wrong_type")
    by_kind = {kind: [m for m in evaluation.mistakes if m.kind == kind] for kind in kinds}
    lines = [
        f"# Scam analyzer eval, {info.when:%Y-%m-%d}",
        "",
        _headline(checks),
        "",
        "Scores the Scam Analyzer's classifier (`scam.classify`) on the messages in "
        f"`data-scripts/{info.source}`. Written by `python -m evals.run_scam_eval`; "
        "the steps are in `docs/runbooks/NF-SA-014-scam-eval-runner.md`.",
        "",
        "| | |",
        "|---|---|",
        f"| Run at | {info.when:%Y-%m-%d %H:%M} UTC |",
        f"| Classifier | `{info.model}`, prompt `{info.prompt}` |",
        f"| Taxonomy | content hash `{info.taxonomy_hash}` |",
        f"| Message set | {evaluation.overall.total} messages ({scams} scams, {benign} benign), "
        f"fingerprint `{info.golden_hash}` |",
        "",
        "## Against the bar",
        "",
        f"F1 of scam against benign: at least {OVERALL_F1_MIN} overall and "
        f"{LANGUAGE_F1_MIN} in every language.",
        "",
        *_bar(checks),
        "",
        "## Scam against benign, by language",
        "",
        "Caught: a scam called a scam. Missed: a scam called benign. False alarm: a benign message "
        "called a scam. Passed: a benign message called benign. Precision is Caught out of "
        "everything called a scam; recall is Caught out of every scam.",
        "",
        *_by_language(evaluation),
        "",
        "## Per class",
        "",
        "One class against all the others. A scam called by the wrong type counts against both "
        "types. Read these as counts: a type has 6 to 12 messages in the whole set, so one "
        "message moves a figure by 8 points or more, and the bar is not set on them (D-129).",
        "",
        *_per_class(evaluation),
        "",
        "## Confidence",
        "",
        *_confidence(evaluation),
        "",
        "## Confusion matrix",
        "",
        *_confusion(evaluation),
        "",
        "## Wrong answers",
        "",
        *_wrong("False alarms: benign called a scam", by_kind["false_alarm"], benign=True),
        *_wrong("Missed scams: a scam called benign", by_kind["missed"], benign=False),
        *_wrong("Called a scam, but the wrong type", by_kind["wrong_type"], benign=False),
    ]
    return "\n".join(lines).rstrip() + "\n"
