"""The report transaction against the real Firestore emulator (NF-SA-013).

The service tests use an in-memory stand-in with the same rules; this is the proof that the rules
hold in Firestore itself: one commit writes the Radar report, every counter and the check's
`reported_report_id`, a check is reported once even when two taps race, and what the repository
writes is what the NF-SA-012 reader reads.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import pytest
from google.api_core.exceptions import Aborted
from google.cloud.firestore import Client

from app.repositories import scam_report_repo
from app.repositories.scam_indicator_repo import ScamIndicatorRepository
from app.repositories.scam_report_repo import (
    CheckGoneError,
    IndicatorUpdate,
    ScamReportRepository,
)
from app.schemas.radar import RadarReport, RadarValidation
from app.schemas.radar_scam import RadarScamReport, ReportedIndicator
from app.schemas.scam import ScamDetails, ScamIndicator
from app.services.scam.indicator_seen import attach_seen, indicator_doc_id
from tests.fixtures.scam_checks import NOW

pytestmark = pytest.mark.anyio

UID = "worker-1"
SCAM_TYPE = "illegal_recruitment_fee"
PHONE = ScamIndicator(
    id="8c83cb97", kind="phone", value="6590000001", flags=[], imitates=None, seen=None
)
SENDER = ScamIndicator(
    id="aaaaaaaa", kind="sender", value="LoanPH", flags=[], imitates=None, seen=None
)


def _update(indicator: ScamIndicator) -> IndicatorUpdate:
    return IndicatorUpdate(
        indicator_doc_id(indicator), indicator.kind, indicator.value, [], indicator.imitates
    )


def _report(report_id: str, cluster_id: str | None = None) -> RadarReport:
    return RadarReport(
        entity_type="scam_type",
        entity_name="Illegal recruitment fee",
        entity_slug="scam-illegal-recruitment-fee",
        violation_type="scam_message",
        corridor_id="SG-IN",
        host_country="SG",
        description="Pay the fee to [ACCOUNT] today",
        language="en",
        cluster_id=cluster_id or report_id,
        source="scam_check",
        validation=RadarValidation(spam_score=0.0, category_confidence=0.9, model="m"),
        scam=RadarScamReport(
            scam_type=SCAM_TYPE,
            tactics=["urgency"],
            risk_level="high",
            confidence=0.9,
            trigger_phrases=["fee"],
            details=ScamDetails(),
            indicators=[ReportedIndicator(kind="phone", value="6590000001", flags=[])],
            input_type="text",
        ),
        created_at=NOW,
    )


def _check(client: Client, check_id: str, uid: str = UID, **fields: Any) -> None:
    client.document(f"users/{uid}/scam_checks/{check_id}").set(
        {"created_at": NOW, "expires_at": NOW, **fields}
    )


def _commit(
    client: Client,
    check_id: str,
    report_id: str,
    updates: list[IndicatorUpdate],
    *,
    uid: str = UID,
    cluster_id: str | None = None,
) -> Any:
    return ScamReportRepository(client).commit_report(
        uid=uid,
        check_id=check_id,
        report_id=report_id,
        report=_report(report_id, cluster_id),
        updates=updates,
        scam_type=SCAM_TYPE,
        now=NOW,
    )


def _indicator(client: Client, indicator: ScamIndicator) -> dict[str, Any] | None:
    snapshot = client.document(f"scam_indicators/{indicator_doc_id(indicator)}").get()
    return snapshot.to_dict() if snapshot.exists else None


def test_one_commit_writes_the_report_the_counters_and_the_checks_mark(
    clean_firestore: Client,
) -> None:
    client = clean_firestore
    _check(client, "c1")

    result = _commit(client, "c1", "r1", [_update(PHONE)])

    assert (result.report_id, result.created) == ("r1", True)
    report = client.document("radar_reports/r1").get().to_dict()
    assert report is not None
    assert report["entity_slug"] == "scam-illegal-recruitment-fee" and report["cluster_id"] == "r1"
    assert report["scam"]["indicators"] == [{"kind": "phone", "value": "6590000001", "flags": []}]
    assert "reporter_hash" not in report
    counter = _indicator(client, PHONE)
    assert counter is not None
    assert (counter["report_count"], counter["incident_count"], counter["flagged"]) == (1, 1, False)
    assert counter["corridors"] == ["SG-IN"] and counter["hidden"] is False
    check = client.document(f"users/{UID}/scam_checks/c1").get().to_dict()
    assert check is not None and check["reported_report_id"] == "r1"
    assert isinstance(check["reported_at"], datetime) and check["reported_at"].tzinfo is not None


def test_a_check_already_reported_writes_and_counts_nothing_more(clean_firestore: Client) -> None:
    client = clean_firestore
    _check(client, "c1")
    _commit(client, "c1", "r1", [_update(PHONE)])

    again = _commit(client, "c1", "r2", [_update(PHONE)])

    assert (again.report_id, again.created) == ("r1", False)
    assert not client.document("radar_reports/r2").get().exists
    counter = _indicator(client, PHONE)
    assert counter is not None and counter["report_count"] == 1


def test_two_taps_at_once_never_report_the_check_twice_or_count_it_twice(
    clean_firestore: Client,
) -> None:
    """Safety, not liveness: two taps that start together hold the check between them and the
    client may give up on one (the emulator's "Transaction lock timeout"), so that tap may fail.
    What must never happen is a second report or a second count; and the worker's retry, when
    the other tap is over, must end with exactly one report."""
    client = clean_firestore
    _check(client, "c1")
    start = threading.Barrier(2)

    def tap(report_id: str) -> Any:
        start.wait()
        try:
            return _commit(client, "c1", report_id, [_update(PHONE)])
        except (ValueError, Aborted) as exc:
            # Two ways the emulator gives up on a tap that waits for the other one's lock: the
            # client's "Failed to commit transaction in 5 attempts" (ValueError, when the commit is
            # refused), and a raw Aborted "Transaction lock timeout" (when the read inside the
            # transaction is). The client retries only the first, so the second reaches us as it is.
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(tap, ["r_a", "r_b"]))

    created = [r for r in results if not isinstance(r, Exception) and r.created]
    assert len(created) <= 1, "two taps both reported the check"
    assert len(list(client.collection("radar_reports").stream())) <= 1
    counter = _indicator(client, PHONE)
    assert counter is None or counter["report_count"] == 1

    # The worker taps again, alone: the check ends up reported once, whatever happened above.
    retry = _commit(client, "c1", "r_retry", [_update(PHONE)])
    reports = [doc.id for doc in client.collection("radar_reports").stream()]
    assert len(reports) == 1 and retry.report_id == reports[0]
    final = _indicator(client, PHONE)
    assert final is not None and final["report_count"] == 1
    check = client.document(f"users/{UID}/scam_checks/c1").get().to_dict()
    assert check is not None and check["reported_report_id"] == reports[0]


def test_a_second_tap_a_moment_later_is_told_the_first_report(clean_firestore: Client) -> None:
    client = clean_firestore
    _check(client, "c1")
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(_commit, client, "c1", "r_a", [_update(PHONE)])
        first.result()
    second = _commit(client, "c1", "r_b", [_update(PHONE)])

    assert (second.report_id, second.created) == ("r_a", False)


def test_the_same_indicator_in_two_workers_checks_adds_up_and_is_flagged_at_two_incidents(
    clean_firestore: Client,
) -> None:
    client = clean_firestore
    _check(client, "c1")
    _check(client, "c2", uid="worker-2")

    _commit(client, "c1", "r1", [_update(PHONE)])
    first = _indicator(client, PHONE)
    _commit(client, "c2", "r2", [_update(PHONE)], uid="worker-2")
    second = _indicator(client, PHONE)

    assert first is not None and second is not None
    assert (first["incident_count"], first["flagged"]) == (1, False)
    assert (second["report_count"], second["incident_count"], second["flagged"]) == (2, 2, True)
    assert second["scam_type_counts"] == {SCAM_TYPE: 2}
    assert second["first_reported_at"] == first["first_reported_at"]


def test_a_report_that_joined_a_cluster_is_no_new_incident(clean_firestore: Client) -> None:
    client = clean_firestore
    _check(client, "c1")

    _commit(client, "c1", "r2", [_update(PHONE)], cluster_id="r_earlier")

    counter = _indicator(client, PHONE)
    assert counter is not None
    assert (counter["report_count"], counter["incident_count"], counter["flagged"]) == (1, 0, False)


def test_a_hidden_indicator_stays_hidden_and_is_still_counted(clean_firestore: Client) -> None:
    client = clean_firestore
    _check(client, "c1")
    client.document(f"scam_indicators/{indicator_doc_id(PHONE)}").set(
        {"kind": "phone", "value": "6590000001", "hidden": True, "report_count": 4}
    )

    _commit(client, "c1", "r1", [_update(PHONE)])

    counter = _indicator(client, PHONE)
    assert counter is not None and counter["hidden"] is True and counter["report_count"] == 5


def test_a_check_that_is_gone_raises_and_writes_nothing(clean_firestore: Client) -> None:
    with pytest.raises(CheckGoneError):
        _commit(clean_firestore, "missing", "r1", [_update(PHONE)])

    assert not clean_firestore.document("radar_reports/r1").get().exists
    assert _indicator(clean_firestore, PHONE) is None


def test_a_failure_part_way_writes_nothing_at_all(
    clean_firestore: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = clean_firestore
    _check(client, "c1")
    real = scam_report_repo.merge_indicator
    calls = {"n": 0}

    def fails_on_the_second(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("the second counter could not be built")
        return real(*args, **kwargs)

    monkeypatch.setattr(scam_report_repo, "merge_indicator", fails_on_the_second)

    with pytest.raises(RuntimeError):
        _commit(client, "c1", "r1", [_update(PHONE), _update(SENDER)])

    assert not client.document("radar_reports/r1").get().exists
    assert _indicator(client, PHONE) is None and _indicator(client, SENDER) is None
    check = client.document(f"users/{UID}/scam_checks/c1").get().to_dict()
    assert check is not None and "reported_report_id" not in check


async def test_what_is_written_is_what_the_checks_reader_reads(clean_firestore: Client) -> None:
    client = clean_firestore
    _check(client, "c1")
    _commit(client, "c1", "r1", [_update(PHONE), _update(SENDER)])

    # A sender is keyed on its lowercase form, so "LoanPH" and "loanph" are one (scam.md).
    shown = await attach_seen(
        [PHONE, SENDER.model_copy(update={"value": "loanph"})], ScamIndicatorRepository(client)
    )

    assert [(i.kind, i.seen.reports if i.seen else None) for i in shown] == [
        ("phone", 1),
        ("sender", 1),
    ]
    assert shown[0].seen is not None and shown[0].seen.last_reported_at == NOW


def test_the_report_is_stored_with_real_timestamps(clean_firestore: Client) -> None:
    client = clean_firestore
    _check(client, "c1")

    _commit(client, "c1", "r1", [_update(PHONE)])

    report = client.document("radar_reports/r1").get().to_dict()
    counter = _indicator(client, PHONE)
    assert report is not None and counter is not None
    assert report["created_at"] == NOW
    assert counter["expires_at"] == datetime(2027, 11, 5, 9, 0, tzinfo=UTC)
