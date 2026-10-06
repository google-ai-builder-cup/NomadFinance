from __future__ import annotations

import logging
from typing import Any

import pytest
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from app.config import get_settings
from app.integrations.gemini import (
    ChatReply,
    ChatTurn,
    GeminiClient,
    GeminiRateLimitError,
    GeminiRequestError,
    GeminiResponseError,
    GeminiUnavailableError,
    ModelTier,
    truncate_history,
)
from app.integrations.gemini.chat import build_contents, estimate_tokens, with_summary
from tests.unit.integrations.gemini_fakes import (
    api_error,
    make_client,
    text_response,
    unavailable,
    usage,
)

pytestmark = pytest.mark.anyio


def turns(*pairs: tuple[str, str]) -> list[ChatTurn]:
    return [ChatTurn(role=role, text=text) for role, text in pairs]  # type: ignore[arg-type]


# --- truncate_history ------------------------------------------------------------------


def test_short_history_is_kept_whole() -> None:
    history = turns(("user", "hi"), ("model", "hello"), ("user", "I earn 4200"))

    window = truncate_history(history, max_turns=10, max_tokens=1000)

    assert window.kept == history
    assert window.dropped == []


def test_empty_history_gives_an_empty_window() -> None:
    window = truncate_history([], max_turns=10, max_tokens=1000)

    assert window.kept == [] and window.dropped == []


def test_the_turn_limit_keeps_the_newest_turns_and_returns_the_rest_in_order() -> None:
    history = turns(
        ("user", "u1"), ("model", "m1"), ("user", "u2"), ("model", "m2"), ("user", "u3")
    )

    window = truncate_history(history, max_turns=3, max_tokens=1000)

    assert [t.text for t in window.kept] == ["u2", "m2", "u3"]
    assert [t.text for t in window.dropped] == ["u1", "m1"]


def test_the_token_limit_drops_older_turns_first() -> None:
    old = "x" * 300  # about 100 tokens
    history = turns(("user", old), ("model", old), ("user", "short"), ("model", "short"))

    window = truncate_history(history, max_turns=10, max_tokens=50)

    assert [t.text for t in window.kept] == ["short", "short"]
    assert [t.role for t in window.kept] == ["user", "model"]
    assert window.dropped == history[:2]


def test_the_window_starts_on_a_user_turn() -> None:
    history = turns(("user", "u1"), ("model", "m1"), ("user", "u2"), ("model", "m2"))

    # Three turns fit, which would start the window on a model turn: Gemini refuses that.
    window = truncate_history(history, max_turns=3, max_tokens=1000)

    assert [t.text for t in window.kept] == ["u2", "m2"]
    assert [t.text for t in window.dropped] == ["u1", "m1"]
    assert window.kept[0].role == "user"


def test_the_newest_turn_is_taken_even_when_it_alone_is_over_the_token_limit() -> None:
    history = turns(("user", "short"), ("model", "y" * 3000), ("user", "z" * 3000))

    window = truncate_history(history, max_turns=10, max_tokens=10)

    assert [t.text[:1] for t in window.kept] == ["z"]
    assert window.dropped == history[:2]


def test_estimate_tokens_rounds_up_and_runs_high_for_indic_scripts() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("ab") == 1
    assert estimate_tokens("abcd") == 2


# --- build_contents, with_summary ------------------------------------------------------


def test_build_contents_keeps_roles_and_puts_the_new_message_last() -> None:
    contents = build_contents(turns(("user", "hi"), ("model", "hello")), "new question")

    assert [c.role for c in contents] == ["user", "model", "user"]  # type: ignore[union-attr]
    assert contents[-1].parts[0].text == "new question"  # type: ignore[union-attr, index]


def test_with_summary() -> None:
    assert with_summary("rules", None) == "rules"
    assert with_summary("rules", "") == "rules"
    assert with_summary(None, "<summary/>") == "<summary/>"
    assert with_summary("rules", "<summary/>") == "rules\n\n<summary/>"


# --- GeminiClient.chat -----------------------------------------------------------------


async def chat(client: GeminiClient, **kwargs: Any) -> ChatReply:
    return await client.chat(
        operation="coach.reply",
        tier=ModelTier.REASONING,
        message="How much should I save?",
        **kwargs,
    )


async def test_chat_returns_the_text_and_sends_history_then_the_message() -> None:
    client, fake = make_client([text_response("Start with a month of rent.", usage(40, 9))])
    history = turns(("user", "I earn 4200 AUD"), ("model", "Thanks, and your costs?"))

    reply = await chat(client, history=history, system_instruction="You are a coach.")

    assert reply.text == "Start with a month of rent."
    call = fake.calls[0]
    assert call["model"] == get_settings().gemini_model_reasoning
    assert [c.role for c in call["contents"]] == ["user", "model", "user"]
    assert call["contents"][-1].parts[0].text == "How much should I save?"
    assert call["config"].system_instruction == "You are a coach."
    # A conversation is free text: no response schema is attached.
    assert call["config"].response_schema is None


