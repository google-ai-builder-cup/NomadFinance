"""The stats repository and job against the real Firestore emulator (NF-SA-022): the
collection-group query across workers, the field mask, and the documents the job writes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from google.cloud.firestore import Client

from app.repositories.scam_stats_repo import ScamStatsRepository
from app.services.scam.stats import iso_week_of, run_scam_stats

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 4, 9, 30, tzinfo=UTC)
WEEK = iso_week_of(NOW)
SECRET = "Pay 800 SGD to account 0000-0000-1234 today"


def _check(
    created: datetime, *, scam: bool = True, corridor: str = "SG-IN", kind: str | None = "lottery"
) -> dict[str, Any]:
    return {
        "created_at": created,
        "corridor_id": corridor,
        "input_type": "text",
        "verdict": {"is_scam": scam, "scam_type": kind if scam else None, "confidence": 0.9},
        "redacted_text": SECRET,
        "indicators": [{"kind": "url", "value": "sg-careers-visa.example"}],
        "explainer": {"scammer_wants": "your money"},
    }


def _seed(client: Client) -> None:
    inside = WEEK.start + timedelta(days=1)
    client.document("users/worker-1/scam_checks/a").set(_check(inside))
    client.document("users/worker-1/scam_checks/b").set(_check(inside, scam=False))
    client.document("users/worker-2/scam_checks/c").set(_check(inside, corridor="AU-PH"))
    # Before the week, and exactly at its end (the end is not in the week).
    client.document("users/worker-2/scam_checks/d").set(_check(WEEK.start - timedelta(seconds=1)))
    client.document("users/worker-2/scam_checks/e").set(_check(WEEK.end))


def test_the_query_finds_checks_of_every_worker_in_the_week_and_reads_only_counted_fields(
    clean_firestore: Client,
) -> None:
    _seed(clean_firestore)

    found = ScamStatsRepository(clean_firestore).checks_created_between(WEEK.start, WEEK.end)

    assert len(found) == 3
    for check in found:
        assert set(check) <= {"corridor_id", "verdict", "input_type", "reported_at"}
        assert "redacted_text" not in check and "indicators" not in check
        assert "explainer" not in check and "confidence" not in check["verdict"]


async def test_the_job_writes_the_week_and_a_second_run_changes_nothing(
    clean_firestore: Client,
) -> None:
    _seed(clean_firestore)
    repo = ScamStatsRepository(clean_firestore)

    result, complete = await run_scam_stats(repo, NOW)
    first = _read_all(clean_firestore)
    await run_scam_stats(repo, NOW)

    assert complete and result.documents_written == 14
    assert _read_all(clean_firestore) == first
    sg_in = first["scam_stats/SG-IN/weeks/2026-W45"]
    assert (sg_in["checks"], sg_in["scams"], sg_in["benign"]) == (2, 1, 1)
    assert sg_in["by_type"] == {"lottery": 1}
    assert first["scam_stats/AU-PH/weeks/2026-W45"]["checks"] == 1
    assert first["scam_stats/SG-PH/weeks/2026-W45"]["checks"] == 0
    assert first["scam_stats/SG-IN"]["corridor_id"] == "SG-IN"


async def test_nothing_a_worker_wrote_reaches_the_stats(clean_firestore: Client) -> None:
    _seed(clean_firestore)

    await run_scam_stats(ScamStatsRepository(clean_firestore), NOW)

    text = repr(_read_all(clean_firestore))
    for secret in (SECRET, "0000-0000-1234", "sg-careers-visa.example", "worker-1", "worker-2"):
        assert secret not in text


def _read_all(client: Client) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for corridor in client.collection("scam_stats").stream():
        out[f"scam_stats/{corridor.id}"] = corridor.to_dict() or {}
        for week in corridor.reference.collection("weeks").stream():
            out[f"scam_stats/{corridor.id}/weeks/{week.id}"] = week.to_dict() or {}
    return out
