from __future__ import annotations

import copy
import hashlib
import re
from collections.abc import Sequence
from typing import Any

import pytest
from firebase_admin import firestore  # type: ignore[import-untyped]
from google.cloud.firestore_v1.vector import Vector

from src.config import SCAM_PATTERNS_DIR
from src.embedding import EMBEDDING_DIMENSION, EMBEDDING_MODEL, normalise
from src.loaders import scam_patterns
from src.loaders.scam_patterns import content_hash, load_pattern_docs, main
from src.loaders.scam_patterns_check import (
    Outcome,
    cosine_neighbours,
    evaluate,
    golden_scams,
    load_redactor,
    pick_held_out,
    report,
    type_of,
)
from src.validators.scam_golden import GoldenRow
from src.validators.scam_patterns import PatternRow, load_all


class HashEmbedder:
    """Words hashed into 768 buckets: similar wording gives a close vector, with no network."""

    model = EMBEDDING_MODEL
    dimension = EMBEDDING_DIMENSION

    def __init__(self) -> None:
        self.calls: list[int] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(len(texts))
        out = []
        for text in texts:
            vec = [0.0] * self.dimension
            for word in re.findall(r"\w+", text.lower()):
                vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimension] += 1.0
            out.append(normalise(vec))
        return out


class _Snapshot:
    def __init__(self, doc_id: str, data: dict[str, Any]) -> None:
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


class _Ref:
    def __init__(self, client: _FakeClient, path: str) -> None:
        self._client = client
        self.path = path

    def document(self, doc_id: str) -> _Ref:
        return _Ref(self._client, f"{self.path}/{doc_id}")

    def stream(self) -> list[_Snapshot]:
        prefix = f"{self.path}/"
        return [
            _Snapshot(path.removeprefix(prefix), data)
            for path, data in self._client.store.items()
            if path.startswith(prefix)
        ]


class _Batch:
    def __init__(self, client: _FakeClient) -> None:
        self._client = client
        self._ops: list[tuple[str, str, dict[str, Any] | None, bool]] = []

    def set(self, ref: _Ref, data: dict[str, Any], merge: bool = False) -> None:
        self._ops.append(("set", ref.path, data, merge))

    def delete(self, ref: _Ref) -> None:
        self._ops.append(("delete", ref.path, None, False))

    def commit(self) -> None:
        assert len(self._ops) <= 500, "a Firestore batch holds at most 500 writes"
        self._client.commits += 1
        for action, path, data, merge in self._ops:
            if action == "delete":
                self._client.store.pop(path, None)
            elif merge and path in self._client.store:
                stored = self._client.store[path]
                for key, value in (data or {}).items():
                    if value is firestore.DELETE_FIELD:
                        stored.pop(key, None)
                    else:
                        stored[key] = value
            else:
                self._client.store[path] = copy.copy(data or {})


class _FakeClient:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.commits = 0

    def collection(self, name: str) -> _Ref:
        return _Ref(self, name)

    def batch(self) -> _Batch:
        return _Batch(self)


@pytest.fixture(scope="module")
def rows() -> list[PatternRow]:
    loaded, problems = load_all(SCAM_PATTERNS_DIR)
    assert problems == []
    return loaded


def _load(client: _FakeClient, rows: list[PatternRow], embedder: HashEmbedder | None = None) -> Any:
    return load_pattern_docs(client, rows, embedder or HashEmbedder(), collection="scam_patterns")  # type: ignore[arg-type]


# ---------------------------------------------------------------- loader


def test_first_load_writes_every_template_with_a_768_vector(rows: list[PatternRow]) -> None:
    client = _FakeClient()
    embedder = HashEmbedder()

    result = _load(client, rows, embedder)

    assert (result.new, result.changed, result.unchanged, result.removed) == (480, 0, 0, 0)
    assert len(client.store) == 480
    doc = client.store["scam_patterns/fake_job_offer-en-001"]
    assert (
        isinstance(doc["embedding"], Vector)
        and len(doc["embedding"].to_map_value()["value"]) == 768
    )
    assert doc["embedding_model"] == "gemini-embedding-001" and doc["dimension"] == 768
    assert doc["source"] == "curated" and doc["schema_version"] == 1
    assert doc["scam_type"] == "fake_job_offer" and doc["language"] == "en"
    assert doc["created_at"] == firestore.SERVER_TIMESTAMP
    assert doc["corridor_id"] == "SG-PH" and len(doc["content_hash"]) == 64
    assert "scam_patterns/fake_job_offer-ne-001" in client.store
    assert "corridor_id" not in client.store["scam_patterns/fake_job_offer-ne-001"]


