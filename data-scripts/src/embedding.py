"""Text embeddings for data-scripts: Gemini `gemini-embedding-001`, 768 numbers, normalised.

The same model, size and task type as the backend (backend/app/integrations/gemini/embeddings.py):
a vector made here must be comparable with one the backend makes for an incoming message, or the
nearest-neighbour search compares unlike things. The model returns 3072 numbers by default;
Firestore vectors stop at 2048, so every request asks for 768 and the result is rescaled to unit
length (a shortened embedding is not unit length).

Needs `GEMINI_API_KEY` in the environment. Nothing here reads or writes a key file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
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
# Finished embeddings are kept here between runs. Only synthetic templates and invented test
# messages are ever embedded by these scripts, so a file in the temp folder holds nothing real.
CACHE_FILE = Path(
    os.environ.get("EMBEDDING_CACHE_FILE")
    or Path(tempfile.gettempdir()) / "nomadfinance-embedding-cache.json"
)


class EmbeddingQuotaError(RuntimeError):
    """The quota will not clear within a retry: stop, say why, and keep what is already done."""


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


def daily_quota_id(details: object) -> str | None:
    """The id of an exhausted per-day quota, if the 429 names one (`...PerDay...`)."""
    error = details.get("error") if isinstance(details, dict) else None
    for item in (error.get("details") or []) if isinstance(error, dict) else []:
        if not isinstance(item, dict):
            continue
        for violation in item.get("violations") or []:
            quota_id = str(violation.get("quotaId", "")) if isinstance(violation, dict) else ""
            if "PerDay" in quota_id:
                return quota_id
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
                daily = daily_quota_id(exc.details)
                asked = retry_delay(exc.details)
                if daily or (asked is not None and asked > _MAX_WAIT):
                    # Waiting a minute and trying again cannot clear a day's quota.
                    why = daily or f"asks to wait {asked:.0f} s"
                    raise EmbeddingQuotaError(
                        f"Gemini will not embed more for now ({why})."
                        " The free tier allows 100 texts a minute and a limited number a day. "
                        "Run again later: what was already embedded is kept, so the run resumes. "
                        "A key with billing enabled has no such limit."
                    ) from exc
                # The free tier counts every text in a batch as a request and allows 100 a minute,
                # so a long run must wait out the quota window, not back off for a few seconds.
                wait = min(_MAX_WAIT, (asked or 2.0**attempt) + 2.0)
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


class CachedEmbedder:
    """Remembers finished embeddings on disk, so a run that dies half way resumes where it was.

    The key is the text with the model, the size and the task type, so a different model never
    reads an old vector. Texts are embedded in batches and the file is saved after each one:
    when the quota runs out part way, the vectors already made are not lost.
    """

    def __init__(self, inner: Embedder, path: Path | None = None) -> None:
        self._inner = inner
        self._path = path or CACHE_FILE
        self.model = inner.model
        self.dimension = inner.dimension

    def _key(self, text: str) -> str:
        raw = f"{self.model}|{self.dimension}|{TASK_TYPE}|{text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load(self) -> dict[str, list[float]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}  # no cache yet, or a damaged one: start again rather than fail
        return data if isinstance(data, dict) else {}

    def _save(self, cache: dict[str, list[float]]) -> None:
        temp = self._path.with_suffix(".tmp")
        temp.write_text(json.dumps(cache), encoding="utf-8")
        temp.replace(self._path)  # a crash mid-write cannot leave half a file

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        cache = self._load()
        keys = [self._key(t) for t in texts]
        missing = list(dict.fromkeys(t for t, k in zip(texts, keys, strict=True) if k not in cache))
        log.info(
            "embedding cache: %d of %d texts already done", len(texts) - len(missing), len(texts)
        )
        for start in range(0, len(missing), _BATCH_SIZE):
            batch = missing[start : start + _BATCH_SIZE]
            for text, vector in zip(batch, self._inner.embed(batch), strict=True):
                cache[self._key(text)] = vector
            self._save(cache)
        return [cache[k] for k in keys]
