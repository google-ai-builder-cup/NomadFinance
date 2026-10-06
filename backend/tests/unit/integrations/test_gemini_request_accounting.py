"""Every Gemini request leaves exactly one log line, so a metric can count quota use (NF-F0-016).

The daily limit is per model and counts every attempt, retries included. A request ends as a
`gemini_call` (answered), a `gemini_call_failed` (gave up) or a `gemini_retry` (failed, tried
again). Counting those three lines is the number of requests made; this file keeps that true.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from google.genai import errors as genai_errors

from app.config import get_settings
from app.integrations.gemini import GeminiError, ModelTier
from app.integrations.gemini.embeddings import EMBEDDING_DIMENSION
from tests.unit.integrations.test_gemini_client import OK, api_error, generate, make_client
from tests.unit.integrations.test_gemini_embeddings import _client as embed_client
from tests.unit.integrations.test_gemini_embeddings import _error as embed_error
from tests.unit.integrations.test_gemini_embeddings import _response as embed_response

pytestmark = pytest.mark.anyio

_REQUEST_LINES = ("gemini_call ", "gemini_call_failed ", "gemini_retry ")


def _request_lines(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage().startswith(_REQUEST_LINES)]


def _usage(record: logging.LogRecord) -> dict[str, Any]:
    fields: dict[str, Any] = record.__dict__["gemini_usage"]
    return fields


def _unavailable() -> genai_errors.APIError:
    return api_error(genai_errors.ServerError, 503, "UNAVAILABLE")


@pytest.mark.parametrize(
    ("failures", "answered"),
    [(0, True), (1, True), (2, True), (3, False)],
    ids=["first try", "one retry", "two retries", "gave up"],
)
async def test_one_line_per_request_to_a_model(
    caplog: pytest.LogCaptureFixture, failures: int, answered: bool
) -> None:
    outcomes: list[Any] = [_unavailable() for _ in range(failures)]
    if answered:
        outcomes.append(OK)
    client, fake = make_client(outcomes)

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        try:
            await generate(client)
        except GeminiError:
            assert not answered

    lines = _request_lines(caplog)
    # Whatever the outcome, the lines add up to the requests made.
    assert len(lines) == len(fake.calls)
    for record in lines:
        usage = _usage(record)
        assert usage["model"] == get_settings().gemini_model_reasoning
        assert usage["operation"] == "test.clause"
        assert usage["feature"] == "test"


async def test_a_retry_line_says_what_failed_and_which_attempt() -> None:
    client, _ = make_client([_unavailable(), OK])
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Capture()
    logging.getLogger("app.integrations.gemini").addHandler(handler)
    try:
        await generate(client)
    finally:
        logging.getLogger("app.integrations.gemini").removeHandler(handler)

    retry = next(r for r in records if r.getMessage().startswith("gemini_retry"))
    usage = _usage(retry)
    assert (usage["outcome"], usage["attempt"], usage["error"]) == (
        "retry",
        1,
        "GeminiUnavailableError",
    )
    assert usage["tier"] == ModelTier.REASONING.value


@pytest.mark.parametrize(
    ("failures", "answered"),
    [(0, True), (2, True), (3, False)],
    ids=["clean", "retried", "gave up"],
)
async def test_embeddings_are_counted_the_same_way(
    caplog: pytest.LogCaptureFixture, failures: int, answered: bool
) -> None:
    outcomes: list[Any] = [embed_error(genai_errors.ServerError, 503, "UNAVAILABLE")] * failures
    if answered:
        outcomes.append(embed_response([1.0] * EMBEDDING_DIMENSION))
    client, models = embed_client(outcomes)

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        try:
            await client.embed_text("x", operation="radar.embed")
        except GeminiError:
            assert not answered

    lines = _request_lines(caplog)
    assert len(lines) == len(models.calls)
    for record in lines:
        usage = _usage(record)
        assert usage["model"] == "gemini-embedding-001"
        assert usage["feature"] == "radar"
        assert usage["tier"] is None
