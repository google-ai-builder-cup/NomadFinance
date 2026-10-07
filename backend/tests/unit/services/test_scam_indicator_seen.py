"""How often an indicator was reported, read when a check is shown (NF-SA-012)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.repositories.scam_indicator_repo import ScamIndicatorRepository
from app.schemas.scam import ScamIndicator
from app.services.scam.indicator_seen import attach_seen, indicator_doc_id
from app.services.scam.indicators import make_indicator
from tests.fixtures.scam_checks import FakeIndicatorRepo

pytestmark = pytest.mark.anyio

WHEN = datetime(2026, 11, 20, 7, 5, tzinfo=UTC)
PHONE = make_indicator("phone", "6590000001")
URL = make_indicator("url", "sg-careers-visa.example", ["lookalike"], imitates="mom.gov.sg")


def _repo(docs: dict[str, dict[str, Any]]) -> ScamIndicatorRepository:
    return cast(ScamIndicatorRepository, FakeIndicatorRepo(docs))


def _doc(**changes: Any) -> dict[str, Any]:
    return {
        "report_count": 5,
        "incident_count": 3,
        "last_reported_at": WHEN,
        "flagged": True,
        "hidden": False,
    } | changes


def test_the_document_id_is_the_first_32_characters_of_the_key_whose_first_8_are_the_id() -> None:
    doc_id = indicator_doc_id(PHONE)

    assert len(doc_id) == 32 and doc_id.startswith(PHONE.id)


def test_the_id_matches_the_data_models_own_example() -> None:
    # scam.md: the number 6590000001 is `scam_indicators/8c83cb97151fd86a6c73ff5fa296244e`.
    assert indicator_doc_id(PHONE) == "8c83cb97151fd86a6c73ff5fa296244e"


async def test_a_reported_indicator_shows_its_count() -> None:
    [shown, other] = await attach_seen([PHONE, URL], _repo({indicator_doc_id(PHONE): _doc()}))

    assert shown.seen is not None
    assert (shown.seen.reports, shown.seen.incidents, shown.seen.flagged) == (5, 3, True)
    assert shown.seen.last_reported_at == WHEN
    assert other.seen is None and other.imitates == "mom.gov.sg"


async def test_a_hidden_indicator_is_treated_as_never_reported() -> None:
    [shown] = await attach_seen([PHONE], _repo({indicator_doc_id(PHONE): _doc(hidden=True)}))

    assert shown.seen is None


@pytest.mark.parametrize(
    "doc",
    [
        {},
        {"report_count": 0, "last_reported_at": WHEN},
        {"report_count": "5", "last_reported_at": WHEN},
        {"report_count": 5},
    ],
    ids=["empty", "zero reports", "text count", "no date"],
)
async def test_a_document_that_does_not_say_how_often_gives_no_count(doc: dict[str, Any]) -> None:
    [shown] = await attach_seen([PHONE], _repo({indicator_doc_id(PHONE): doc}))

    assert shown.seen is None


async def test_a_count_with_no_incidents_recorded_counts_as_one_incident() -> None:
    [shown] = await attach_seen(
        [PHONE], _repo({indicator_doc_id(PHONE): _doc(incident_count=None, flagged=None)})
    )

    assert shown.seen is not None
    assert (shown.seen.incidents, shown.seen.flagged) == (1, False)


async def test_no_indicators_means_no_lookup() -> None:
    repo = FakeIndicatorRepo()
    repo.down = True  # would fail if it were asked

    assert await attach_seen([], cast(ScamIndicatorRepository, repo)) == []


async def test_a_failed_lookup_leaves_the_indicators_as_they_were() -> None:
    repo = FakeIndicatorRepo({indicator_doc_id(PHONE): _doc()})
    repo.down = True

    result = await attach_seen([PHONE], cast(ScamIndicatorRepository, repo))

    assert result == [PHONE]


def test_the_indicators_the_fake_makes_are_the_contracts_model() -> None:
    assert isinstance(PHONE, ScamIndicator)
