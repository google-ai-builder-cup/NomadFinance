from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import pytest
from google.api_core.exceptions import FailedPrecondition

from app.repositories.radar_repo import SimilarReport
from app.repositories.scam_report_repo import CheckGoneError
from app.schemas.radar import RadarReport
from app.schemas.scam import ScamReportRequest
from app.services.scam.history import CheckNotFoundError
from app.services.scam.indicator_seen import indicator_doc_id
from app.services.scam.report import (
    MAX_DESCRIPTION_CHARS,
    IndicatorsNotInCheckError,
    NotAScamError,
    entity_slug,
)
from tests.fixtures.scam_checks import mock_check, put_check
from tests.fixtures.scam_report import VECTOR, ReportWorld

pytestmark = pytest.mark.anyio

UID = "worker-a"
PHONE_ID, URL_ID = "8c83cb97", "f2c46aad"  # the indicators of the "high" mock check


def _request(**changes: Any) -> ScamReportRequest:
    return ScamReportRequest.model_validate({"indicator_ids": [PHONE_ID, URL_ID]} | changes)


def _world(case: str = "high", **kwargs: Any) -> tuple[ReportWorld, str]:
    world = ReportWorld(**kwargs)
    return world, put_check(world.checks, UID, mock_check(case))


def _stored_report(world: ReportWorld, report_id: str = "r_01") -> RadarReport:
    return RadarReport.model_validate(world.radar.reports[report_id])


# ---------------------------------------------------------------- what is stored


async def test_a_scam_check_becomes_a_scam_report_about_its_kind_of_scam() -> None:
    world, check_id = _world()

    outcome = await world.reporter.report(UID, check_id, _request())

    assert outcome.created is True
    response = outcome.response
    assert (response.report_id, response.already_reported) == ("r_01", False)
    assert response.entity_slug == "scam-illegal-recruitment-fee"
    assert response.entity_name == "Illegal recruitment fee"
    report = _stored_report(world)
    assert (report.entity_type, report.violation_type, report.source) == (
        "scam_type",
        "scam_message",
        "scam_check",
    )
    assert report.entity_slug == "scam-illegal-recruitment-fee"
    assert report.corridor_id == "SG-IN" and report.host_country == "SG"
    # The mock's message is in English although the worker reads Hindi: the report says English.
    assert report.language == "en"
    assert report.cluster_id == "r_01"  # nothing similar: a new incident
    assert report.reporter_hash is None and report.summary is None and report.evidence_paths == []


async def test_the_validation_holds_the_analyzers_real_values_not_invented_ones() -> None:
    world, check_id = _world()
    world.checks.docs[(UID, check_id)]["models"] = {"classifier": "classifier-model-x"}

    await world.reporter.report(UID, check_id, _request())

    validation = _stored_report(world).validation
    assert (validation.spam_score, validation.category_confidence, validation.model) == (
        0.0,
        0.94,
        "classifier-model-x",
    )


async def test_the_scam_map_carries_the_verdict_the_details_and_the_confirmed_indicators() -> None:
    world, check_id = _world()

    await world.reporter.report(UID, check_id, _request())

    scam = _stored_report(world).scam
    assert scam is not None
    assert (scam.scam_type, scam.risk_level, scam.confidence) == (
        "illegal_recruitment_fee",
        "high",
        0.94,
    )
    assert scam.tactics == ["urgency", "scarcity"]
    assert scam.details.payment_requested == "bank transfer"
    assert scam.details.amount_requested is not None and scam.details.amount_requested.amount == 800
    assert (scam.message_language, scam.input_type) == ("en", "text")
    assert [(i.kind, i.value, i.flags, i.imitates) for i in scam.indicators] == [
        ("phone", "6590000001", [], None),
        ("url", "sg-careers-visa.example", ["lookalike"], "mom.gov.sg"),
    ]


async def test_only_the_indicators_the_worker_left_ticked_are_reported_and_counted() -> None:
    world, check_id = _world()

    await world.reporter.report(UID, check_id, _request(indicator_ids=[URL_ID]))

    scam = _stored_report(world).scam
    assert scam is not None and [i.kind for i in scam.indicators] == ["url"]
    assert set(world.indicators.docs) == {
        indicator_doc_id(mock_check().indicators[1]),
    }


