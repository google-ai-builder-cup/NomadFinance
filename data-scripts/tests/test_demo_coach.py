"""The demo workers' Coach seed and its loader (NF-HR-003)."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from google.cloud.firestore import Client
from pydantic import ValidationError

from src.config import SEED_COACH_DIR, SEED_USERS_DIR
from src.loaders.demo_coach import (
    SESSION_KEEP,
    build_documents,
    checkins_for,
    load_worker,
    main,
    slot_hash,
)
from src.validators.demo_coach import DEPARTURE, CoachSeed, load, seed_files, tokens
from src.validators.demo_user import load as load_user
from tests.fake_firestore import FakeClient

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
STEMS = ["miguel_jp_care", "priya_sg_domestic", "rajesh_kr_manufacturing"]


def _path(stem: str) -> Path:
    return SEED_COACH_DIR / f"{stem}.json"


def _raw(stem: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_path(stem).read_text(encoding="utf-8")))


def _seed(stem: str) -> CoachSeed:
    return load(_path(stem))


def _client_with_user(uid: str) -> FakeClient:
    client = FakeClient()
    client.put(f"users/{uid}", {"preferred_language": "hi"})
    return client


# --- the committed files ---------------------------------------------------------------


def test_there_is_one_file_for_each_demo_worker() -> None:
    assert [p.stem for p in seed_files()] == STEMS


@pytest.mark.parametrize("stem", STEMS)
def test_each_file_is_valid_and_belongs_to_the_worker_of_the_same_name(stem: str) -> None:
    seed = _seed(stem)

    assert seed.uid == load_user(SEED_USERS_DIR / f"{stem}.json").uid
    assert seed.language == load_user(SEED_USERS_DIR / f"{stem}.json").user.preferred_language
    assert seed.signal_sharing.coach and seed.signal_sharing.scam


def test_the_three_plans_differ_as_the_workers_do() -> None:
    scores = {s: _seed(s).plan["score"]["total"] for s in STEMS}
    corridors = {s: _seed(s).plan.get("corridor_id") for s in STEMS}

    assert scores == {
        "miguel_jp_care": 94,
        "priya_sg_domestic": 65,
        "rajesh_kr_manufacturing": 58,
    }
    # Korea starts none of the six corridors, so Rajesh's plan has no provider quote.
    assert corridors["rajesh_kr_manufacturing"] is None
    assert _seed("rajesh_kr_manufacturing").plan["plan"]["remittance"]["provider"] is None
    assert _seed("priya_sg_domestic").plan["plan"]["remittance"]["provider"] is not None


def test_the_plan_is_in_the_workers_language_and_keeps_every_figure() -> None:
    seed = _seed("priya_sg_domestic")
    english = seed.plan["plan"]
    hindi = seed.translations["hi"]["plan"]

    assert english["monthly_budget"] == hindi["monthly_budget"]
    assert english["remittance"] == hindi["remittance"]
    assert english["summary"] != hindi["summary"]
    assert tokens(english["summary"]) == tokens(hindi["summary"])


# --- the checker ------------------------------------------------------------------------


def _broken(stem: str, edit: Any) -> dict[str, Any]:
    raw = copy.deepcopy(_raw(stem))
    edit(raw)
    return raw


def test_a_translation_that_changes_a_number_is_refused() -> None:
    raw = _broken(
        "priya_sg_domestic",
        lambda r: r["translations"]["hi"]["plan"].update(summary="आप 700 SGD कमाएँगे।"),
    )

    with pytest.raises(ValidationError, match="changes a number"):
        CoachSeed.model_validate(raw)


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda r: r["plan"]["slots"].update(departure_date="2026-12-12"), "@departure"),
        (lambda r: r["session"].update(status="active"), "completed"),
        (lambda r: r["plan"]["plan"]["weeks"].pop(), "weeks 1 to 13"),
        (lambda r: r.update(plan_created_days_ago=10), "dated after the departure"),
        (lambda r: r.update(departure_in_days=-5), "answered in the future"),
        (lambda r: r["translations"].update(ne={}), "translations must hold exactly"),
    ],
)
def test_the_checker_refuses_what_the_loader_relies_on(edit: Any, message: str) -> None:
    raw = _broken("priya_sg_domestic", edit)

    with pytest.raises(ValidationError, match=message):
        CoachSeed.model_validate(raw)


# --- the documents ---------------------------------------------------------------------


def test_the_departure_is_counted_from_the_day_of_the_load() -> None:
    docs = build_documents(_seed("priya_sg_domestic"), NOW)

    assert docs.departure == (NOW - timedelta(days=40)).date()
    assert docs.plan["slots"]["departure_date"] == docs.departure.isoformat()
    assert docs.plan["departure_date"] == docs.departure.isoformat()
    assert docs.session["slots"]["departure_date"]["value"] == docs.departure.isoformat()
    assert DEPARTURE not in json.dumps(docs.plan, default=str)
    assert DEPARTURE not in json.dumps(docs.session, default=str)


def test_the_plan_id_is_the_hash_of_the_answers_and_the_session_points_to_it() -> None:
    docs = build_documents(_seed("miguel_jp_care"), NOW)

    assert docs.plan_id == slot_hash(docs.plan["slots"])[:20]
    assert docs.plan["slot_hash"].startswith(docs.plan_id)
    assert docs.session["plan_id"] == docs.plan_id
    assert docs.plan["session_id"] == docs.session_id == "demo_s_01"


def test_the_same_day_gives_the_same_plan_and_another_day_another() -> None:
    seed = _seed("priya_sg_domestic")

    same = build_documents(seed, NOW + timedelta(hours=3)).plan_id
    later = build_documents(seed, NOW + timedelta(days=1)).plan_id

    assert same == build_documents(seed, NOW).plan_id
    assert later != same


def test_every_instant_moves_together_so_the_rates_stay_older_than_the_plan() -> None:
    docs = build_documents(_seed("priya_sg_domestic"), NOW)
    created = docs.plan["created_at"]

    assert NOW - timedelta(days=52, hours=1) < created < NOW - timedelta(days=51)
    assert docs.plan["rates_as_of"] <= created
    assert all(fx["fetched_at"] <= created for fx in docs.plan["grounding"]["fx"])
    assert (
        docs.session["created_at"] < docs.session["completed_at"] <= created + timedelta(minutes=1)
    )
    assert docs.translations["hi"]["created_at"] > docs.plan["rates_as_of"]


def test_a_completed_session_is_kept_for_30_days_from_the_load() -> None:
    docs = build_documents(_seed("priya_sg_domestic"), NOW)

    assert docs.session["expires_at"] == NOW + SESSION_KEEP
    assert docs.session["status"] == "completed"


def test_priya_has_answered_her_day_30_check_in_and_rajesh_has_none_due() -> None:
    priya = build_documents(_seed("priya_sg_domestic"), NOW)
    rajesh = build_documents(_seed("rajesh_kr_manufacturing"), NOW)

    d30 = priya.plan["checkins"]["d30"]
    assert d30["due_on"] == (priya.departure + timedelta(days=30)).isoformat()
    assert d30["answers"] == {"remittance": "on_track", "savings": "behind", "pay": "full_on_time"}
    assert d30["notified_at"] < d30["answered_at"] <= NOW
    assert set(priya.plan["checkins"]) == {"d30"}
    assert "checkins" not in rajesh.plan
    assert rajesh.departure == (NOW + timedelta(days=21)).date()


def test_a_reminder_with_no_answer_is_written_when_the_day_has_come() -> None:
    seed = _seed("priya_sg_domestic")
    seed.checkins.clear()

    entries = checkins_for(seed, NOW.date() - timedelta(days=40))

    assert set(entries) == {"d30"} and "answers" not in entries["d30"]


def test_the_documents_carry_the_marker_the_cleanup_relies_on() -> None:
    docs = build_documents(_seed("miguel_jp_care"), NOW)

    assert docs.plan["demo_seed"] is docs.session["demo_seed"] is True
    assert docs.translations["tl"]["demo_seed"] is True


# --- the load --------------------------------------------------------------------------


def test_the_load_writes_the_session_the_plan_its_translation_and_the_opt_in() -> None:
    seed = _seed("priya_sg_domestic")
    client = _client_with_user(seed.uid)

    result = load_worker(cast(Client, client), seed, NOW)

    base = f"users/{seed.uid}"
    assert f"{base}/coach_sessions/demo_s_01" in client.store
    assert f"{base}/coach_plans/{result.plan_id}" in client.store
    assert f"{base}/coach_plans/{result.plan_id}/translations/hi" in client.store
    assert client.store[base]["signal_sharing"] == {"coach": True, "scam": True}
    assert client.store[base]["preferred_language"] == "hi"  # merged, not replaced
    assert client.commits == 1


def test_a_second_run_on_the_same_day_changes_nothing() -> None:
    seed = _seed("priya_sg_domestic")
    client = _client_with_user(seed.uid)
    load_worker(cast(Client, client), seed, NOW)
    before = copy.deepcopy(client.store)

    result = load_worker(cast(Client, client), seed, NOW)

    assert client.store == before and result.removed == 0


def test_a_run_on_another_day_replaces_the_plan_it_made_before() -> None:
    seed = _seed("priya_sg_domestic")
    client = _client_with_user(seed.uid)
    first = load_worker(cast(Client, client), seed, NOW)

    second = load_worker(cast(Client, client), seed, NOW + timedelta(days=1))

    base = f"users/{seed.uid}/coach_plans"
    assert second.plan_id != first.plan_id and second.removed == 1
    assert f"{base}/{first.plan_id}" not in client.store
    assert f"{base}/{first.plan_id}/translations/hi" not in client.store
    assert f"{base}/{second.plan_id}/translations/hi" in client.store


def test_a_plan_the_worker_made_is_never_removed() -> None:
    seed = _seed("priya_sg_domestic")
    client = _client_with_user(seed.uid)
    client.put(f"users/{seed.uid}/coach_plans/aaaaaaaaaaaaaaaaaaaa", {"slot_hash": "x"})
    client.put(f"users/{seed.uid}/coach_sessions/s_real", {"status": "active"})

    result = load_worker(cast(Client, client), seed, NOW)

    assert f"users/{seed.uid}/coach_plans/aaaaaaaaaaaaaaaaaaaa" in client.store
    assert f"users/{seed.uid}/coach_sessions/s_real" in client.store
    assert result.removed == 0


def test_a_worker_without_a_user_document_is_told_to_run_the_seed_first() -> None:
    seed = _seed("priya_sg_domestic")

    with pytest.raises(LookupError, match="loaders.seed"):
        load_worker(cast(Client, FakeClient()), seed, NOW)


def test_the_command_line_checks_the_files_without_touching_firestore(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--dry-run"]) == 0
    assert main(["--dry-run", "--only", "miguel_jp_care"]) == 0
