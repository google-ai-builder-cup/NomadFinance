"""The backend's classifier, called the way the analyzer calls it (NF-SA-014).

`classify_message` is the step that decides `is_scam`, the type, the tactics and the risk, so it
is what the golden set scores. The messages go through the same steps in front of it as a pasted
one does in `app/services/scam/analyzer.py`: the request model (trims the text), `redact_text`,
`extract_signals`. What follows it (the explainer, the search for similar scams, the cache and the
hourly limit) cannot change the verdict and is not run, so the eval needs no Firestore.

data-scripts does not depend on the backend, so it is imported by name when a run starts and its
packages are expected in the environment (`pip install -r backend/requirements.txt`). Nothing
here is typed against it for the same reason: `scam_patterns_check.py` loads the redactor the same
way.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.scam_eval.metrics import Prediction
from src.scam_eval.runner import Classifier, ClassifyError
from src.validators.scam_golden import GoldenRow
from src.validators.scam_taxonomy import Entry, Taxonomy

BACKEND_DIR = Path(__file__).resolve().parents[3] / "backend"


class SetupError(RuntimeError):
    """The backend cannot be loaded or configured here: nothing was sent to Gemini."""


def _settings(config: Any) -> Any:
    # The backend's settings fail fast on two values the eval never uses; a placeholder lets
    # them load without a real Radar key in the shell. An APP_ENV or key already set wins.
    os.environ.setdefault("APP_ENV", "local")
    os.environ.setdefault("RADAR_REPORTER_HASH_SECRET", "unused-by-the-scam-eval")
    try:
        settings = config.get_settings()
    except ValidationError as exc:
        missing = sorted({str(e["loc"][0]).upper() for e in exc.errors() if e["loc"]})
        raise SetupError(
            f"the backend settings are not complete ({', '.join(missing)}): set them in this "
            "shell or in backend/.env.local"
        ) from exc
    if not settings.gemini_api_key.get_secret_value().strip():
        raise SetupError("GEMINI_API_KEY is empty: set it in this shell or in backend/.env.local")
    return settings


def _taxonomy_for_backend(taxonomy: Taxonomy, taxonomy_class: Any) -> Any:
    """The documents the loader writes, in the order the backend reads them back (`order`)."""

    def documents(entries: dict[str, Entry]) -> dict[str, dict[str, Any]]:
        ordered = sorted(entries.items(), key=lambda item: item[1].order)
        return {name: e.model_dump(mode="json", exclude_none=True) for name, e in ordered}

    # `version` is the Firestore counter a stored check records; the classifier does not read it.
    return taxonomy_class(
        version=0, types=documents(taxonomy.types), tactics=documents(taxonomy.tactics)
    )


def load_backend_classifier(taxonomy: Taxonomy) -> Classifier:
    """Build the classifier the analyzer uses, with a Gemini client from the backend's settings.

    Args:
        taxonomy: The local taxonomy files, which stand in for the Firestore collection.

    Raises:
        SetupError: The backend is missing or not installed, or its settings are incomplete.
    """
    if not (BACKEND_DIR / "app").is_dir():
        raise SetupError(f"the backend is not at {BACKEND_DIR}")
    if str(BACKEND_DIR) not in sys.path:
        sys.path.append(str(BACKEND_DIR))
    try:
        config = importlib.import_module("app.config")
        gemini = importlib.import_module("app.integrations.gemini")
        classifier = importlib.import_module("app.services.scam.classifier")
        indicators = importlib.import_module("app.services.scam.indicators")
        redact = importlib.import_module("app.core.redact")
        schemas = importlib.import_module("app.schemas.scam")
        repo = importlib.import_module("app.repositories.scam_taxonomy_repo")
    except ModuleNotFoundError as exc:
        raise SetupError(
            f"the backend needs {exc.name!r}: pip install -r backend/requirements.txt"
        ) from exc

    settings = _settings(config)
    client = gemini.GeminiClient(settings)
    backend_taxonomy = _taxonomy_for_backend(taxonomy, repo.ScamTaxonomy)

    async def classify(row: GoldenRow) -> Prediction:
        request = schemas.ScamAnalyzeTextRequest(
            text=row.text, language=row.language, corridor_id=row.corridor_id
        )
        redacted = redact.redact_text(request.text)
        signals = indicators.extract_signals(request.text, redacted, corridor_id=row.corridor_id)
        try:
            result = await classifier.classify_message(redacted, backend_taxonomy, client, signals)
        except gemini.GeminiError as exc:
            raise ClassifyError(f"{type(exc).__name__}: {exc}") from exc
        verdict = result.verdict
        return Prediction(verdict.is_scam, verdict.scam_type, verdict.confidence)

    prompt = classifier.CLASSIFY_PROMPT
    model = gemini.model_for(gemini.ModelTier.CLASSIFICATION, settings)
    return Classifier(classify, model=model, prompt=f"{prompt.key} v{prompt.version}")
