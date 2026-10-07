"""Score the Scam Analyzer's classifier against the golden messages (NF-SA-014).

Run from data-scripts/:  python -m evals.run_scam_eval

Sends the 120 messages of evals/scam_golden_*.jsonl through the backend's classifier, which calls
Gemini, so GEMINI_API_KEY must be in this shell or in backend/.env.local. Scores the answers
against the labels and writes the report to docs/evals/scam-eval-<date>.md.

  --report PATH     write the report here instead
  --rows PATH       score the messages of this one file (a golden-format JSONL, such as the
                    stress set evals/scam_stress_en_hi.jsonl) instead of the three golden sets.
                    The bar then applies to the languages the file has
  --limit N         try the setup on N messages spread over the languages: nothing is scored
  --concurrency N   calls in flight at once (default 4)
  --rpm N           start at most N calls a minute (default no limit; a free-tier key needs
                    about 10, or its quota runs out part way)

Exit code: 0 the bar is met; 1 it is not (the report is written either way); 2 not scored, because
a message got no answer or the setup is incomplete. The bar is F1 of scam against benign of at
least 0.85 overall and 0.75 in every language (docs/evals/scam-golden-set.md).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from src.config import EVAL_REPORT_DIR
from src.loaders.scam_patterns_calibrate import golden_rows
from src.loaders.scam_taxonomy import content_hash
from src.scam_eval.backend import SetupError, load_backend_classifier
from src.scam_eval.metrics import (
    BENIGN,
    Prediction,
    evaluate,
    fingerprint,
    gate,
    predicted_class,
    true_class,
)
from src.scam_eval.report import RunInfo, render_report
from src.scam_eval.runner import Classifier, Progress, run_eval
from src.validators.scam_golden import GoldenRow, load_rows
from src.validators.scam_taxonomy import Taxonomy, load_taxonomy

NOT_SCORED = 2


def _spread(rows: list[GoldenRow], limit: int) -> list[GoldenRow]:
    """`limit` rows taken evenly from the whole list, so a few still touch every language."""
    return rows[:: max(1, len(rows) // limit)][:limit]


def _progress(total: int) -> Progress:
    done = 0

    def show(row: GoldenRow, outcome: Prediction | str) -> None:
        nonlocal done
        done += 1
        if isinstance(outcome, str):
            line = f"FAILED  {' '.join(outcome.split())[:200]}"
        else:
            label, said = true_class(row), predicted_class(outcome)
            line = f"{'ok    ' if said == label else 'WRONG '}  label {label}, called {said}"
        print(f"[{done:>3}/{total}] {row.id}  {line}", flush=True)

    return show


def run(
    args: argparse.Namespace, rows: list[GoldenRow], taxonomy: Taxonomy, classifier: Classifier
) -> int:
    """Run the messages, score them and write the report; returns the exit code."""
    partial = args.limit is not None and args.limit < len(rows)
    chosen = _spread(rows, args.limit) if partial else rows
    started = datetime.now(UTC)
    print(f"Classifier {classifier.model}, prompt {classifier.prompt}: {len(chosen)} messages")
    result = asyncio.run(
        run_eval(
            chosen,
            classifier.classify,
            concurrency=args.concurrency,
            rpm=args.rpm,
            progress=_progress(len(chosen)),
        )
    )
    if result.failures:
        print(f"\n{len(result.failures)} message(s) got no answer, so nothing was scored:")
        for message_id, why in result.failures.items():
            print(f"  {message_id}  {' '.join(why.split())[:200]}")
        print("Run again, with a lower --concurrency or an --rpm if the quota ran out.")
        return NOT_SCORED
    if partial:
        print("\nPartial run: no report written and no bar applied.")
        return 0

    ordered = sorted(taxonomy.types.items(), key=lambda item: item[1].order)
    classes = (*(name for name, _ in ordered), BENIGN)
    evaluation = evaluate(chosen, result.predictions, classes)
    own_set: Path | None = getattr(args, "rows", None)
    # A set of one or two languages is scored on those; the golden sets must cover all six.
    checks = gate(evaluation, only_present=own_set is not None)
    info = RunInfo(
        when=started,
        model=classifier.model,
        prompt=classifier.prompt,
        taxonomy_hash=content_hash(taxonomy)[:12],
        golden_hash=fingerprint(chosen),
        source=f"evals/{own_set.name}" if own_set is not None else RunInfo.source,
    )
    name = f"scam-eval-{own_set.stem}-" if own_set is not None else "scam-eval-"
    path: Path = args.report or EVAL_REPORT_DIR / f"{name}{started:%Y-%m-%d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_report(evaluation, checks, info).encode("utf-8"))

    print("\nScam against benign (F1, bar):")
    for check in checks:
        verdict = "met" if check.met else "NOT MET"
        print(f"  {check.name:<8}{check.f1:.3f}  >= {check.minimum:.2f}  {verdict}")
    print(f"Report: {path}")
    return 0 if all(check.met for check in checks) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the scam classifier on the golden set.")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--rows", type=Path, metavar="PATH")
    parser.add_argument("--limit", type=int, metavar="N")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--rpm", type=int, default=0)
    args = parser.parse_args(argv)
    if (args.limit is not None and args.limit < 1) or args.concurrency < 1 or args.rpm < 0:
        parser.error("--limit and --concurrency must be at least 1 and --rpm at least 0")
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    if reconfigure := getattr(sys.stdout, "reconfigure", None):
        # A Windows console is not UTF-8, and the reason a call failed can say anything.
        reconfigure(encoding="utf-8")

    try:
        if args.rows is not None:
            rows, problems = load_rows(args.rows)
            if problems or not rows:
                raise ValueError(f"{args.rows.name}: {problems[0] if problems else 'no rows'}")
        else:
            rows = golden_rows()
        taxonomy = load_taxonomy()
        classifier = load_backend_classifier(taxonomy)
    except (SetupError, ValueError, OSError) as exc:
        print(f"FAIL {exc}")
        return NOT_SCORED
    return run(args, rows, taxonomy, classifier)


if __name__ == "__main__":
    sys.exit(main())
