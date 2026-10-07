from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

from google.cloud.firestore import Client, Transaction, transactional

from app.repositories.base import get_firestore_client
from app.schemas.radar import RadarReport

INDICATORS_COLLECTION = "scam_indicators"
# A phone number is reissued to someone else after a while: an indicator nobody has reported for
# a year stops being flagged (scam.md, `scam_indicators.expires_at`).
INDICATOR_TTL = timedelta(days=365)
FLAG_AT_INCIDENTS = 2  # the same rule as `radar_entities`: a pattern, not one unverified report
SCHEMA_VERSION = 1


class CheckGoneError(LookupError):
    """The check vanished (it expired) between the worker's tap and the write."""


@dataclass(frozen=True)
class IndicatorUpdate:
    """One confirmed indicator, to be counted in `scam_indicators/{doc_id}`."""

    doc_id: str
    kind: str
    value: str
    flags: list[str]
    imitates: str | None


@dataclass(frozen=True)
class CommitResult:
    """`created` is False when the check had been reported already: nothing was written."""

    report_id: str
    created: bool


def merge_indicator(
    existing: dict[str, Any] | None,
    update: IndicatorUpdate,
    *,
    scam_type: str,
    corridor_id: str | None,
    host_country: str | None,
    new_incident: bool,
    now: datetime,
) -> dict[str, Any]:
    """The `scam_indicators` document after one more report names this indicator (scam.md).

    `report_count` counts every report. `incident_count` counts only reports that began a new
    similarity cluster, so a worker repeating one message does not make an indicator look
    widespread. A `hidden` document stays hidden and is still counted: an operator took it out
    of the lookups, not out of the record.
    """
    old = existing or {}
    incident_count = int(old.get("incident_count", 0)) + (1 if new_incident else 0)
    type_counts = dict(old.get("scam_type_counts", {}))
    type_counts[scam_type] = int(type_counts.get(scam_type, 0)) + 1
    corridors = sorted({*old.get("corridors", []), *([corridor_id] if corridor_id else [])})
    countries = sorted({*old.get("host_countries", []), *([host_country] if host_country else [])})
    flags = list(dict.fromkeys([*old.get("flags", []), *update.flags]))
    document: dict[str, Any] = {
        "kind": update.kind,
        "value": update.value,
        "flags": flags,
        "report_count": int(old.get("report_count", 0)) + 1,
        "incident_count": incident_count,
        "scam_type_counts": type_counts,
        "first_reported_at": old.get("first_reported_at", now),
        "last_reported_at": now,
        "flagged": incident_count >= FLAG_AT_INCIDENTS,
        "hidden": bool(old.get("hidden", False)),
        "expires_at": now + INDICATOR_TTL,
        "updated_at": now,
        "schema_version": SCHEMA_VERSION,
    }
    imitates = old.get("imitates") or update.imitates
    for name, value in (
        ("imitates", imitates),
        ("corridors", corridors),
        ("host_countries", countries),
    ):
        if value:
            document[name] = value
    return document


class ScamReportRepository:
    """Writes a scam report: the Radar report, the counters of each confirmed indicator and the
    check's `reported_report_id`, in one transaction (NF-SA-013; radar.md, scam.md).

    One transaction so a check is reported once and the counters cannot drift from the reports:
    the check is read inside it, and a second tap on the same check, or two taps at once, find
    `reported_report_id` already set and write nothing.
    """

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    def commit_report(
        self,
        *,
        uid: str,
        check_id: str,
        report_id: str,
        report: RadarReport,
        updates: list[IndicatorUpdate],
        scam_type: str,
        now: datetime,
    ) -> CommitResult:
        """Write the report unless the check was reported already.

        Raises:
            CheckGoneError: The check document no longer exists.
        """
        client = self._client
        check_ref = client.collection("users").document(uid).collection("scam_checks")
        check_ref = check_ref.document(check_id)
        report_ref = client.collection("radar_reports").document(report_id)
        indicator_refs = {
            u.doc_id: client.collection(INDICATORS_COLLECTION).document(u.doc_id) for u in updates
        }
        # A report that began its own cluster is a new incident (radar.md, `cluster_id`).
        new_incident = report.cluster_id == report_id

        @transactional
        def run(transaction: Transaction) -> CommitResult:
            # Every read first: Firestore refuses a read after a write in a transaction.
            check = check_ref.get(transaction=transaction)
            if not check.exists:
                raise CheckGoneError(check_id)
            already = (check.to_dict() or {}).get("reported_report_id")
            if already:
                return CommitResult(str(already), created=False)
            stored = {
                snapshot.id: snapshot.to_dict() or {}
                for snapshot in client.get_all(
                    list(indicator_refs.values()), transaction=transaction
                )
                if snapshot.exists
            }
            transaction.set(report_ref, report.model_dump(exclude_none=True))
            for update in updates:
                merged = merge_indicator(
                    stored.get(update.doc_id),
                    update,
                    scam_type=scam_type,
                    corridor_id=report.corridor_id,
                    host_country=report.host_country,
                    new_incident=new_incident,
                    now=now,
                )
                transaction.set(indicator_refs[update.doc_id], merged)
            transaction.update(check_ref, {"reported_report_id": report_id, "reported_at": now})
            return CommitResult(report_id, created=True)

        try:
            result: CommitResult = run(client.transaction())
        except ValueError:
            # The client's "Failed to commit transaction in N attempts": two taps at once held
            # the check between them. If the other tap has reported it by now, its report is
            # the answer; otherwise the failure is raised as it was and the worker's retry,
            # which is then alone, succeeds. Either way the check is reported at most once.
            snapshot = check_ref.get()
            already = (
                (snapshot.to_dict() or {}).get("reported_report_id") if snapshot.exists else None
            )
            if not already:
                raise
            return CommitResult(str(already), created=False)
        return result


@lru_cache
def get_scam_report_repository() -> ScamReportRepository:
    return ScamReportRepository(get_firestore_client())
