from __future__ import annotations

import logging
from typing import Any

import pytest
from pydantic import BaseModel

from app.integrations.gemini import GeminiUnavailableError, ModelTier
from app.integrations.gemini.usage import feature_of, log_usage
from tests.unit.integrations.gemini_fakes import make_client, text_response, unavailable, usage

pytestmark = pytest.mark.anyio


class Verdict(BaseModel):
    is_scam: bool


def records(caplog: pytest.LogCaptureFixture, prefix: str) -> list[dict[str, Any]]:
    return [r.__dict__["gemini_usage"] for r in caplog.records if r.getMessage().startswith(prefix)]


@pytest.mark.parametrize(
    ("operation", "feature"),
    [
        ("contract.extract", "contract"),
        ("radar.embed", "radar"),
        ("fib.synthesize_narrative", "fib"),
        ("coach.reply", "coach"),
        ("scam.classify", "scam"),
        ("smoke", "smoke"),
    ],
)
def test_the_feature_is_the_part_of_the_operation_before_the_dot(
    operation: str, feature: str
) -> None:
    assert feature_of(operation) == feature


def test_usage_missing_from_the_response_logs_unknowns_not_zeros(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        log_usage(
            None,
            operation="scam.classify",
            tier=ModelTier.CLASSIFICATION,
            model="m",
            latency_ms=5,
            attempts=1,
        )

    (fields,) = records(caplog, "gemini_call ")
    assert fields["tokens_in"] is None and fields["tokens_out"] is None
    assert fields["latency_ms"] == 5


def test_an_answer_with_no_thinking_still_has_tokens_out(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        log_usage(
            usage(10, 7),
            operation="scam.classify",
            tier=ModelTier.CLASSIFICATION,
            model="m",
            latency_ms=5,
            attempts=1,
        )

    (fields,) = records(caplog, "gemini_call ")
    assert (fields["tokens_in"], fields["tokens_out"]) == (10, 7)


async def test_existing_structured_calls_now_carry_the_feature_and_the_new_token_names(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _ = make_client([text_response('{"is_scam": true}', usage(12, 7))])

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        await client.generate_structured(
            operation="contract.detect",
            tier=ModelTier.CLASSIFICATION,
            contents="text",
            response_model=Verdict,
        )

    (fields,) = records(caplog, "gemini_call ")
    assert fields["feature"] == "contract"
    # The names earlier runbooks and queries read are still there.
    assert (fields["prompt_tokens"], fields["output_tokens"]) == (12, 7)
    assert (fields["tokens_in"], fields["tokens_out"]) == (12, 7)


async def test_a_structured_call_that_fails_is_logged_with_its_error_and_attempts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _ = make_client([unavailable()] * 3)

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        with pytest.raises(GeminiUnavailableError):
            await client.generate_structured(
                operation="scam.classify",
                tier=ModelTier.CLASSIFICATION,
                contents="text",
                response_model=Verdict,
            )

    (fields,) = records(caplog, "gemini_call_failed")
    assert fields["feature"] == "scam"
    assert fields["error"] == "GeminiUnavailableError"
    assert fields["outcome"] == "failed"
    assert fields["attempts"] == 3
    assert isinstance(fields["latency_ms"], int)
    assert records(caplog, "gemini_call ") == []


async def test_a_failure_line_never_carries_the_error_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _ = make_client([unavailable()] * 3)

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        with pytest.raises(GeminiUnavailableError):
            await client.chat(
                operation="coach.reply", tier=ModelTier.REASONING, message="my salary is 4200"
            )

    line = next(r.getMessage() for r in caplog.records if "gemini_call_failed" in r.getMessage())
    assert "my salary" not in line and "fake failure" not in line
