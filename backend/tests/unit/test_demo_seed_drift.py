"""The demo workers' Coach and scam-check seed files hold what the backend would store (NF-HR-003).

`data-scripts/data/seed/coach/` and `.../scam-checks/` are built by `tests/fixtures/demo_seed.py`
through the real plan and analyzer code. These tests rebuild them and fail when a committed file
differs, so a change to the score, the plan rules, the cost baselines, a prompt version or the
masking is noticed here; they also read the loaders' output back through the backend's own models,
which is what data-scripts (which does not import the backend) cannot do.

To rebuild after a deliberate change:  python -m tests.fixtures.demo_seed --write
"""

from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.redact import redact_text
from app.schemas.coach_plan import CoachPlan, CoachScore, slot_hash
from app.schemas.coach_profile import SLOT_NAMES, CoachProfile
from app.schemas.scam import ScamAnalyzeTextRequest
from app.services.coach.plan_document import to_response
from app.services.coach.plan_translation_check import narrative_of, same_figures
from app.services.coach.question_bank import load_question_bank
from app.services.coach.session_document import to_session
from app.services.scam.analyzer import analyze_text
from app.services.scam.check_store import (
    cache_key,
    check_id_for,
    from_document,
    is_usable_as_answer,
    prompt_versions,
)
from app.services.scam.indicators import extract_signals
from tests.fixtures import demo_seed
from tests.fixtures.demo_seed import SEED_DIR, WORKERS, build_all, golden_rows
from tests.fixtures.fake_gemini import FakeGemini
from tests.fixtures.scam_app import FakeTaxonomyRepo
from tests.fixtures.scam_checks import FakeCheckRepo, make_store
from tests.fixtures.scam_classify import load_taxonomy
from tests.fixtures.scam_similar import FakeFinder

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
TAXONOMY = load_taxonomy()


def _loaders() -> tuple[Any, Any]:
    """The data-scripts loaders, imported from their folder: they are plain modules there."""
    path = str(demo_seed.REPO / "data-scripts")
    if path not in sys.path:
        sys.path.insert(0, path)
    return (
        importlib.import_module("src.loaders.demo_coach"),
        importlib.import_module("src.loaders.demo_scam"),
    )


def _coach_seed(stem: str) -> Any:
    _loaders()
    module = importlib.import_module("src.validators.demo_coach")
    return module.load(SEED_DIR / "coach" / f"{stem}.json")


def _scam_seed(stem: str) -> Any:
    _loaders()
    module = importlib.import_module("src.validators.demo_scam")
    return module.load(SEED_DIR / "scam-checks" / f"{stem}.json")


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


# --- the files are what the builders make ------------------------------------------------


async def test_the_committed_files_are_what_the_backend_builds_now() -> None:
    built = await build_all()

    assert {p.name for p in built} == {f"{s}.json" for s in WORKERS}
    for path, body in built.items():
        committed = json.loads(path.read_text(encoding="utf-8"))
        assert committed == body, (
            f"{path.name} is out of date: run `python -m tests.fixtures.demo_seed --write` "
            "from backend/ and commit the files"
        )


# --- the Coach files, read as the backend would ----------------------------------------


@pytest.mark.parametrize("stem", list(WORKERS))
def test_the_loaders_plan_is_one_the_backend_accepts(stem: str) -> None:
    coach, _ = _loaders()
    seed = _coach_seed(stem)

    docs = coach.build_documents(seed, NOW)

    plan = CoachPlan.model_validate(docs.plan["plan"])
    score = CoachScore.model_validate(docs.plan["score"])
    profile = CoachProfile.model_validate(docs.plan["slots"])
    assert slot_hash(profile) == docs.plan["slot_hash"]
    assert docs.plan_id == slot_hash(profile)[:20]
    assert set(docs.plan["slots"]) <= set(SLOT_NAMES)
    response = to_response(docs.plan_id, docs.plan, session_id=docs.session_id, language="en")
    assert response.plan == plan and response.score == score
    assert response.departure_date == docs.departure.isoformat()


@pytest.mark.parametrize("stem", list(WORKERS))
def test_the_translation_changes_words_and_nothing_else(stem: str) -> None:
    coach, _ = _loaders()
    seed = _coach_seed(stem)
    docs = coach.build_documents(seed, NOW)
    english = CoachPlan.model_validate(docs.plan["plan"])
    translated = CoachPlan.model_validate(docs.translations[seed.language]["plan"])

    assert same_figures(english, translated)
    assert narrative_of(english).summary != narrative_of(translated).summary
    assert len(translated.weeks) == 13


@pytest.mark.parametrize("stem", list(WORKERS))
def test_the_session_is_a_completed_one_at_the_plan_stage(stem: str) -> None:
    coach, _ = _loaders()
    docs = coach.build_documents(_coach_seed(stem), NOW)

    session = to_session(docs.session_id, docs.session, load_question_bank())

    assert session.status == "completed" and session.stage == "plan"
    assert session.plan_id == docs.plan_id
    assert all(slot.confirmed for slot in session.slots.values())