async def test_unticking_everything_reports_the_scam_with_no_contact_point() -> None:
    world, check_id = _world()

    outcome = await world.reporter.report(UID, check_id, _request(indicator_ids=[]))

    scam = _stored_report(world).scam
    assert outcome.created and scam is not None and scam.indicators == []
    assert world.indicators.docs == {}


async def test_each_confirmed_indicator_is_counted_once_in_scam_indicators() -> None:
    world, check_id = _world()

    await world.reporter.report(UID, check_id, _request())

    phone = world.indicators.docs[indicator_doc_id(mock_check().indicators[0])]
    assert (phone["kind"], phone["value"]) == ("phone", "6590000001")
    assert (phone["report_count"], phone["incident_count"]) == (1, 1)
    assert phone["scam_type_counts"] == {"illegal_recruitment_fee": 1}
    assert phone["corridors"] == ["SG-IN"] and phone["host_countries"] == ["SG"]
    assert phone["flagged"] is False and phone["hidden"] is False


async def test_the_check_is_marked_reported_with_the_reports_id() -> None:
    world, check_id = _world()

    await world.reporter.report(UID, check_id, _request())

    stored = world.checks.docs[(UID, check_id)]
    assert stored["reported_report_id"] == "r_01" and stored["reported_at"] is not None


# ---------------------------------------------------------------- nothing that identifies


async def test_nothing_that_identifies_the_worker_or_the_check_is_in_the_report() -> None:
    world, check_id = _world()

    await world.reporter.report(UID, check_id, _request())

    document = json.dumps(world.radar.reports["r_01"], default=str)
    for forbidden in (UID, check_id, "reporter", "uid"):
        assert forbidden not in document


async def test_the_text_is_masked_again_whatever_the_worker_typed() -> None:
    world, check_id = _world()
    typed = "Call me on +65 9123 4567 or write to a.b@mail.example, https://bad.example/x"

    await world.reporter.report(UID, check_id, _request(description=typed))

    description = _stored_report(world).description
    assert "[PHONE]" in description and "[EMAIL]" in description and "[URL]" in description
    for secret in ("9123 4567", "a.b@mail.example", "bad.example"):
        assert secret not in description
    assert world.gemini.embedded[0][0] == description  # the confirmed text is what is embedded


async def test_without_a_text_the_masked_message_is_used_and_cut_at_a_thousand_characters() -> None:
    world, check_id = _world()
    world.checks.docs[(UID, check_id)]["redacted_text"] = "word " * 400

    await world.reporter.report(UID, check_id, _request())

    description = _stored_report(world).description
    assert len(description) <= MAX_DESCRIPTION_CHARS and description.startswith("word word")


async def test_the_log_has_counts_and_the_slug_never_text_or_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world, check_id = _world()

    with caplog.at_level(logging.DEBUG):
        await world.reporter.report(UID, check_id, _request())

    assert (
        "scam_reported report_id=r_01 slug=scam-illegal-recruitment-fee indicators=2" in caplog.text
    )
    for value in ("6590000001", "sg-careers-visa", "Congratulations", UID, check_id):
        assert value not in caplog.text


# ---------------------------------------------------------------- the host country


@pytest.mark.parametrize(
    ("profile", "corridor", "expected"),
    [
        ({"host_country": "AU"}, "SG-IN", "AU"),  # the profile wins
        ({}, "SG-IN", "SG"),  # else the corridor's host
        ({"host_country": "XX"}, "AU-PH", "AU"),  # an unknown value is not trusted
        ({}, None, None),  # neither: still reported
    ],
)
async def test_the_host_country_comes_from_the_profile_then_the_corridor(
    profile: dict[str, Any], corridor: str | None, expected: str | None
) -> None:
    world = ReportWorld(profile=profile)
    check_id = put_check(world.checks, UID, mock_check("high", corridor_id=corridor))

    await world.reporter.report(UID, check_id, _request())

    report = _stored_report(world)
    assert report.host_country == expected and report.corridor_id == corridor


async def test_a_message_in_another_language_is_reported_in_the_workers_language() -> None:
    world = ReportWorld()
    check_id = put_check(world.checks, UID, mock_check("high", message_language="other"))

    await world.reporter.report(UID, check_id, _request())

    assert _stored_report(world).language == "hi"  # the worker's own


