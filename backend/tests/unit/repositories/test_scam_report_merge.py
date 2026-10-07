from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.repositories.scam_report_repo import (
    FLAG_AT_INCIDENTS,
    INDICATOR_TTL,
    IndicatorUpdate,
    merge_indicator,
)

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
UPDATE = IndicatorUpdate("a" * 32, "phone", "6590000001", [], None)


def _merge(existing: dict[str, Any] | None = None, **changes: Any) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "scam_type": "illegal_recruitment_fee",
        "corridor_id": "SG-IN",
        "host_country": "SG",
        "new_incident": True,
        "now": NOW,
    }
    update = changes.pop("update", UPDATE)
    return merge_indicator(existing, update, **(arguments | changes))


def test_the_first_report_creates_the_document_as_the_data_model_describes() -> None:
    doc = _merge()

    assert doc == {
        "kind": "phone",
        "value": "6590000001",
        "flags": [],
        "report_count": 1,
        "incident_count": 1,
        "scam_type_counts": {"illegal_recruitment_fee": 1},
        "corridors": ["SG-IN"],
        "host_countries": ["SG"],
        "first_reported_at": NOW,
        "last_reported_at": NOW,
        "flagged": False,
        "hidden": False,
        "expires_at": NOW + INDICATOR_TTL,
        "updated_at": NOW,
        "schema_version": 1,
    }
    assert INDICATOR_TTL == timedelta(days=365)


def test_every_report_counts_but_only_a_new_cluster_is_a_new_incident() -> None:
    first = _merge()
    joined = _merge(first, new_incident=False)

    assert (joined["report_count"], joined["incident_count"]) == (2, 1)
    assert joined["flagged"] is False  # one repeated report is not a pattern


def test_the_indicator_is_flagged_at_two_incidents_and_stays_flagged() -> None:
    doc = _merge()
    later = _merge(doc, now=NOW + timedelta(days=1))
    assert FLAG_AT_INCIDENTS == 2
    assert (later["incident_count"], later["flagged"]) == (2, True)

    again = _merge(later, new_incident=False, now=NOW + timedelta(days=2))
    assert again["flagged"] is True and again["report_count"] == 3


def test_a_first_report_that_joined_an_older_cluster_starts_at_zero_incidents() -> None:
    doc = _merge(new_incident=False)

    assert (doc["report_count"], doc["incident_count"], doc["flagged"]) == (1, 0, False)


def test_the_counts_by_type_corridors_and_countries_add_up_and_stay_sorted() -> None:
    doc = _merge()
    doc = _merge(doc, scam_type="fake_job_offer", corridor_id="AU-IN", host_country="AU")
    doc = _merge(doc, corridor_id="SG-IN", host_country="SG")

    assert doc["scam_type_counts"] == {"illegal_recruitment_fee": 2, "fake_job_offer": 1}
    assert doc["corridors"] == ["AU-IN", "SG-IN"] and doc["host_countries"] == ["AU", "SG"]


def test_a_report_without_a_corridor_or_country_adds_none() -> None:
    doc = _merge(corridor_id=None, host_country=None)

    assert "corridors" not in doc and "host_countries" not in doc


def test_the_dates_first_is_kept_last_moves_and_expiry_follows_the_last_report() -> None:
    doc = _merge()
    later = NOW + timedelta(days=30)

    doc = _merge(doc, now=later)

    assert doc["first_reported_at"] == NOW and doc["last_reported_at"] == later
    assert doc["expires_at"] == later + INDICATOR_TTL and doc["updated_at"] == later


def test_a_hidden_indicator_stays_hidden_and_is_still_counted() -> None:
    doc = _merge({"hidden": True, "report_count": 4, "incident_count": 3})

    assert doc["hidden"] is True and doc["report_count"] == 5 and doc["incident_count"] == 4


def test_flags_are_gathered_without_repeats_and_the_first_imitation_is_kept() -> None:
    url = IndicatorUpdate("b" * 32, "url", "mom-gov-sg.com", ["lookalike"], "mom.gov.sg")
    doc = _merge(update=url)
    doc = _merge(
        doc,
        update=IndicatorUpdate(
            "b" * 32, "url", "mom-gov-sg.com", ["lookalike", "shortener"], "x.sg"
        ),
    )

    assert doc["flags"] == ["lookalike", "shortener"] and doc["imitates"] == "mom.gov.sg"


@pytest.mark.parametrize("existing", [None, {}])
def test_an_empty_or_missing_document_is_a_new_one(existing: dict[str, Any] | None) -> None:
    assert _merge(existing)["report_count"] == 1