def test_the_slot_hash_of_data_scripts_is_the_backends() -> None:
    coach, _ = _loaders()
    slots = {
        "destination_country": "SG",
        "monthly_salary": {"amount": 650.0, "currency": "SGD", "period": "month"},
        "dependents": 3,
        "debt_interest": {"rate_percent": 2.0, "period": "month"},
    }

    assert coach.slot_hash(slots) == slot_hash(CoachProfile.model_validate(slots))


def test_the_plans_numbers_are_the_engines_for_the_seeded_answers() -> None:
    expected = {
        "priya_sg_domestic": (65, "getting_ready"),
        "rajesh_kr_manufacturing": (58, "getting_ready"),
        "miguel_jp_care": (94, "well_prepared"),
    }
    for stem, (total, band) in expected.items():
        score = _coach_seed(stem).plan["score"]
        assert (score["total"], score["band"]) == (total, band)


# --- the scam files, read as the backend would ---------------------------------------


def _checks(stem: str) -> list[tuple[Any, dict[str, Any], str]]:
    _, scam = _loaders()
    out = []
    for check in _scam_seed(stem).checks:
        document = scam.check_document(check, NOW, TAXONOMY.version)
        out.append((check, document, scam.check_id(document)))
    return out


@pytest.mark.parametrize("stem", list(WORKERS))
def test_each_stored_check_is_readable_and_has_the_backends_id_and_key(stem: str) -> None:
    for check, document, check_id in _checks(stem):
        redacted = redact_text(check.message)
        assert document["redacted_text"] == redacted
        key = cache_key(redacted, document["language"])
        assert document["cache_key"] == key and check_id == check_id_for(key)
        detail = from_document(check_id, document)
        assert detail.explainer is not None and detail.explainer_status == "ready"
        assert detail.verdict.is_scam == document["verdict"]["is_scam"]


@pytest.mark.parametrize("stem", list(WORKERS))
def test_the_indicators_are_what_the_rules_find_in_the_message(stem: str) -> None:
    corridor = WORKERS[stem].corridor
    for check, document, _ in _checks(stem):
        redacted = redact_text(check.message)
        signals = extract_signals(check.message, redacted, corridor_id=corridor)  # type: ignore[arg-type]
        stored = [{k: v for k, v in i.items()} for i in document["indicators"]]
        found = [
            i.model_dump(mode="json", exclude={"seen"}, exclude_none=True)
            for i in signals.indicators
        ]
        assert stored == found


@pytest.mark.parametrize("stem", list(WORKERS))
def test_labels_ids_and_phrases_are_valid(stem: str) -> None:
    rows = golden_rows()
    for check, document, _ in _checks(stem):
        verdict = document["verdict"]
        row = rows[check.golden_id]
        assert verdict["is_scam"] is row["is_scam"]
        assert verdict["scam_type"] == row["scam_type"]
        assert verdict["tactics"] == row["tactics"]
        assert verdict["risk_level"] == row["risk_level"]
        if verdict["scam_type"]:
            assert verdict["scam_type"] in TAXONOMY.types
        assert set(verdict["tactics"]) <= set(TAXONOMY.tactics)
        assert all(p in document["redacted_text"] for p in verdict["trigger_phrases"])
        if verdict["is_scam"]:
            assert len(verdict["trigger_phrases"]) >= 1
            assert document["explainer"]["kind"] == "scam"
            assert len(document["explainer"]["next_steps"]) == 3
        else:
            assert document["explainer"]["kind"] == "benign"


@pytest.mark.parametrize("stem", list(WORKERS))
def test_the_prompt_versions_are_the_ones_the_backend_serves_now(stem: str) -> None:
    for _, document, _ in _checks(stem):
        is_scam = document["verdict"]["is_scam"]
        assert document["prompt_versions"] == prompt_versions(is_scam)
        assert is_usable_as_answer(document, TAXONOMY.version)


async def test_pasting_a_seeded_message_again_is_answered_from_the_stored_check() -> None:
    # The finale's pre-warm: the same message, in the language it was checked in, costs no model
    # call. A FakeGemini with no recording raises if the analyzer asks it anything.
    for stem, worker in WORKERS.items():
        repo = FakeCheckRepo()
        for _check, document, check_id in _checks(stem):
            repo.docs[(worker.uid, check_id)] = {
                **document,
                "created_at": NOW,
                "last_checked_at": NOW,
                "expires_at": datetime(2099, 1, 1, tzinfo=UTC),
            }
        store = make_store(repo)
        for check in _scam_seed(stem).checks:
            response = await analyze_text(
                ScamAnalyzeTextRequest(
                    text=check.message,
                    language=worker.language,  # type: ignore[arg-type]
                    corridor_id=worker.corridor,  # type: ignore[arg-type]
                ),
                worker.uid,
                FakeGemini({}),  # type: ignore[arg-type]
                FakeTaxonomyRepo(TAXONOMY),  # type: ignore[arg-type]
                FakeFinder(),  # type: ignore[arg-type]
                store,
            )
            assert response.cached is True, check.id
            assert response.verdict.is_scam == check.document["verdict"]["is_scam"]