# ---------------------------------------------------------------- the refusals


async def test_a_message_judged_safe_cannot_be_reported() -> None:
    world, check_id = _world("benign")

    with pytest.raises(NotAScamError):
        await world.reporter.report(UID, check_id, _request(indicator_ids=[]))

    assert world.reports.calls == 0 and world.radar.reports == {}


async def test_an_indicator_the_check_does_not_have_is_refused_before_anything_is_written() -> None:
    world, check_id = _world()

    with pytest.raises(IndicatorsNotInCheckError, match="0badc0de"):
        await world.reporter.report(UID, check_id, _request(indicator_ids=[PHONE_ID, "0badc0de"]))

    assert world.reports.calls == 0 and world.gemini.embedded == []


@pytest.mark.parametrize("check_id", ["unknown", "../escape", "x" * 80, ""])
async def test_a_check_that_is_not_there_is_not_found(check_id: str) -> None:
    world, _ = _world()

    with pytest.raises(CheckNotFoundError):
        await world.reporter.report(UID, check_id, _request())


async def test_another_workers_check_is_not_found_whatever_its_id() -> None:
    world, check_id = _world()

    with pytest.raises(CheckNotFoundError):
        await world.reporter.report("worker-b", check_id, _request())

    assert world.reports.calls == 0


async def test_an_expired_check_is_not_found() -> None:
    world = ReportWorld()
    check_id = put_check(world.checks, UID, mock_check("high"))
    world.checks.docs[(UID, check_id)]["expires_at"] = datetime(2020, 1, 1, tzinfo=UTC)

    with pytest.raises(CheckNotFoundError):
        await world.reporter.report(UID, check_id, _request())


async def test_a_check_that_expires_between_the_read_and_the_write_is_not_found() -> None:
    world, check_id = _world()

    def vanish() -> None:
        world.checks.docs.pop((UID, check_id))

    world.reports.before_commit = vanish

    with pytest.raises(CheckNotFoundError):
        await world.reporter.report(UID, check_id, _request())


# ---------------------------------------------------------------- once only


async def test_a_second_tap_returns_the_first_report_and_writes_and_counts_nothing() -> None:
    world, check_id = _world()
    first = await world.reporter.report(UID, check_id, _request())
    counts = json.dumps(world.indicators.docs, default=str, sort_keys=True)

    second = await world.reporter.report(UID, check_id, _request(description="a different text"))

    assert (second.created, second.response.already_reported) == (False, True)
    assert second.response.report_id == first.response.report_id
    assert second.response.entity_slug == first.response.entity_slug
    assert second.response.created_at == first.response.created_at
    assert world.reports.calls == 1 and len(world.radar.reports) == 1
    assert json.dumps(world.indicators.docs, default=str, sort_keys=True) == counts
    assert len(world.gemini.embedded) == 1, "a repeat must not embed, or write a vector, again"


async def test_when_another_tap_wins_first_this_one_gets_its_report_and_saves_nothing() -> None:
    world, check_id = _world()
    winner_stored = {
        "entity_slug": "scam-illegal-recruitment-fee",
        "entity_name": "Illegal recruitment fee",
        "created_at": mock_check().created_at,
        "cluster_id": "r_win",
    }

    def another_tap_wins() -> None:
        world.radar.reports["r_win"] = winner_stored
        world.checks.docs[(UID, check_id)]["reported_report_id"] = "r_win"

    world.reports.before_commit = another_tap_wins

    outcome = await world.reporter.report(UID, check_id, _request())

    assert (outcome.created, outcome.response.report_id) == (False, "r_win")
    assert outcome.response.already_reported is True
    assert world.radar.embeddings == [] and world.radar.entities == {}
    assert "r_01" not in world.radar.reports


async def test_a_reported_check_whose_report_is_gone_still_answers_with_its_id() -> None:
    world, check_id = _world()
    world.checks.docs[(UID, check_id)]["reported_report_id"] = "r_gone"

    outcome = await world.reporter.report(UID, check_id, _request())

    assert (outcome.response.report_id, outcome.response.already_reported) == ("r_gone", True)
    assert outcome.response.entity_slug == "scam-illegal-recruitment-fee"


# ---------------------------------------------------------------- clustering and the entity


