"""The flags mocks in docs/mocks/flags/ must always parse as what the backend really sends."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.schemas.errors import ErrorEnvelope
from app.schemas.feature_flags import FeatureFlagsResponse

MOCKS = Path(__file__).resolve().parents[2].parent / "docs" / "mocks" / "flags"
FILES = sorted(MOCKS.glob("*.json"))


def _load(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def test_the_flags_mocks_exist() -> None:
    assert {path.name for path in FILES} >= {
        "flags-all-off.json",
        "flags-coach-on.json",
        "flags-scam-on.json",
        "flags-unauthenticated.json",
    }


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_each_mock_is_a_get_of_the_flags_route(path: Path) -> None:
    assert _load(path)["request"] == "GET /api/v2/flags"


@pytest.mark.parametrize(
    "path", [p for p in FILES if _load(p)["status"] == 200], ids=lambda path: path.name
)
def test_a_200_mock_fits_the_response_model(path: Path) -> None:
    body = FeatureFlagsResponse.model_validate(_load(path)["body"])

    assert set(body.model_dump()) == {"coach", "scam"}


@pytest.mark.parametrize(
    "path", [p for p in FILES if _load(p)["status"] >= 400], ids=lambda path: path.name
)
def test_an_error_mock_is_the_standard_envelope(path: Path) -> None:
    mock = _load(path)
    envelope = ErrorEnvelope.model_validate(mock["body"])

    assert envelope.request_id == mock["headers"]["X-Request-ID"]
