"""The scam mocks in docs/mocks/scam/ must always parse as what the backend will really send.

Shape alone is not enough, so this also checks the facts a screen leans on: the type and tactic
ids exist in the taxonomy, the stored text is already redacted, an indicator id is the real hash,
and the history list, the detail and the analyze answer agree about the same check.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.redact import redact_text
from app.schemas.errors import ErrorEnvelope
from app.schemas.scam import (
    MAX_REPORT_DESCRIPTION_CHARS,
    MAX_TEXT_CHARS,
    ScamAnalyzeResponse,
    ScamAnalyzeTextRequest,
    ScamCheckDetail,
    ScamCheckListResponse,
    ScamReportRequest,
    ScamReportResponse,
    ScamVerdict,
)

REPO = Path(__file__).resolve().parents[3]
MOCKS = REPO / "docs" / "mocks" / "scam"
DOC = REPO / "docs" / "api" / "v2-scam.md"
TAXONOMY = REPO / "data-scripts" / "data" / "source" / "scam-taxonomy"
FILES = sorted(MOCKS.glob("*.json"))

# Codes of docs/api/v2-conventions.md section 2, and the three this feature adds (v2-scam.md).
KNOWN_CODES = {
    "validation_failed",
    "rate_limited",
    "not_found",
    "unauthenticated",
    "payload_too_large",
    "ai_busy",
    "ai_unavailable",
    "ai_timeout",
    "ai_bad_response",
    "invalid_cursor",
    "unsupported_media_type",
    "image_unreadable",
    "not_a_scam",
}


def _load(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _taxonomy(name: str) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = _load(TAXONOMY / f"{name}.json")["entries"]
    return entries


TYPES = _taxonomy("types")
TACTICS = _taxonomy("tactics")


def _model_for(request: str) -> type[Any] | None:
    method, path = request.split(" ", 1)
    path = path.split("?", 1)[0]
    if (method, path) == ("POST", "/api/v2/scam/analyze"):
        return ScamAnalyzeResponse
    if (method, path) == ("GET", "/api/v2/scam/checks"):
        return ScamCheckListResponse
    if method == "GET" and path.startswith("/api/v2/scam/checks/"):
        return ScamCheckDetail
    if method == "POST" and path.startswith("/api/v2/scam/checks/") and path.endswith("/report"):
        return ScamReportResponse
    return None


def _ok(path: Path) -> bool:
    return _load(path)["status"] < 400


def _checks() -> list[tuple[str, dict[str, Any]]]:
    """Every mock body that is one check (an analyze answer or a detail), with its file name."""
    found = []
    for path in FILES:
        mock = _load(path)
        if (
            mock["status"] == 200
            and isinstance(mock.get("body"), dict)
            and "verdict" in mock["body"]
        ):
            found.append((path.name, mock["body"]))
    return found


def test_the_scam_mocks_exist() -> None:
    names = {path.name for path in FILES}

    assert {
        "analyze-01-high-risk.json",
        "analyze-02-medium-risk.json",
        "analyze-03-low-risk.json",
        "analyze-04-benign.json",
        "checks-list-01-first-page.json",
        "check-01-high-risk.json",
        "report-01-created.json",
    } <= names


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_each_mock_is_a_request_the_contract_has(path: Path) -> None:
    mock = _load(path)

    assert _model_for(mock["request"]) is not None
    assert {"description", "request", "status"} <= set(mock)


@pytest.mark.parametrize("path", [p for p in FILES if _ok(p)], ids=lambda path: path.name)
def test_a_success_mock_fits_the_response_model_with_no_extra_fields(path: Path) -> None:
    mock = _load(path)
    model = _model_for(mock["request"])
    assert model is not None

    parsed = model.model_validate(mock["body"])

    # What was set, written back out, is the file again: a stray or misspelt field would be dropped.
    assert parsed.model_dump(mode="json", exclude_unset=True) == mock["body"]


@pytest.mark.parametrize("path", [p for p in FILES if not _ok(p)], ids=lambda path: path.name)
def test_an_error_mock_is_the_standard_envelope(path: Path) -> None:
    mock = _load(path)
    envelope = ErrorEnvelope.model_validate(mock["body"])

    assert envelope.request_id == mock["headers"]["X-Request-ID"]
    assert envelope.code in KNOWN_CODES
    assert (envelope.details is not None) == (envelope.code == "validation_failed")


# --- what a screen can rely on ------------------------------------------------------------


@pytest.mark.parametrize(("name", "check"), _checks(), ids=lambda value: str(value)[:40])
def test_the_ids_in_a_check_are_in_the_taxonomy(name: str, check: dict[str, Any]) -> None:
    verdict = check["verdict"]

    assert verdict["scam_type"] is None or verdict["scam_type"] in TYPES
    assert set(verdict["tactics"]) <= set(TACTICS)
    explainer = check["explainer"]
    if explainer is not None and explainer["kind"] == "scam":
        assert {why["tactic"] for why in explainer["why_it_works"]} <= set(verdict["tactics"])
    assert all(s["scam_type"] is None or s["scam_type"] in TYPES for s in check["similar"])


@pytest.mark.parametrize(("name", "check"), _checks(), ids=lambda value: str(value)[:40])
def test_the_stored_text_is_already_redacted_and_the_phrases_come_from_it(
    name: str, check: dict[str, Any]
) -> None:
    text = check["redacted_text"]

    assert redact_text(text) == text
    assert all(phrase in text for phrase in check["verdict"]["trigger_phrases"])
    for indicator in check["indicators"]:
        assert indicator["value"] not in text


def _normal(kind: str, value: str) -> str:
    if kind == "phone":
        return "".join(ch for ch in value if ch.isdigit())
    if kind == "url":
        return value.lower().removeprefix("www.")
    return value.lower().lstrip("@").strip()


@pytest.mark.parametrize(("name", "check"), _checks(), ids=lambda value: str(value)[:40])
def test_an_indicator_id_is_the_real_hash_of_its_kind_and_value(
    name: str, check: dict[str, Any]
) -> None:
    for indicator in check["indicators"]:
        key = hashlib.sha256(
            f"{indicator['kind']}:{_normal(indicator['kind'], indicator['value'])}".encode()
        ).hexdigest()

        assert indicator["id"] == key[:8]
    assert len({i["id"] for i in check["indicators"]}) == len(check["indicators"])


@pytest.mark.parametrize(("name", "check"), _checks(), ids=lambda value: str(value)[:40])
def test_a_check_expires_90_days_after_it_was_made_unless_it_was_repeated(
    name: str, check: dict[str, Any]
) -> None:
    if check.get("cached"):
        pytest.skip("a repeated check moves its expiry forward")
    created = datetime.fromisoformat(check["created_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(check["expires_at"].replace("Z", "+00:00"))

    assert created.tzinfo is UTC
    assert expires - created == timedelta(days=90)


def _by_id(prefix: str) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for n, c in _checks() if n.startswith(prefix)}


def test_the_analyze_answers_and_the_stored_checks_describe_the_same_checks() -> None:
    analyzed = _by_id("analyze-0")
    stored = _by_id("check-0")

    for check_id, detail in stored.items():
        answer = {k: v for k, v in analyzed[check_id].items() if k != "cached"}
        assert answer == detail


def test_the_history_rows_say_what_their_checks_say() -> None:
    stored = _by_id("check-0")
    rows = [
        row
        for name in ("checks-list-01-first-page.json", "checks-list-02-last-page.json")
        for row in _load(MOCKS / name)["body"]["items"]
    ]

    assert {row["id"] for row in rows} == set(stored)
    for row in rows:
        check = stored[row["id"]]
        assert row["is_scam"] == check["verdict"]["is_scam"]
        assert row["scam_type"] == check["verdict"]["scam_type"]
        assert row["risk_level"] == check["verdict"]["risk_level"]
        assert row["created_at"] == check["created_at"]
        assert row["excerpt"] == check["redacted_text"][:140]
    created = [row["created_at"] for row in rows[:3]]
    assert created == sorted(created, reverse=True), "newest first"


def test_the_report_names_the_radar_profile_of_the_scam_type() -> None:
    report = _load(MOCKS / "report-01-created.json")["body"]
    check = _by_id("check-0")["k_01"]
    scam_type = check["verdict"]["scam_type"]

    assert report["entity_slug"] == "scam-" + scam_type.replace("_", "-")
    assert report["entity_name"] == TYPES[scam_type]["label"]
    assert (
        _load(MOCKS / "report-02-already-reported.json")["body"]["report_id"] == report["report_id"]
    )


def test_each_risk_level_and_a_benign_message_has_a_mock() -> None:
    checks = {c["id"]: c["verdict"] for c in _by_id("analyze-0").values()}

    assert {v["risk_level"] for v in checks.values() if v["is_scam"]} == {"low", "medium", "high"}
    assert any(not v["is_scam"] for v in checks.values())


# --- the request models -------------------------------------------------------------------


def test_a_pasted_message_is_trimmed_and_kept_whole() -> None:
    request = ScamAnalyzeTextRequest(text="  Pay today.\n", language="en")

    assert request.text == "Pay today."
    assert request.corridor_id is None


@pytest.mark.parametrize("text", ["", "   \n\t "])
def test_an_empty_message_is_refused(text: str) -> None:
    with pytest.raises(ValidationError, match="empty"):
        ScamAnalyzeTextRequest(text=text, language="en")


def test_a_message_over_the_limit_is_refused_not_cut() -> None:
    assert ScamAnalyzeTextRequest(text="x" * MAX_TEXT_CHARS, language="en")

    with pytest.raises(ValidationError, match="at most 4000"):
        ScamAnalyzeTextRequest(text="x" * (MAX_TEXT_CHARS + 1), language="en")


@pytest.mark.parametrize(("field", "value"), [("language", "ar"), ("corridor_id", "SG-NP")])
def test_a_language_or_corridor_outside_the_project_is_refused(field: str, value: str) -> None:
    body: dict[str, Any] = {"text": "hi", "language": "en", field: value}

    with pytest.raises(ValidationError):
        ScamAnalyzeTextRequest.model_validate(body)


def test_a_report_may_confirm_no_indicators_and_keep_the_text() -> None:
    request = ScamReportRequest(indicator_ids=[])

    assert request.description is None


@pytest.mark.parametrize(
    "ids", [["8c83cb97", "8c83cb97"], ["zzzzzzzz"], ["8c83cb9"], [f"{i:08x}" for i in range(11)]]
)
def test_a_report_with_bad_indicator_ids_is_refused(ids: list[str]) -> None:
    with pytest.raises(ValidationError):
        ScamReportRequest(indicator_ids=ids)


def test_a_reported_description_cannot_be_blank_or_over_the_limit() -> None:
    with pytest.raises(ValidationError, match="empty"):
        ScamReportRequest(indicator_ids=[], description="  ")
    with pytest.raises(ValidationError, match="at most 1000"):
        ScamReportRequest(indicator_ids=[], description="x" * (MAX_REPORT_DESCRIPTION_CHARS + 1))


def _verdict(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "is_scam": True,
        "scam_type": "lottery",
        "tactics": ["authority"],
        "risk_level": "low",
        "confidence": 0.6,
        "trigger_phrases": [],
    }
    return {**base, **changes}


@pytest.mark.parametrize(
    "changes",
    [
        {"scam_type": None},
        {"is_scam": False},
        {"is_scam": False, "scam_type": None, "tactics": [], "risk_level": "high"},
        {"confidence": 1.2},
        {"trigger_phrases": ["x"] * 6},
        {"trigger_phrases": ["x" * 81]},
        {"tactics": ["urgency"] * 7},
    ],
)
def test_a_verdict_that_contradicts_itself_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ScamVerdict.model_validate(_verdict(**changes))


def test_a_message_that_is_not_a_scam_is_a_verdict_with_no_type() -> None:
    verdict = ScamVerdict.model_validate(
        _verdict(is_scam=False, scam_type=None, tactics=[], risk_level="low")
    )

    assert verdict.is_scam is False


# --- the contract document ----------------------------------------------------------------


def test_the_contract_document_names_every_route_and_the_codes_it_adds() -> None:
    text = DOC.read_text(encoding="utf-8")

    for route in (
        "/api/v2/scam/analyze",
        "/api/v2/scam/checks",
        "/api/v2/scam/checks/{id}",
        "/api/v2/scam/checks/{id}/report",
    ):
        assert f"`{route}`" in text
    for code in ("unsupported_media_type", "image_unreadable", "not_a_scam"):
        assert f"`{code}`" in text


def test_the_contract_document_describes_the_limits_the_models_enforce() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert f"{MAX_TEXT_CHARS:,}" in text
    assert f"{MAX_REPORT_DESCRIPTION_CHARS:,}" in text
    for mock in FILES:
        if mock.name.startswith("analyze-0"):
            assert mock.name.removesuffix(".json").removeprefix("analyze-") in text
