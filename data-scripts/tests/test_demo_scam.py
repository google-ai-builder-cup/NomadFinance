"""The demo workers' stored scam checks and their loader (NF-HR-003)."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from google.cloud.firestore import Client
from pydantic import ValidationError

from src.config import SEED_SCAM_DIR, SEED_USERS_DIR
from src.loaders.demo_scam import (
    CHECK_TTL,
    check_document,
    check_id,
    load_worker,
    main,
    taxonomy_version_of,
)
from src.validators.demo_scam import ScamSeed, cache_key, load, seed_files
from src.validators.demo_user import load as load_user
from tests.fake_firestore import FakeClient

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
STEMS = ["miguel_jp_care", "priya_sg_domestic", "rajesh_kr_manufacturing"]


def _path(stem: str) -> Path:
    return SEED_SCAM_DIR / f"{stem}.json"


def _raw(stem: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_path(stem).read_text(encoding="utf-8")))


def _seed(stem: str) -> ScamSeed:
    return load(_path(stem))


def _client_with_user(uid: str) -> FakeClient:
    client = FakeClient()
    client.put(f"users/{uid}", {"preferred_language": "hi"})
    return client


# --- the committed files ---------------------------------------------------------------


def test_there_is_one_file_for_each_demo_worker() -> None:
    assert [p.stem for p in seed_files()] == STEMS


@pytest.mark.parametrize("stem", STEMS)
def test_each_worker_has_five_checks_that_mix_scams_and_benign_messages(stem: str) -> None:
    seed = _seed(stem)

    flags = [c.document["verdict"]["is_scam"] for c in seed.checks]
    assert seed.uid == load_user(SEED_USERS_DIR / f"{stem}.json").uid
    assert len(flags) == 5 and 0 < sum(flags) < 5


@pytest.mark.parametrize("stem", STEMS)
def test_the_explanations_are_in_the_workers_language(stem: str) -> None:
    seed = _seed(stem)
    language = load_user(SEED_USERS_DIR / f"{stem}.json").user.preferred_language

    assert {c.document["language"] for c in seed.checks} == {language}


def test_the_demo_covers_three_message_languages_for_each_worker() -> None:
    for stem in STEMS:
        languages = {c.document["message_language"] for c in _seed(stem).checks}
        assert len(languages) >= 3, stem


def test_one_scam_of_each_worker_is_left_unreported_for_the_live_demo() -> None:
    for stem in STEMS:
        scams = [c for c in _seed(stem).checks if c.document["verdict"]["is_scam"]]
        assert all("reported_report_id" not in c.document for c in scams), stem


def test_no_check_holds_a_time_or_the_raw_message_in_its_document() -> None:
    for stem in STEMS:
        for check in _seed(stem).checks:
            assert "created_at" not in check.document
            if check.message != check.document["redacted_text"]:
                # Something was masked (a number, a link): the raw message must not be stored.
                assert check.message not in json.dumps(check.document, ensure_ascii=False)


# --- the checker -------------------------------------------------------------------------


def _broken(edit: Any) -> dict[str, Any]:
    raw = copy.deepcopy(_raw("priya_sg_domestic"))
    edit(raw)
    return raw


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda r: r["checks"].pop(), "5 checks"),
        (lambda r: r["checks"][0]["document"].update(created_at="2026-01-01T00:00:00Z"), "loader"),
        (
            lambda r: r["checks"][0]["document"].update(cache_key="0" * 64),
            "worked out by the loader",
        ),
        (lambda r: r["checks"][0]["document"].update(explainer=None), "explainer"),
        (lambda r: r["checks"][0].update(id="k_1"), "demo_k_"),
        (lambda r: r["checks"][0]["document"].pop("verdict"), "missing"),
    ],
)
def test_the_checker_refuses_what_the_loader_relies_on(edit: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ScamSeed.model_validate(_broken(edit))


def test_five_scams_or_five_benign_messages_are_refused() -> None:
    def all_benign(raw: dict[str, Any]) -> None:
        for check in raw["checks"]:
            check["document"]["verdict"]["is_scam"] = False

    with pytest.raises(ValidationError, match="mix scams"):
        ScamSeed.model_validate(_broken(all_benign))


def test_the_cache_key_is_the_backends_key() -> None:
    # The same text differing in case and spacing is the same message; the language is part of it.
    assert cache_key("Pay  the FEE", "hi") == cache_key("pay the fee", "hi")
    assert cache_key("pay the fee", "hi") != cache_key("pay the fee", "tl")
    assert len(cache_key("x", "hi")) == 64


# --- the documents ---------------------------------------------------------------------


def test_a_check_is_dated_from_the_day_of_the_load_and_expires_in_90_days() -> None:
    check = _seed("priya_sg_domestic").checks[0]

    document = check_document(check, NOW, taxonomy_version=3)

    assert document["created_at"] == datetime(2026, 10, 13, 7, 0, tzinfo=UTC)
    assert document["last_checked_at"] == document["created_at"]
    assert document["expires_at"] == document["created_at"] + CHECK_TTL
    assert document["demo_seed"] is True and document["taxonomy_version"] == 3


def test_a_check_is_never_dated_after_now() -> None:
    check = _seed("priya_sg_domestic").checks[0].model_copy(update={"days_ago": 0, "hour_utc": 23})

    assert check_document(check, NOW, None)["created_at"] == NOW


def test_the_file_keeps_its_taxonomy_version_when_the_taxonomy_is_not_loaded() -> None:
    check = _seed("priya_sg_domestic").checks[0]

    document = check_document(check, NOW, None)

    assert document["taxonomy_version"] == check.document["taxonomy_version"]


def test_the_id_is_the_first_32_characters_of_the_key_the_loader_works_out() -> None:
    check = _seed("priya_sg_domestic").checks[0]
    assert "cache_key" not in check.document

    document = check_document(check, NOW, None)

    assert document["cache_key"] == cache_key(
        check.document["redacted_text"], check.document["language"]
    )
    assert check_id(document) == document["cache_key"][:32] and len(check_id(document)) == 32


def test_the_live_taxonomy_version_is_read() -> None:
    client = FakeClient()
    assert taxonomy_version_of(cast(Client, client)) is None

    client.put("scam_taxonomy/_meta", {"version": 4})

    assert taxonomy_version_of(cast(Client, client)) == 4


# --- the load --------------------------------------------------------------------------


def test_the_load_writes_five_checks_under_their_ids() -> None:
    seed = _seed("miguel_jp_care")
    client = _client_with_user(seed.uid)

    result = load_worker(cast(Client, client), seed, NOW, taxonomy_version=2)

    paths = [p for p in client.store if "/scam_checks/" in p]
    assert result.written == 5 and len(paths) == 5
    assert all(client.store[p]["taxonomy_version"] == 2 for p in paths)
    assert client.commits == 1


def test_a_second_run_changes_nothing_and_a_new_day_moves_the_dates() -> None:
    seed = _seed("miguel_jp_care")
    client = _client_with_user(seed.uid)
    load_worker(cast(Client, client), seed, NOW, None)
    before = copy.deepcopy(client.store)

    load_worker(cast(Client, client), seed, NOW, None)
    assert client.store == before

    load_worker(cast(Client, client), seed, NOW + timedelta(days=1), None)
    assert set(client.store) == set(before)
    assert client.store != before


def test_a_demo_check_taken_out_of_the_file_is_removed_and_a_real_one_stays() -> None:
    seed = _seed("miguel_jp_care")
    client = _client_with_user(seed.uid)
    client.put(f"users/{seed.uid}/scam_checks/{'a' * 32}", {"demo_seed": True})
    client.put(f"users/{seed.uid}/scam_checks/{'b' * 32}", {"input_type": "text"})

    result = load_worker(cast(Client, client), seed, NOW, None)

    assert f"users/{seed.uid}/scam_checks/{'a' * 32}" not in client.store
    assert f"users/{seed.uid}/scam_checks/{'b' * 32}" in client.store
    assert result.removed == 1


def test_a_worker_without_a_user_document_is_told_to_run_the_seed_first() -> None:
    with pytest.raises(LookupError, match="loaders.seed"):
        load_worker(cast(Client, FakeClient()), _seed("miguel_jp_care"), NOW, None)


def test_the_command_line_checks_the_files_without_touching_firestore() -> None:
    assert main(["--dry-run"]) == 0
