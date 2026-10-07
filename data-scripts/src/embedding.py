"""Text embeddings for data-scripts: Gemini `gemini-embedding-001`, 768 numbers, normalised.

The same model, size and task type as the backend (backend/app/integrations/gemini/embeddings.py):
a vector made here must be comparable with one the backend makes for an incoming message, or the
nearest-neighbour search compares unlike things. The model returns 3072 numbers by default;
Firestore vectors stop at 2048, so every request asks for 768 and the result is rescaled to unit
length (a shortened embedding is not unit length).

Needs `GEMINI_API_KEY` in the environment. Nothing here reads or writes a key file.
"""

from __future__ import annotations

import logging
import math
import os
import time
from collections.abc import Sequence
from typing import Protocol

log = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768
TASK_TYPE = "SEMANTIC_SIMILARITY"

_BATCH_SIZE = 50
_TIMEOUT_MS = 30_000
_ATTEMPTS = 8
_MAX_WAIT = 90.0  # seconds; a free-tier minute is 60, plus the margin Google asks for
_RETRY_CODES = {429, 500, 502, 503, 504}


class Embedder(Protocol):
    """Anything that turns texts into fixed-size vectors; the loader and the check use this."""

    model: str
    dimension: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One unit-length vector per text, in the same order."""
        ...


def retry_delay(details: object) -> float | None:
    """Seconds the API asks us to wait (`RetryInfo.retryDelay`, like "22s"), if it says."""
    error = details.get("error") if isinstance(details, dict) else None
    for item in (error.get("details") or []) if isinstance(error, dict) else []:
        if isinstance(item, dict) and str(item.get("@type", "")).endswith("RetryInfo"):
            value = str(item.get("retryDelay", ""))
            try:
                return float(value.removesuffix("s"))
            except ValueError:
                return None
    return None


def normalise(vector: Sequence[float]) -> list[float]:
    """Scale to unit length so cosine similarity and dot product agree."""
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        raise ValueError("cannot normalise a zero vector")
    return [v / norm for v in vector]


class GeminiEmbedder:
    """Embeds with the Gemini API in batches, retrying the errors that are worth retrying."""

    model = EMBEDDING_MODEL
    dimension = EMBEDDING_DIMENSION

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Set it in this shell only "
                "(never in a file that is committed) and run again."
            )
        # Imported here so the validators and tests run without the SDK installed.
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            api_key=key, http_options=types.HttpOptions(timeout=_TIMEOUT_MS)
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            vectors.extend(self._embed_batch(list(texts[start : start + _BATCH_SIZE])))
        return vectors

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        from google.genai import errors

        for attempt in range(1, _ATTEMPTS + 1):
            try:
                response = self._client.models.embed_content(
                    model=self.model,
                    contents=batch,
                    config=self._types.EmbedContentConfig(
                        task_type=TASK_TYPE, output_dimensionality=self.dimension
                    ),
                )
            except errors.APIError as exc:
                if exc.code not in _RETRY_CODES or attempt == _ATTEMPTS:
                    raise
                # The free tier counts every text in a batch as a request and allows 100 a minute,
                # so a long run must wait out the quota window, not back off for a few seconds.
                wait = min(_MAX_WAIT, (retry_delay(exc.details) or 2.0**attempt) + 2.0)
                log.warning("Gemini says %s: waiting %.0f s (attempt %d)", exc.code, wait, attempt)
                time.sleep(wait)
                continue
            embeddings = response.embeddings or []
            if len(embeddings) != len(batch):
                raise RuntimeError(f"asked for {len(batch)} embeddings, got {len(embeddings)}")
            vectors = [normalise(e.values or []) for e in embeddings]
            if any(len(v) != self.dimension for v in vectors):
                raise RuntimeError(f"the model did not return {self.dimension} numbers")
            return vectors
        raise AssertionError("unreachable")  # the loop returns or raises