async def test_chat_sends_only_the_window_and_returns_what_was_left_out() -> None:
    client, fake = make_client([text_response("ok")])
    history = turns(*[("user" if i % 2 == 0 else "model", f"turn {i}") for i in range(8)])

    reply = await chat(client, history=history, max_history_turns=4)

    sent = [c.parts[0].text for c in fake.calls[0]["contents"]]
    assert sent == ["turn 4", "turn 5", "turn 6", "turn 7", "How much should I save?"]
    assert [t.text for t in reply.dropped_turns] == [f"turn {i}" for i in range(4)]


async def test_chat_history_limits_come_from_the_settings_when_not_given() -> None:
    client, fake = make_client([text_response("ok")], gemini_chat_history_turns=2)
    history = turns(("user", "a"), ("model", "b"), ("user", "c"), ("model", "d"), ("user", "e"))

    await chat(client, history=history)

    # Two turns fit, but the older of them is a model turn: only the last user turn and the
    # new message are sent.
    assert len(fake.calls[0]["contents"]) == 2


async def test_chat_adds_the_summary_after_the_system_instruction() -> None:
    client, fake = make_client([text_response("ok")])

    await chat(client, system_instruction="rules", summary="<summary>earlier</summary>")

    assert fake.calls[0]["config"].system_instruction == "rules\n\n<summary>earlier</summary>"


async def test_chat_passes_safety_settings_and_thinking_budget() -> None:
    client, fake = make_client([text_response("ok")])
    safety = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        )
    ]

    await chat(client, safety_settings=safety, thinking_budget=0, temperature=0.4)

    config = fake.calls[0]["config"]
    assert config.safety_settings == safety
    assert config.thinking_config.thinking_budget == 0
    assert config.temperature == 0.4


async def test_chat_leaves_safety_and_thinking_to_the_defaults_when_not_asked() -> None:
    client, fake = make_client([text_response("ok")])

    await chat(client)

    assert fake.calls[0]["config"].safety_settings is None
    assert fake.calls[0]["config"].thinking_config is None


async def test_chat_retries_a_transient_failure() -> None:
    client, fake = make_client([unavailable(), text_response("second try")])

    reply = await chat(client)

    assert reply.text == "second try"
    assert len(fake.calls) == 2


async def test_chat_gives_up_after_the_configured_attempts() -> None:
    client, fake = make_client([unavailable()] * 3)

    with pytest.raises(GeminiUnavailableError):
        await chat(client)

    assert len(fake.calls) == 3


async def test_chat_does_not_retry_a_rejected_request() -> None:
    client, fake = make_client([api_error(genai_errors.ClientError, 400, "INVALID_ARGUMENT")])

    with pytest.raises(GeminiRequestError):
        await chat(client)

    assert len(fake.calls) == 1


async def test_chat_reports_a_daily_quota_so_the_caller_can_say_try_tomorrow() -> None:
    error = genai_errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "quota",
                "details": [{"violations": [{"quotaId": "GenerateRequestsPerDay-FreeTier"}]}],
            }
        },
    )
    client, _ = make_client([error] * 3)

    with pytest.raises(GeminiRateLimitError) as caught:
        await chat(client)

    assert caught.value.daily is True


async def test_chat_with_no_text_is_a_response_error_not_an_empty_reply() -> None:
    client, _ = make_client([text_response("")])

    with pytest.raises(GeminiResponseError, match="no content"):
        await chat(client)


# --- structured calls take the same options --------------------------------------------


class Slot(BaseModel):
    value: str


async def test_generate_structured_passes_safety_settings_and_thinking_budget() -> None:
    client, fake = make_client([text_response('{"value": "AUD"}', usage(5, 3))])
    safety = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        )
    ]

    result = await client.generate_structured(
        operation="scam.classify",
        tier=ModelTier.CLASSIFICATION,
        contents="msg",
        response_model=Slot,
        safety_settings=safety,
        thinking_budget=128,
    )

    assert result == Slot(value="AUD")
    config = fake.calls[0]["config"]
    assert config.safety_settings == safety
    assert config.thinking_config.thinking_budget == 128
    assert config.response_schema is Slot


async def test_chat_logs_feature_model_tokens_and_latency(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, _ = make_client([text_response("ok", usage(120, 30, 200))])

    with caplog.at_level(logging.INFO, logger="app.integrations.gemini"):
        await chat(client)

    fields = next(r for r in caplog.records if r.getMessage().startswith("gemini_call ")).__dict__[
        "gemini_usage"
    ]
    assert fields["feature"] == "coach"
    assert fields["operation"] == "coach.reply"
    assert fields["model"] == get_settings().gemini_model_reasoning
    assert fields["tokens_in"] == 120
    # Billed output is the answer plus the thinking.
    assert fields["tokens_out"] == 230
    assert fields["thinking_tokens"] == 200
    assert isinstance(fields["latency_ms"], int)
