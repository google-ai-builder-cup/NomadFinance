from __future__ import annotations

import asyncio
import time

import pytest

from src.loaders.scam_patterns_calibrate import golden_rows
from src.scam_eval.metrics import Prediction
from src.scam_eval.runner import ClassifyError, run_eval
from src.validators.scam_golden import GoldenRow


@pytest.fixture(scope="module")
def rows() -> list[GoldenRow]:
    return golden_rows()[:12]


async def right(row: GoldenRow) -> Prediction:
    return Prediction(row.is_scam, row.scam_type, 0.9)


def test_every_row_is_answered_and_the_answers_keep_the_order_of_the_rows(
    rows: list[GoldenRow],
) -> None:
    async def slow_at_the_start(row: GoldenRow) -> Prediction:
        # The first rows finish last, so the order of finishing is not the order of the rows.
        await asyncio.sleep(0.02 * (len(rows) - rows.index(row)))
        return await right(row)

    result = asyncio.run(run_eval(rows, slow_at_the_start, concurrency=12))

    assert list(result.predictions) == [r.id for r in rows]
    assert result.failures == {}


def test_a_message_the_classifier_cannot_answer_is_recorded_and_the_rest_still_run(
    rows: list[GoldenRow],
) -> None:
    broken = rows[3].id

    async def classify(row: GoldenRow) -> Prediction:
        if row.id == broken:
            raise ClassifyError("GeminiRateLimitError: quota")
        return await right(row)

    result = asyncio.run(run_eval(rows, classify))

    assert result.failures == {broken: "GeminiRateLimitError: quota"}
    assert broken not in result.predictions
    assert len(result.predictions) == len(rows) - 1


def test_a_bug_is_not_swallowed_as_a_failed_message(rows: list[GoldenRow]) -> None:
    async def classify(row: GoldenRow) -> Prediction:
        raise KeyError("not a Gemini failure")

    with pytest.raises(KeyError):
        asyncio.run(run_eval(rows, classify))


def test_no_more_calls_run_at_once_than_asked(rows: list[GoldenRow]) -> None:
    running = peak = 0

    async def classify(row: GoldenRow) -> Prediction:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return await right(row)

    asyncio.run(run_eval(rows, classify, concurrency=3))

    assert peak == 3


def test_calls_are_started_no_faster_than_the_rate_asked(rows: list[GoldenRow]) -> None:
    started: list[float] = []

    async def classify(row: GoldenRow) -> Prediction:
        started.append(time.monotonic())
        return await right(row)

    asyncio.run(run_eval(rows[:5], classify, concurrency=5, rpm=1200))  # one every 0.05 s

    # Four gaps of 0.05 s; half of that is allowed for the coarse clock of a Windows timer.
    assert started[-1] - started[0] >= 0.1


def test_progress_is_reported_once_per_message_with_the_answer_or_the_reason(
    rows: list[GoldenRow],
) -> None:
    seen: dict[str, Prediction | str] = {}

    async def classify(row: GoldenRow) -> Prediction:
        if row.id == rows[0].id:
            raise ClassifyError("timed out")
        return await right(row)

    asyncio.run(
        run_eval(rows, classify, progress=lambda row, outcome: seen.update({row.id: outcome}))
    )

    assert set(seen) == {r.id for r in rows}
    assert seen[rows[0].id] == "timed out"
    assert isinstance(seen[rows[1].id], Prediction)


@pytest.mark.parametrize(("concurrency", "rpm"), [(0, 0), (1, -1)])
def test_nonsense_limits_are_refused(rows: list[GoldenRow], concurrency: int, rpm: int) -> None:
    with pytest.raises(ValueError):
        asyncio.run(run_eval(rows, right, concurrency=concurrency, rpm=rpm))