def test_a_second_run_embeds_and_writes_nothing(rows: list[PatternRow]) -> None:
    client = _FakeClient()
    _load(client, rows)
    commits = client.commits
    embedder = HashEmbedder()
    snapshot = copy.deepcopy(client.store)

    result = _load(client, rows, embedder)

    assert (result.new, result.changed, result.unchanged, result.removed) == (0, 0, 480, 0)
    assert embedder.calls == [] and client.commits == commits
    assert client.store.keys() == snapshot.keys()


def test_a_changed_text_is_re_embedded_alone_and_keeps_created_at(rows: list[PatternRow]) -> None:
    client = _FakeClient()
    _load(client, rows)
    client.store["scam_patterns/lottery-en-001"]["created_at"] = "2026-10-08"
    edited = [
        r.model_copy(update={"text": r.text + " Reply now."}) if r.id == "lottery-en-001" else r
        for r in rows
    ]
    embedder = HashEmbedder()

    result = _load(client, edited, embedder)

    assert (result.new, result.changed, result.unchanged) == (0, 1, 479)
    assert embedder.calls == [1]
    doc = client.store["scam_patterns/lottery-en-001"]
    assert doc["text"].endswith("Reply now.") and doc["created_at"] == "2026-10-08"


def test_a_removed_template_is_deleted(rows: list[PatternRow]) -> None:
    client = _FakeClient()
    _load(client, rows)

    result = _load(client, [r for r in rows if r.id != "lottery-bn-010"])

    assert result.removed == 1
    assert "scam_patterns/lottery-bn-010" not in client.store and len(client.store) == 479


def test_a_new_template_is_added(rows: list[PatternRow]) -> None:
    client = _FakeClient()
    _load(client, rows[:-1])

    result = _load(client, rows)

    assert (result.new, result.unchanged) == (1, 479)


def test_a_dropped_corridor_is_removed_from_the_stored_document(rows: list[PatternRow]) -> None:
    client = _FakeClient()
    _load(client, rows)
    edited = [
        r.model_copy(update={"corridor_id": None}) if r.id == "lottery-en-001" else r for r in rows
    ]

    _load(client, edited)

    assert "corridor_id" not in client.store["scam_patterns/lottery-en-001"]


def test_a_new_model_re_embeds_everything(rows: list[PatternRow]) -> None:
    client = _FakeClient()
    _load(client, rows)
    other = HashEmbedder()
    other.model = "another-model"

    result = _load(client, rows, other)

    assert result.changed == 480


def test_the_curator_is_not_part_of_the_hash(rows: list[PatternRow]) -> None:
    row = rows[0]
    other = row.model_copy(update={"curator": "AB", "reviewed_by": "PP"})
    assert content_hash(row, "m", 768) == content_hash(other, "m", 768)
    changed = row.model_copy(update={"text": row.text + "!"})
    assert content_hash(row, "m", 768) != content_hash(changed, "m", 768)


def test_a_failed_embedding_writes_nothing(rows: list[PatternRow]) -> None:
    class Broken(HashEmbedder):
        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            raise RuntimeError("quota")

    client = _FakeClient()

    with pytest.raises(RuntimeError, match="quota"):
        _load(client, rows, Broken())

    assert client.store == {} and client.commits == 0


def test_writes_are_split_into_batches_of_at_most_500(rows: list[PatternRow]) -> None:
    client = _FakeClient()
    _load(client, rows)
    assert client.commits == 2  # 480 writes in chunks of 400


