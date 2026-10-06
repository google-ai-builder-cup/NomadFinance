from __future__ import annotations

import logging

from google.genai import types
from tenacity import RetryCallState

from app.integrations.gemini.model_tiers import ModelTier

logger = logging.getLogger(__name__)


def feature_of(operation: str) -> str:
    """The product area an operation belongs to: `contract.extract` is `contract`, so cost can
    be summed per feature without every call site naming one."""
    return operation.split(".", 1)[0]


def log_usage(
    usage: types.GenerateContentResponseUsageMetadata | None,
    *,
    operation: str,
    tier: ModelTier,
    model: str,
    latency_ms: int,
    attempts: int,
    time_to_first_token_ms: int | None = None,
) -> None:
    """One `gemini_call` line for a finished call, with the fields cost is summed from.

    `tokens_in` is the prompt. `tokens_out` is what Google bills as output: the answer and the
    thinking, which the reasoning tier spends heavily. `output_tokens` and `thinking_tokens` are
    the same two parts separately, kept because earlier runbooks and queries read them.
    """
    prompt = usage.prompt_token_count if usage else None
    answer = usage.candidates_token_count if usage else None
    thinking = usage.thoughts_token_count if usage else None
    fields: dict[str, object] = {
        "operation": operation,
        "feature": feature_of(operation),
        "tier": tier.value,
        "model": model,
        "tokens_in": prompt,
        "tokens_out": None if usage is None else (answer or 0) + (thinking or 0),
        "prompt_tokens": prompt,
        "output_tokens": answer,
        "thinking_tokens": thinking,
        "total_tokens": usage.total_token_count if usage else None,
        "latency_ms": latency_ms,
        "attempts": attempts,
    }
    if time_to_first_token_ms is not None:
        fields["time_to_first_token_ms"] = time_to_first_token_ms
    # Readable in plain-text logs now; `extra` carries the same fields for JSON logging.
    logger.info(
        "gemini_call %s",
        " ".join(f"{key}={value}" for key, value in fields.items()),
        extra={"gemini_usage": fields},
    )


def log_failure(
    error: BaseException | None,
    *,
    operation: str,
    tier: ModelTier,
    model: str,
    latency_ms: int,
    attempts: int,
    outcome: str = "failed",
) -> None:
    """One `gemini_call_failed` line for a call that ended without an answer (D-86).

    `outcome` is `failed`, `cancelled` (the worker went away) or `closed` (the caller stopped
    reading a stream early; no error). Only the error's class is logged: its text can carry a
    quota id or model message, and the retry lines already have the detail.
    """
    fields: dict[str, object] = {
        "operation": operation,
        "feature": feature_of(operation),
        "tier": tier.value,
        "model": model,
        "outcome": outcome,
        "error": type(error).__name__ if error is not None else None,
        "latency_ms": latency_ms,
        "attempts": attempts,
    }
    logger.warning(
        "gemini_call_failed %s",
        " ".join(f"{key}={value}" for key, value in fields.items()),
        extra={"gemini_usage": fields},
    )


def log_retry(retry_state: RetryCallState) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "gemini_retry attempt=%d error=%s: %s",
        retry_state.attempt_number,
        type(exc).__name__,
        exc,
    )
