from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src import embedding
from src.embedding import (
    CachedEmbedder,
    EmbeddingQuotaError,
    GeminiEmbedder,
    daily_quota_id,
    normalise,
)

DAILY = {
    "error": {
        "code": 429,
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [
                    {"quotaId": "EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier"}
                ],
            },
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "30s"},
        ],
    }
}
PER_MINUTE = {
    "error": {
        "code": 429,
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [
                    {"quotaId": "EmbedContentRequestsPerMinutePerUserPerProjectPerModel-FreeTier"}
                ],
            },
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "22s"},
        ],
    }
}


def test_a_per_day_quota_is_told_from_a_per_minute_one() -> None:
    assert "PerDay" in str(daily_quota_id(DAILY))
    assert daily_quota_id(PER_MINUTE) is None
    assert daily_quota_id(None) is None
    assert daily_quota_id({"error": {"details": ["x", {"violations": ["y"]}]}}) is None


# ---------------------------------------------------------------- the real embedder's retries


def _embedder(*outcomes: Any, monkeypatch: pytest.MonkeyPatch) -> tuple[GeminiEmbedder, list[Any]]:
    """A real `GeminiEmbedder` whose SDK call plays `outcomes` (an error to raise, or a count)."""
    from google.genai import errors

    embedder = GeminiEmbedder(api_key="not-a-real-key")
    log: list[Any] = []
    queue = list(outcomes)

    class Models:
        def embed_content(self, model: str, contents: list[str], config: Any) -> Any:
            log.append(("call", len(contents)))
            outcome = queue.pop(0)
            if isinstance(outcome, dict):
                raise errors.APIError(outcome["error"]["code"], outcome)
            vector = [3.0] + [0.0] * 767
            return SimpleNamespace(embeddings=[SimpleNamespace(values=vector) for _ in contents])

    embedder._client = SimpleNamespace(models=Models())  # type: ignore[assignment]
    monkeypatch.setattr(embedding.time, "sleep", lambda seconds: log.append(("sleep", seconds)))
    return embedder, log


def test_a_daily_quota_stops_at_once_with_a_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    embedder, log = _embedder(DAILY, DAILY, monkeypatch=monkeypatch)

    with pytest.raises(EmbeddingQuotaError, match="PerDay") as caught:
        embedder.embed(["a", "b"])

    assert log == [("call", 2)]  # no sleeping, no second try
    assert "kept" in str(caught.value) and "billing" in str(caught.value)


def test_a_wait_longer_than_a_run_can_use_also_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    long_wait = {
        "error": {
            "code": 429,
            "details": [{"@type": "x.RetryInfo", "retryDelay": "600s"}],
        }
    }
    embedder, log = _embedder(long_wait, monkeypatch=monkeypatch)

    with pytest.raises(EmbeddingQuotaError, match="600"):
        embedder.embed(["a"])

    assert log == [("call", 1)]


def test_a_per_minute_limit_is_waited_out_as_asked_and_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedder, log = _embedder(PER_MINUTE, 1, monkeypatch=monkeypatch)

    vectors = embedder.embed(["a"])

    assert log == [("call", 1), ("sleep", 24.0), ("call", 1)]  # the 22 s asked for, plus 2
    assert len(vectors) == 1 and len(vectors[0]) == 768
    assert vectors[0][0] == pytest.approx(1.0)  # rescaled to unit length


# ---------------------------------------------------------------- the cache


class CountingEmbedder:
    model = "m1"
    dimension = 3

    def __init__(self, fail_on_call: int | None = None) -> None:
        self.calls: list[list[str]] = []
        self._fail_on_call = fail_on_call

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._fail_on_call == len(self.calls):
            raise EmbeddingQuotaError("daily quota")
        return [normalise([float(len(t)), 1.0, 2.0]) for t in texts]