def test_dry_run_touches_neither_gemini_nor_firestore(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(*_: Any, **__: Any) -> None:
        raise AssertionError("must not be called in a dry run")

    monkeypatch.setattr(scam_patterns, "get_firestore_client", boom)
    monkeypatch.setattr(scam_patterns, "GeminiEmbedder", boom)

    with caplog.at_level("INFO"):
        assert main(["--dry-run"]) == 0

    assert "Validated 480 templates" in caplog.text and "[dry-run]" in caplog.text


def test_an_invalid_library_stops_the_run_before_anything_is_written(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "lottery.jsonl").write_text("not json\n", encoding="utf-8")

    def boom(*_: Any, **__: Any) -> None:
        raise AssertionError("must not be called")

    monkeypatch.setattr(scam_patterns, "get_firestore_client", boom)
    monkeypatch.setattr(scam_patterns, "GeminiEmbedder", boom)

    assert main(["--input-dir", str(tmp_path)]) == 1
    assert "Nothing was written" in caplog.text


# ---------------------------------------------------------------- nearest-neighbour check


def test_type_of_reads_the_id() -> None:
    assert type_of("illegal_recruitment_fee-en-004") == "illegal_recruitment_fee"
    assert type_of("lottery-bn-010") == "lottery"


def test_held_out_pick_is_fixed_and_covers_every_type_and_language() -> None:
    scams = golden_scams()
    first = pick_held_out(scams)
    assert [r.id for r in first] == [r.id for r in pick_held_out(scams)]
    assert len(first) == 10 and len({r.id for r in first}) == 10
    assert {r.scam_type for r in first} == {r.scam_type for r in scams}
    assert {r.language for r in first} == {"en", "hi", "tl", "id", "ne", "bn"}


def test_all_golden_scams_are_loaded() -> None:
    scams = golden_scams()
    assert len(scams) >= 80 and all(r.is_scam for r in scams)


def test_cosine_neighbours_ranks_the_closest_first() -> None:
    embedder = HashEmbedder()
    texts = [
        "send passport and bank details now",
        "pay the visa fee today",
        "you won a lottery prize",
    ]
    library = list(zip(["a-en-001", "b-en-001", "c-en-001"], embedder.embed(texts), strict=True))
    query = embedder.embed(["pay your visa fee"])[0]

    top = cosine_neighbours(query, library, 2)

    assert [pid for pid, _ in top] == ["b-en-001", "a-en-001"] or top[0][0] == "b-en-001"
    assert top[0][1] >= top[1][1] and len(top) == 2


def _golden(row_id: str, scam_type: str, text: str) -> GoldenRow:
    return GoldenRow.model_validate(
        {
            "id": row_id,
            "language": "en",
            "script": "latin",
            "text": text,
            "is_scam": True,
            "scam_type": scam_type,
            "tactics": ["urgency"],
            "risk_level": "high",
            "rationale": "A message that asks for money now, for the test.",
            "resembles": None,
            "corridor_id": None,
            "channel": "sms",
            "provenance": "synthetic",
            "curator": "DD",
            "reviewed_by": None,
        }
    )


def test_a_hit_needs_a_same_type_pattern_in_the_top_three() -> None:
    row = _golden("gold-en-001", "lottery", "You won the lottery prize draw today")
    assert Outcome(row, [("fake_job_offer-en-001", 0.9), ("lottery-hi-002", 0.8)]).hit
    assert not Outcome(row, [("fake_job_offer-en-001", 0.9), ("loan_app_trap-en-002", 0.8)]).hit


def test_evaluate_and_report_pass_when_every_held_out_scam_hits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    embedder = HashEmbedder()
    library_rows = [
        ("lottery-en-001", "You have won the lottery prize draw, pay the fee"),
        ("fake_job_offer-en-001", "Hiring cleaners, send your passport copy for the job"),
    ]
    library = list(
        zip(
            [pid for pid, _ in library_rows],
            embedder.embed([t for _, t in library_rows]),
            strict=True,
        )
    )
    scams = [
        _golden("gold-en-001", "lottery", "You won the lottery prize draw, pay the fee now"),
        _golden(
            "gold-en-002", "fake_job_offer", "Cleaners hiring, send your passport copy for this job"
        ),
    ]

    outcomes = evaluate(scams, embedder, lambda v: cosine_neighbours(v, library), lambda t: t)

    assert all(o.hit for o in outcomes)
    assert report(outcomes, scams) is True
    assert "Held-out gate: 2 of 2 hit" in capsys.readouterr().out


def test_report_fails_and_lists_a_missed_held_out_scam(capsys: pytest.CaptureFixture[str]) -> None:
    scam = _golden("gold-en-001", "lottery", "You won the lottery prize draw today")
    outcomes = [Outcome(scam, [("loan_app_trap-en-001", 0.5)])]

    assert report(outcomes, [scam]) is False
    out = capsys.readouterr().out
    assert "MISS gold-en-001" in out and "0 of 1 hit" in out


def test_the_backend_redactor_masks_what_the_analyzer_masks() -> None:
    redact = load_redactor()
    masked = redact(
        "Mail hr@brightpath-hire.example or call +65 0000 0031 or open https://x.example/a"
    )
    assert "[EMAIL]" in masked and "[URL]" in masked and "brightpath" not in masked


def test_retry_delay_reads_the_wait_the_api_asks_for() -> None:
    from src.embedding import retry_delay

    quota = {
        "error": {
            "code": 429,
            "details": [
                {"@type": "type.googleapis.com/google.rpc.Help"},
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "22s"},
            ],
        }
    }
    assert retry_delay(quota) == 22.0
    assert retry_delay({"error": {"code": 503}}) is None
    assert retry_delay(None) is None
    assert (
        retry_delay({"error": {"details": [{"@type": "x.RetryInfo", "retryDelay": "soon"}]}})
        is None
    )
