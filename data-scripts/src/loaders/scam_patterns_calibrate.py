"""Choose the "similar enough to show" cutoff of the Scam Analyzer's neighbour search (NF-SA-010).

Run from data-scripts/:  python -m src.loaders.scam_patterns_calibrate

The backend shows a known scam as a neighbour of a message when its cosine similarity is at least
a cutoff (`PATTERN_MIN_SCORE` in backend/app/services/scam/retrieval.py). Too low, and a safe
message is told it looks like a known scam; too high, and a real scam shows nothing. This scores,
for every golden message (the scams and the benign look-alikes of evals/scam_golden_*.jsonl), the
similarity of its closest template, as the backend will: redacted first, embedded the same way.
Then it shows how many scams and how many safe messages each cutoff would let through.

The benign look-alikes are the hard half: each imitates a scam type and gets it right (a bank's
real one-time-password text, an agency that says "you pay no fee"). A cutoff that keeps them out
and still shows most scams is the one to use. Needs GEMINI_API_KEY; about 600 embeddings, which
on the free tier (100 a minute) takes about 6 minutes.
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from src.config import EVALS_DIR, SCAM_PATTERNS_DIR
from src.embedding import CachedEmbedder, Embedder, EmbeddingQuotaError
from src.loaders.scam_patterns_check import cosine_neighbours, load_redactor
from src.validators.scam_golden import GoldenRow, load_rows
from src.validators.scam_patterns import check_library, load_all

log = logging.getLogger(__name__)

QUOTA_EXIT_CODE = 2  # not a failure of the data: run again later
SHOWN_THRESHOLDS = (0.70, 0.75, 0.80, 0.85, 0.90)
_SCAN = [t / 1000 for t in range(500, 1000, 5)]


def golden_rows(directory: Path = EVALS_DIR) -> list[GoldenRow]:
    """Every row of every golden set, scams and benign, in id order."""
    rows: list[GoldenRow] = []
    for path in sorted(directory.glob("scam_golden_*.jsonl")):
        loaded, problems = load_rows(path)
        if problems:
            raise ValueError(f"{path.name}: {problems[0]}")
        rows.extend(loaded)
    return sorted(rows, key=lambda r: r.id)


def share_at_or_above(scores: Sequence[float], cutoff: float) -> float:
    """The share of `scores` a cutoff lets through."""
    return sum(s >= cutoff for s in scores) / len(scores) if scores else 0.0


def suggest_cutoff(scam_scores: Sequence[float], benign_scores: Sequence[float]) -> float:
    """The cutoff that shows the most scams for the fewest safe messages (Youden's J), the
    higher one on a tie: showing nothing is safer than showing a wrong match."""
    return max(
        _SCAN,
        key=lambda t: (share_at_or_above(scam_scores, t) - share_at_or_above(benign_scores, t), t),
    )


def best_scores(
    rows: Sequence[GoldenRow],
    embedder: Embedder,
    library: list[tuple[str, list[float]]],
    redact: Callable[[str], str],
) -> list[tuple[GoldenRow, str, float]]:
    """For each row: the id and the similarity of its closest template."""
    vectors = embedder.embed([redact(r.text) for r in rows])
    out = []
    for row, vector in zip(rows, vectors, strict=True):
        pattern_id, score = cosine_neighbours(vector, library, 1)[0]
        out.append((row, pattern_id, score))
    return out


def _spread(scores: Sequence[float]) -> str:
    ordered = sorted(scores)
    p10 = ordered[len(ordered) // 10]
    return (
        f"min {ordered[0]:.3f}  p10 {p10:.3f}  median {statistics.median(ordered):.3f}  "
        f"max {ordered[-1]:.3f}"
    )


def report(scored: Sequence[tuple[GoldenRow, str, float]]) -> float:
    """Print the evidence and return the suggested cutoff."""
    scams = [(r, p, s) for r, p, s in scored if r.is_scam]
    benign = [(r, p, s) for r, p, s in scored if not r.is_scam]
    scam_scores = [s for _, _, s in scams]
    benign_scores = [s for _, _, s in benign]
    print(f"Closest-template similarity of {len(scams)} scams:   {_spread(scam_scores)}")
    print(f"Closest-template similarity of {len(benign)} benign:  {_spread(benign_scores)}")
    print("\ncutoff   scams shown   safe messages shown")
    for cutoff in SHOWN_THRESHOLDS:
        print(
            f"{cutoff:.2f}     {share_at_or_above(scam_scores, cutoff):>10.0%}"
            f"   {share_at_or_above(benign_scores, cutoff):>18.0%}"
        )
    print("\nThe 8 safe messages closest to a known scam (they decide the cutoff):")
    for row, pattern_id, score in sorted(benign, key=lambda x: x[2], reverse=True)[:8]:
        print(f"  {score:.3f} {row.id} (resembles {row.resembles}) nearest {pattern_id}")
    print("\nThe 5 scams furthest from any template:")
    for row, pattern_id, score in sorted(scams, key=lambda x: x[2])[:5]:
        print(f"  {score:.3f} {row.id} ({row.scam_type}) nearest {pattern_id}")
    suggested = suggest_cutoff(scam_scores, benign_scores)
    print(
        f"\nSuggested cutoff: {suggested:.3f} "
        f"(shows {share_at_or_above(scam_scores, suggested):.0%} of scams, "
        f"{share_at_or_above(benign_scores, suggested):.0%} of safe messages)"
    )
    return suggested


def main(argv: list[str] | None = None) -> int:
    from src.embedding import GeminiEmbedder

    argparse.ArgumentParser(description="Choose the similar-scam cutoff.").parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # The report prints Hindi, Nepali and Bengali ids only, but keep a Windows console happy.
    if reconfigure := getattr(sys.stdout, "reconfigure", None):
        reconfigure(encoding="utf-8")

    patterns, problems = load_all(SCAM_PATTERNS_DIR)
    problems = problems or check_library(patterns)
    if problems:
        log.error("the pattern library is not valid: %s", problems[0])
        return 1
    embedder = CachedEmbedder(GeminiEmbedder())
    try:
        vectors = embedder.embed([p.text for p in patterns])
        library = [(p.id, v) for p, v in zip(patterns, vectors, strict=True)]
        report(best_scores(golden_rows(), embedder, library, load_redactor()))
    except EmbeddingQuotaError as exc:
        log.error("%s", exc)
        return QUOTA_EXIT_CODE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
