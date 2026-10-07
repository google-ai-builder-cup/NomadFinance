"""Runs the golden messages through a classifier, a few at a time (NF-SA-014).

The classifier is passed in, so the loop is tested without Gemini and the backend is only loaded
when a real run starts (`src/scam_eval/backend.py`).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from src.scam_eval.metrics import Prediction
from src.validators.scam_golden import GoldenRow

Classify = Callable[[GoldenRow], Awaitable[Prediction]]
# Called as each message finishes: with its prediction, or the reason there is none.
Progress = Callable[[GoldenRow, Prediction | str], None]


class ClassifyError(RuntimeError):
    """The classifier could not answer for one message (Gemini failed after its own retries).

    Only this is recorded against the message and the run goes on. Any other exception is a bug
    in the eval or the backend and stops the run.
    """


@dataclass(frozen=True)
class Classifier:
    """A way to classify a message, and what the report says about it."""

    classify: Classify
    model: str
    prompt: str  # e.g. "scam.classify v2"


@dataclass(frozen=True)
class RunResult:
    """What a run produced, each in the order of the rows."""

    predictions: dict[str, Prediction]
    failures: dict[str, str]  # message id -> why it has no prediction


class _Pacer:
    """Lets at most `rpm` calls start a minute, however many are in flight; 0 is no limit.

    A free-tier key allows a few calls a minute, and the Gemini client's own retries (about 8
    seconds) cannot outlast that window, so a run that goes faster loses messages to 429s.
    """

    def __init__(self, rpm: int) -> None:
        if rpm < 0:
            raise ValueError("rpm cannot be negative")
        self._interval = 60.0 / rpm if rpm else 0.0
        self._next_start = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        if not self._interval:
            return
        async with self._lock:
            now = time.monotonic()
            start = max(now, self._next_start)
            self._next_start = start + self._interval
        if start > now:
            await asyncio.sleep(start - now)


async def run_eval(
    rows: Sequence[GoldenRow],
    classify: Classify,
    *,
    concurrency: int = 4,
    rpm: int = 0,
    progress: Progress | None = None,
) -> RunResult:
    """Classify every row, up to `concurrency` at once and at most `rpm` starts a minute.

    A message the classifier cannot answer for is returned in `failures`; the others still run,
    so one bad minute of quota does not cost the whole run.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    slots = asyncio.Semaphore(concurrency)
    pacer = _Pacer(rpm)
    predictions: dict[str, Prediction] = {}
    failures: dict[str, str] = {}

    async def one(row: GoldenRow) -> None:
        async with slots:
            await pacer.wait()
            outcome: Prediction | str
            try:
                outcome = await classify(row)
            except ClassifyError as exc:
                outcome = str(exc) or type(exc).__name__
        if isinstance(outcome, str):
            failures[row.id] = outcome
        else:
            predictions[row.id] = outcome
        if progress is not None:
            progress(row, outcome)

    await asyncio.gather(*(one(row) for row in rows))
    return RunResult(
        predictions={r.id: predictions[r.id] for r in rows if r.id in predictions},
        failures={r.id: failures[r.id] for r in rows if r.id in failures},
    )
