"""The eval's wiring to the backend's real classifier, with the Gemini call replaced.

Needs the backend's own packages (`pip install -r backend/requirements.txt`), which the data
scripts' CI does not install: there this module is skipped. The manual eval workflow installs
them, and so does the backend's virtual environment, which can run it from data-scripts/.
"""

from __future__ import annotations

import asyncio
import importlib
import re
import sys
from collections.abc import Iterator
from typing import Any

import pytest

from src.loaders.scam_patterns_calibrate import golden_rows
from src.scam_eval.backend import BACKEND_DIR, SetupError, load_backend_classifier
from src.scam_eval.metrics import Prediction
from src.scam_eval.runner import Classifier, ClassifyError
from src.validators.scam_golden import GoldenRow
from src.validators.scam_taxonomy import load_taxonomy

for _package in ("pydantic_settings", "tenacity", "limits", "yaml", "google.genai"):
    pytest.importorskip(_package)


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The backend's settings from this test's environment only, never from backend/.env.local.

    A developer's own key must not leak into a test, and a patch that fails to hold must reach
    Google with a made-up key, not a real one.
    """
    if str(BACKEND_DIR) not in sys.path:
        sys.path.append(str(BACKEND_DIR))
    config = importlib.import_module("app.config")
    monkeypatch.setitem(config.Settings.model_config, "env_file", None)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    # Registered and then removed, so the loader's placeholder for it is undone afterwards.
    monkeypatch.setenv("RADAR_REPORTER_HASH_SECRET", "x")
    monkeypatch.delenv("RADAR_REPORTER_HASH_SECRET")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def answer_with(monkeypatch: pytest.MonkeyPatch, **verdict: Any) -> list[dict[str, Any]]:
    """Replace the Gemini call: every request is kept, and the answer is `verdict`."""
    calls: list[dict[str, Any]] = []
    client_class = importlib.import_module("app.integrations.gemini").GeminiClient

    async def generate_structured(self: object, **kwargs: Any) -> Any:
        calls.append(kwargs)
        fields: dict[str, Any] = {
            "is_scam": False,
            "scam_type": None,
            "tactics": [],
            "risk_level": "low",
            "confidence": 0.5,
            "trigger_phrases": [],
            "message_language": "en",
            "details": {},
        }
        return kwargs["response_model"].model_validate(fields | verdict)

    monkeypatch.setattr(client_class, "generate_structured", generate_structured)
    return calls


def loaded() -> Classifier:
    return load_backend_classifier(load_taxonomy())


def classify(classifier: Classifier, row: GoldenRow) -> Prediction:
    async def one() -> Prediction:
        return await classifier.classify(row)

    return asyncio.run(one())


def test_a_message_goes_through_the_backends_own_steps_to_the_classifier_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classifier = loaded()
    row = next(r for r in golden_rows() if r.is_scam and "https://" in r.text)
    link = re.search(r"https://\S+", row.text)
    assert link is not None
    calls = answer_with(
        monkeypatch, is_scam=True, scam_type=row.scam_type, risk_level="high", confidence=0.93
    )

    prediction = classify(classifier, row)

    assert prediction == Prediction(True, row.scam_type, 0.93)
    [call] = calls
    gemini = importlib.import_module("app.integrations.gemini")
    prompt = importlib.import_module("app.services.scam.classifier").CLASSIFY_PROMPT
    assert call["operation"] == "scam.classify"
    assert call["tier"] == gemini.ModelTier.CLASSIFICATION
    assert call["system_instruction"] == prompt.system
    assert call["temperature"] == 0.0
    # The model sees the masked message: the link was replaced before it was sent.
    assert "[URL]" in call["contents"]
    assert link.group(0).rstrip(".,") not in call["contents"]


def test_the_model_is_given_the_taxonomy_types_in_the_order_the_backend_reads_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classifier = loaded()
    calls = answer_with(monkeypatch)

    classify(classifier, golden_rows()[0])

    types = load_taxonomy().types
    expected = [name for name, entry in sorted(types.items(), key=lambda i: i[1].order)]
    ids = re.findall(r'"id": "([a-z_]+)"', calls[0]["contents"])
    assert ids[: len(expected)] == expected


def test_a_benign_answer_and_its_confidence_come_back_as_the_prediction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classifier = loaded()
    answer_with(monkeypatch, is_scam=False, confidence=0.81)

    prediction = classify(classifier, golden_rows()[0])

    assert prediction == Prediction(False, None, 0.81)


def test_a_gemini_failure_is_a_failed_message_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classifier = loaded()
    gemini = importlib.import_module("app.integrations.gemini")

    async def refuse(self: object, **kwargs: Any) -> Any:
        raise gemini.GeminiRateLimitError("quota")

    monkeypatch.setattr(gemini.GeminiClient, "generate_structured", refuse)

    with pytest.raises(ClassifyError, match="GeminiRateLimitError: quota"):
        classify(classifier, golden_rows()[0])


def test_the_report_can_say_which_model_and_prompt_were_scored() -> None:
    classifier = loaded()

    config = importlib.import_module("app.config")
    gemini = importlib.import_module("app.integrations.gemini")
    model = gemini.model_for(gemini.ModelTier.CLASSIFICATION, config.get_settings())
    assert classifier.model == model
    assert re.fullmatch(r"scam\.classify v\d+", classifier.prompt)


def test_an_empty_key_stops_the_run_before_any_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "  ")

    with pytest.raises(SetupError, match="GEMINI_API_KEY is empty"):
        loaded()


def test_a_missing_key_names_what_to_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY")

    with pytest.raises(SetupError, match="GEMINI_API_KEY"):
        loaded()