async def test_the_text_is_embedded_and_the_vector_stored_after_the_report() -> None:
    world, check_id = _world()

    await world.reporter.report(UID, check_id, _request())

    assert world.gemini.embedded[0][1] == "radar.embed"
    stored = world.radar.embeddings
    assert len(stored) == 1 and stored[0]["length"] == len(VECTOR)
    assert stored[0]["entity_type"] == "scam_type"
    assert stored[0]["entity_slug"] == "scam-illegal-recruitment-fee"
    assert stored[0]["corridor_id"] == "SG-IN"


async def test_a_report_like_an_earlier_one_joins_its_cluster_and_is_no_new_incident() -> None:
    world, check_id = _world()
    world.radar.reports["r_early"] = {"cluster_id": "r_early"}
    world.radar.neighbours = [
        SimilarReport("r_early", "scam-illegal-recruitment-fee", distance=0.05)
    ]

    await world.reporter.report(UID, check_id, _request())

    assert _stored_report(world, "r_01").cluster_id == "r_early"
    phone = world.indicators.docs[indicator_doc_id(mock_check().indicators[0])]
    assert (phone["report_count"], phone["incident_count"]) == (1, 0)
    entity = world.radar.entities["scam-illegal-recruitment-fee"]
    assert (entity["report_count"], entity["incident_count"]) == (1, 0)


async def test_a_similar_report_about_another_kind_of_scam_does_not_join() -> None:
    world, check_id = _world()
    world.radar.neighbours = [SimilarReport("r_other", "scam-lottery", distance=0.01)]

    await world.reporter.report(UID, check_id, _request())

    assert _stored_report(world).cluster_id == "r_01"


async def test_the_entitys_profile_counts_the_report() -> None:
    world, check_id = _world()

    await world.reporter.report(UID, check_id, _request())

    entity = world.radar.entities["scam-illegal-recruitment-fee"]
    assert entity["entity_type"] == "scam_type"
    assert entity["name"] == "Illegal recruitment fee"
    assert (entity["report_count"], entity["incident_count"]) == (1, 1)
    assert entity["corridors"] == ["SG-IN"] and entity["host_countries"] == ["SG"]
    assert entity["violation_counts"] == {"scam_message": 1} and entity["flagged"] is False


async def test_a_failed_embedding_still_files_the_report_as_its_own_cluster() -> None:
    world, check_id = _world(embed_fails=True)

    outcome = await world.reporter.report(UID, check_id, _request())

    assert outcome.created is True
    assert _stored_report(world).cluster_id == "r_01"
    assert world.radar.embeddings == []


async def test_a_vector_that_cannot_be_stored_does_not_lose_the_report() -> None:
    world, check_id = _world()
    world.radar.embedding_store_down = True

    outcome = await world.reporter.report(UID, check_id, _request())

    assert outcome.created is True and "r_01" in world.radar.reports
    assert "scam-illegal-recruitment-fee" in world.radar.entities


async def test_a_search_that_cannot_run_still_files_the_report() -> None:
    world, check_id = _world()

    def broken_index(*args: Any) -> list[Any]:
        raise FailedPrecondition("the query needs a vector index")  # type: ignore[no-untyped-call]

    world.radar.find_similar = broken_index  # type: ignore[method-assign,assignment]

    outcome = await world.reporter.report(UID, check_id, _request())

    assert outcome.created is True and _stored_report(world).cluster_id == "r_01"


async def test_the_taxonomy_label_is_spelled_out_when_the_taxonomy_cannot_be_read() -> None:
    world, check_id = _world()

    class Down:
        def get_taxonomy(self) -> Any:
            raise FailedPrecondition("down")  # type: ignore[no-untyped-call]

    world.reporter._taxonomy = Down()  # type: ignore[assignment]

    outcome = await world.reporter.report(UID, check_id, _request())

    assert outcome.response.entity_name == "Illegal recruitment fee"


def test_the_entity_slug_is_scam_and_the_type_with_hyphens() -> None:
    assert entity_slug("illegal_recruitment_fee") == "scam-illegal-recruitment-fee"
    assert entity_slug("other_scam") == "scam-other-scam"


async def test_the_commit_error_for_a_vanished_check_is_the_reporters_not_found() -> None:
    assert issubclass(CheckGoneError, LookupError)
