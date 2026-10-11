"""The demo-day projection (`scripts/project_demo_usage.py`) against the code it describes.

The projection is only as good as its table of Gemini requests per journey. These tests fail when
a Gemini step is added, removed or moved to another tier without the table following, and they
count the calls of the two new features' real services against it.
"""

from __future__ import annotations

import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.integrations.gemini.model_tiers import ModelTier
from app.services.coach.guard_rules import screen
from tests.fixtures.fake_gemini import FakeGemini
from tests.fixtures.scam_app import make_app
from tests.fixtures.scam_classify import load_mock_body
from tests.fixtures.scam_explain import recordings_for

BACKEND = Path(__file__).resolve().parents[3]
APP = BACKEND / "app"
EMBEDDING_OPERATIONS = {"scam.embed", "radar.embed"}
URL = "/api/v2/scam/analyze"


def _load_projection() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "project_demo_usage", BACKEND / "scripts" / "project_demo_usage.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # a dataclass looks its own module up by name
    spec.loader.exec_module(module)
    return module


projection = _load_projection()


def _steps(reply_tier: str = "classification") -> dict[str, tuple[str, float]]:
    """operation -> (tier, count in one journey), for every step of every journey."""
    found: dict[str, tuple[str, float]] = {}
    for steps in projection.journeys(reply_tier).values():
        for step in steps:
            found[step.operation] = (step.tier, step.count)
    return found


def _prompt_operations() -> set[str]:
    """`pillar.step` for every prompt file: the operation name its Gemini call logs."""
    return {
        f"{path.parent.name}.{path.name.split('.')[0]}"
        for path in (APP / "prompts").glob("*/*.v*.yaml")
    }


def _tiers_written_in_the_services() -> dict[str, str]:
    """operation -> tier, for the calls that name `tier=ModelTier.X` next to their prompt."""
    found: dict[str, str] = {}
    for path in (APP / "services").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        prompts = {
            m.group(1): f"{m.group(2)}.{m.group(3)}"
            for m in re.finditer(r'(\w+)\s*=\s*load_prompt\(\s*"(\w+)",\s*"(\w+)"', text)
        }
        for m in re.finditer(r"operation=(\w+)\.key,\s*tier=ModelTier\.(\w+)", text):
            if m.group(1) in prompts:
                found[prompts[m.group(1)]] = m.group(2).lower()
    return found


def test_every_gemini_step_is_in_a_journey_and_every_journey_step_exists() -> None:
    assert set(_steps()) == _prompt_operations() | EMBEDDING_OPERATIONS


def test_the_tier_of_a_step_is_the_tier_the_code_calls_it_on() -> None:
    written = _tiers_written_in_the_services()
    steps = _steps()

    assert len(written) >= 15, "the scan found too few calls to be checking anything"
    for operation, tier in written.items():
        assert steps[operation][0] == tier, operation


def test_the_coach_steps_follow_the_settings_that_choose_their_tier() -> None:
    settings = get_settings()
    steps = _steps()

    assert steps["coach.reply"][0] == settings.gemini_coach_reply_tier
    assert steps["coach.extract"][0] == settings.gemini_coach_extract_tier
    assert steps["coach.guard"][0] == settings.gemini_coach_guard_tier
    assert steps["coach.plan"][0] == settings.gemini_coach_plan_tier
    assert steps["coach.translate_plan"][0] == settings.gemini_coach_translate_tier
    # Built in `turn_service`, with no setting: the older turns are summarised on the fast tier.
    assert steps["coach.summarise"][0] == ModelTier.CLASSIFICATION.value
    assert steps["coach.review"][0] == "classification"
    assert projection.journeys("extraction")["coach_interview"][0].tier == "extraction"


def test_the_interview_length_is_the_average_of_the_twelve_personas() -> None:
    personas = json.loads(
        (BACKEND / "tests" / "fixtures" / "coach_personas.json").read_text(encoding="utf-8")
    )["personas"]

    average = statistics.mean(len(p["script"]) for p in personas)

    assert projection.INTERVIEW_TURNS == pytest.approx(average, abs=0.01)


def test_the_guard_asks_the_model_about_the_share_of_messages_the_table_says() -> None:
    personas = json.loads(
        (BACKEND / "tests" / "fixtures" / "coach_personas.json").read_text(encoding="utf-8")
    )["personas"]
    messages = [turn["say"] for p in personas for turn in p["script"]]
    asked = sum(screen(text) is None for text in messages)
    per_interview = [s for s in projection.journeys("classification")["coach_interview"]]
    guard = next(s for s in per_interview if s.operation == "coach.guard")

    assert guard.count == pytest.approx(
        projection.INTERVIEW_TURNS * asked / len(messages), abs=0.02
    )


@pytest.mark.parametrize(
    ("case", "journey"), [("high", "scam_check_scam"), ("benign", "scam_check_benign")]
)
def test_a_new_scam_check_makes_the_calls_its_journey_lists(case: str, journey: str) -> None:
    mock = load_mock_body(case)
    fake = FakeGemini(recordings_for(case))
    body = {"text": mock["redacted_text"], "language": mock["language"], "corridor_id": None}

    with TestClient(make_app(fake)) as client:
        assert client.post(URL, json=body).status_code == 200

    # The nearest-scam search is faked in this app; its one embedding is the table's `scam.embed`.
    made = sorted((c["operation"], c["tier"].value) for c in fake.calls)
    listed = sorted(
        (step.operation, step.tier)
        for step in projection.journeys("classification")[journey]
        if step.operation != "scam.embed"
    )
    assert made == listed


def test_a_scam_check_repeated_makes_no_call_at_all() -> None:
    mock = load_mock_body("high")
    fake = FakeGemini(recordings_for("high"))
    body = {"text": mock["redacted_text"], "language": mock["language"], "corridor_id": None}

    with TestClient(make_app(fake)) as client:
        client.post(URL, json=body)
        before = len(fake.calls)
        again = client.post(URL, json=body)

    assert again.json()["cached"] is True and len(fake.calls) == before