def test_a_text_is_embedded_once_and_remembered_between_runs(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    first = CountingEmbedder()
    one = CachedEmbedder(first, path).embed(["alpha", "beta"])

    second = CountingEmbedder()
    two = CachedEmbedder(second, path).embed(["beta", "alpha", "gamma"])

    assert first.calls == [["alpha", "beta"]]
    assert second.calls == [["gamma"]]  # only what is new
    assert two[0] == one[1] and two[1] == one[0]  # in the order asked
    assert not list(tmp_path.glob("*.tmp"))


def test_a_run_that_dies_half_way_keeps_what_it_finished(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    texts = [f"text {i}" for i in range(120)]  # three batches of 50, 50 and 20
    dying = CountingEmbedder(fail_on_call=2)

    with pytest.raises(EmbeddingQuotaError):
        CachedEmbedder(dying, path).embed(texts)

    assert len(json.loads(path.read_text(encoding="utf-8"))) == 50
    resumed = CountingEmbedder()
    result = CachedEmbedder(resumed, path).embed(texts)
    assert [len(call) for call in resumed.calls] == [50, 20]  # the first 50 were not redone
    assert len(result) == 120


def test_a_different_model_never_reads_another_models_vectors(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    CachedEmbedder(CountingEmbedder(), path).embed(["alpha"])
    other = CountingEmbedder()
    other.model = "m2"

    CachedEmbedder(other, path).embed(["alpha"])

    assert other.calls == [["alpha"]]


def test_a_repeated_text_in_one_call_is_embedded_once(tmp_path: Path) -> None:
    inner = CountingEmbedder()

    out = CachedEmbedder(inner, tmp_path / "cache.json").embed(["a", "b", "a"])

    assert inner.calls == [["a", "b"]] and out[0] == out[2]


@pytest.mark.parametrize("content", ["not json {", "[1, 2, 3]", ""])
def test_a_damaged_cache_is_ignored_not_fatal(tmp_path: Path, content: str) -> None:
    path = tmp_path / "cache.json"
    path.write_text(content, encoding="utf-8")
    inner = CountingEmbedder()

    out = CachedEmbedder(inner, path).embed(["a"])

    assert len(out) == 1 and inner.calls == [["a"]]


def test_the_cache_file_holds_only_what_it_was_given(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    CachedEmbedder(CountingEmbedder(), path).embed(["a secret-looking text"])

    stored = path.read_text(encoding="utf-8")

    # Keys are hashes: the text itself is not written, only its vector.
    assert "secret-looking" not in stored


# ---------------------------------------------------------------- the commands


class _OutOfQuota:
    model = "m1"
    dimension = 3

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise EmbeddingQuotaError("Gemini will not embed more for now (PerDay).")


def test_the_calibration_ends_cleanly_with_exit_code_2_when_the_quota_is_gone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from src.loaders import scam_patterns_calibrate

    monkeypatch.setattr(embedding, "CACHE_FILE", tmp_path / "cache.json")
    monkeypatch.setattr(embedding, "GeminiEmbedder", lambda: _OutOfQuota())

    assert scam_patterns_calibrate.main([]) == scam_patterns_calibrate.QUOTA_EXIT_CODE == 2

    assert "PerDay" in caplog.text and "Traceback" not in caplog.text


def test_the_check_ends_cleanly_with_exit_code_2_when_the_quota_is_gone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from src.loaders import scam_patterns_check

    monkeypatch.setattr(embedding, "CACHE_FILE", tmp_path / "cache.json")
    monkeypatch.setattr(embedding, "GeminiEmbedder", lambda: _OutOfQuota())

    assert scam_patterns_check.main([]) == 2
    assert "PerDay" in caplog.text


def test_the_loader_writes_nothing_and_exits_2_when_the_quota_is_gone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from src.loaders import scam_patterns

    class Firestore:
        def collection(self, name: str) -> Firestore:
            return self

        def stream(self) -> list[Any]:
            return []

        def batch(self) -> Any:
            raise AssertionError("nothing may be written")

    monkeypatch.setattr(embedding, "CACHE_FILE", tmp_path / "cache.json")
    monkeypatch.setattr(scam_patterns, "get_firestore_client", lambda: Firestore())
    monkeypatch.setattr(scam_patterns, "GeminiEmbedder", lambda: _OutOfQuota())

    assert scam_patterns.main([]) == 2
    assert "PerDay" in caplog.text
