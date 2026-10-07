"""A worker's own report, and the models that read it, must never produce a scam report's types.

`scam_type`, `scam_message` and `scam_check` belong to reports made from a Scam Analyzer check
(NF-SA-013). If the form or a model could name them, a free-text report could be filed under a
kind of scam, with none of its checks (docs/data-model/collections/radar.md).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.radar import (
    RadarEntityType,
    RadarReportSource,
    RadarViolationType,
    UserEntityType,
    UserViolationType,
)
from app.schemas.radar_report import (
    ExtractedEntity,
    RadarReportRequest,
    ViolationClassification,
)

FORM = {"description": "They charged a fee I was never told about.", "language": "en"}


def test_a_worker_cannot_file_a_report_form_under_a_kind_of_scam() -> None:
    with pytest.raises(ValidationError):
        RadarReportRequest.model_validate(FORM | {"entity_type": "scam_type"})
    RadarReportRequest.model_validate(FORM | {"entity_type": "recruitment_agency"})


def test_the_extraction_step_cannot_answer_with_a_kind_of_scam() -> None:
    answer = {
        "entity_name": "X",
        "entity_name_normalized": "x",
        "corridor_id": None,
        "host_country": None,
        "amount": None,
        "currency": None,
    }
    with pytest.raises(ValidationError):
        ExtractedEntity.model_validate(answer | {"entity_type": "scam_type"})


def test_the_categorising_step_cannot_answer_scam_message() -> None:
    with pytest.raises(ValidationError):
        ViolationClassification.model_validate(
            {"violation_type": "scam_message", "category_confidence": 0.9, "summary": "x"}
        )
    ViolationClassification.model_validate(
        {"violation_type": "hidden_fees", "category_confidence": 0.9, "summary": "x"}
    )


def _values(alias: object) -> set[str]:
    """Every string in a Literal, or a union of Literals."""
    from typing import Literal, get_args, get_origin

    if get_origin(alias) is Literal:
        return {str(v) for v in get_args(alias)}
    return {value for part in get_args(alias) for value in _values(part)}


def test_the_stored_types_do_include_the_scam_ones() -> None:
    assert "scam_type" in _values(RadarEntityType)
    assert "scam_message" in _values(RadarViolationType)
    assert "scam_check" in _values(RadarReportSource)
    assert "scam_type" not in _values(UserEntityType)
    assert "scam_message" not in _values(UserViolationType)
