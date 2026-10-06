from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import get_settings
from app.integrations.gemini import GeminiClient

HANG = "hang"


class FakeStream:
    """Stands in for the SDK's async chunk iterator; plays back one item per `__anext__`.

    An item is a response, an exception to raise, or `HANG` (wait until cancelled).
    """

    def __init__(self, items: list[Any]) -> None:
        self.items = list(items)
        self.closed = False

    def __aiter__(self) -> FakeStream:
        return self

    async def __anext__(self) -> types.GenerateContentResponse:
        if not self.items:
            raise StopAsyncIteration
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        if item == HANG:
            await asyncio.sleep(30)
        return cast(types.GenerateContentResponse, item)

    async def aclose(self) -> None:
        self.closed = True


class FakeModels:
    """Stands in for `genai.Client().aio.models`; plays back one outcome per call.

    An outcome is a response (for `generate_content`), a list of stream items (for
    `generate_content_stream`), an exception to raise, or `HANG`.
    """

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []
        self.streams: list[FakeStream] = []

    async def generate_content(self, **kwargs: Any) -> types.GenerateContentResponse:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome == HANG:
            await asyncio.sleep(30)
        return cast(types.GenerateContentResponse, outcome)

    async def generate_content_stream(self, **kwargs: Any) -> FakeStream:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        stream = FakeStream(outcome)
        self.streams.append(stream)
        return stream


def make_client(outcomes: list[Any], **settings_overrides: Any) -> tuple[GeminiClient, FakeModels]:
    fake = FakeModels(outcomes)
    sdk = cast(genai.Client, SimpleNamespace(aio=SimpleNamespace(models=fake)))
    settings = get_settings().model_copy(update=settings_overrides)
    return GeminiClient(settings, sdk_client=sdk, max_backoff_seconds=0), fake


def usage(prompt: int, answer: int, thinking: int | None = None) -> Any:
    return types.GenerateContentResponseUsageMetadata(
        prompt_token_count=prompt,
        candidates_token_count=answer,
        thoughts_token_count=thinking,
        total_token_count=prompt + answer + (thinking or 0),
    )


def text_response(text: str, usage_metadata: Any = None) -> types.GenerateContentResponse:
    """One response (or one chunk of a streamed one) holding `text`; empty text makes a chunk
    that carries only usage, as the last chunk of a stream does."""
    parts = [types.Part(text=text)] if text else []
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts),
                finish_reason=types.FinishReason.STOP,
            )
        ],
        usage_metadata=usage_metadata,
    )


def api_error(cls: type[genai_errors.APIError], code: int, status: str) -> genai_errors.APIError:
    return cls(code, {"error": {"code": code, "message": "fake failure", "status": status}})


def unavailable() -> genai_errors.APIError:
    return api_error(genai_errors.ServerError, 503, "UNAVAILABLE")
