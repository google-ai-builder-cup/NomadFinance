"""The adoption numbers of the pitch (NF-HR-015): what they count, what they hide, and that a
second run over the same data gives the same figures."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import pytest
from google.cloud.firestore import Client

from src.metrics import adoption_snapshot
from src.metrics.adoption_snapshot import MIN_CELL, snapshot, to_markdown
from tests.fake_firestore import FakeClient

T0 = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def session(
    status: str,
    *,
    minutes: float | None = None,
    turns: int = 3,
    language: str = "en",
    created: datetime = T0,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "status": status,
        "language": language,
        "turn_count": turns,
        "created_at": created,
    }
    if status == "completed" and minutes is not None:
        data["completed_at"] = created + timedelta(minutes=minutes)
    return data


def check(
    *, scam: bool, risk: str = "high", kind: str = "lottery", corridor: str = "SG-IN", **extra: Any
) -> dict[str, Any]:
    return {
        "verdict": {"is_scam": scam, "scam_type": kind if scam else None, "risk_level": risk},
        "corridor_id": corridor,
        "input_type": "text",
        "check_count": 1,
        "created_at": T0,
    } | extra


def world() -> FakeClient:
    """Four real workers and a demo one, with what the Coach and the analyzer leave behind."""
    client = FakeClient()
    # w1: a plan in 9 minutes, then a check-in. w2: a plan in 15. w3: gave up. w4: still going.
    client.put("users/w1/coach_sessions/s1", session("completed", minutes=9, turns=12))
    client.put(
        "users/w2/coach_sessions/s1", session("completed", minutes=15, turns=14, language="tl")
    )
    client.put("users/w3/coach_sessions/s1", session("abandoned", language="tl"))
    client.put("users/w4/coach_sessions/s1", session("active", language="tl"))
    # The same worker started twice: two interviews, one worker.
    client.put("users/w3/coach_sessions/s2", session("completed", minutes=11, turns=13))
    client.put(
        "users/w1/coach_plans/p1",
        {
            "score": {"band": "getting_ready"},
            "corridor_id": "SG-IN",
            "created_at": T0,
            "checkins": {"d30": {"answered_at": T0 + timedelta(days=30)}, "d60": {"due_on": "x"}},
        },
    )
    client.put("users/w2/coach_plans/p1", {"score": {"band": "needs_work"}, "created_at": T0})
    client.put("users/w3/coach_plans/p1", {"score": {"band": "getting_ready"}, "created_at": T0})
    for n in range(6):  # six checks that were scams, one cell over the limit
        client.put(f"users/w{n % 4 + 1}/scam_checks/c{n}", check(scam=True, risk="high"))
    client.put("users/w1/scam_checks/c6", check(scam=True, risk="medium", kind="loan_app_trap"))
    client.put("users/w2/scam_checks/c7", check(scam=False, risk="low"))
    client.put(
        "users/w1/scam_checks/c8",
        check(scam=True, kind="lottery", reported_at=T0, check_count=3, corridor="AU-PH"),
    )
    # A demo worker, and a document that is not under a worker at all.
    client.put("users/uid_priya_demo/coach_sessions/s1", session("completed", minutes=5))
    client.put("users/uid_priya_demo/scam_checks/c1", check(scam=True))
    client.put("scam_checks/loose", check(scam=True))
    return client


def run(client: FakeClient, **kwargs: Any) -> dict[str, Any]:
    return snapshot(cast(Client, client), **kwargs)


def test_the_coach_numbers_count_interviews_and_workers_separately() -> None:
    coach = run(world())["coach"]

    assert coach["interviews_started"] == 5
    assert coach["interviews_completed"] == 3
    assert coach["interviews_abandoned"] == 1 and coach["interviews_open"] == 1
    assert coach["completion_rate"] == 0.6
    # Of the interviews that ended: 3 plans against 1 given up.
    assert coach["completion_rate_of_finished"] == 0.75
    # w1, w2, w3 reached a plan of 4 who started: w3 abandoned one and completed another.
    assert coach["workers_started"] == 4 and coach["workers_with_a_plan"] == 3
    assert coach["worker_completion_rate"] == 0.75


def test_the_time_and_turns_are_the_medians_of_the_finished_interviews() -> None:
    coach = run(world())["coach"]

    assert coach["median_minutes_to_a_plan"] == 11.0
    assert coach["median_turns_to_a_plan"] == 13


def test_plans_and_answered_check_ins_are_counted_from_the_plans() -> None:
    coach = run(world())["coach"]

    assert coach["plans"] == 3
    assert coach["checkins_answered"] == {"d30": 1, "d60": 0, "d90": 0}


def test_the_scam_numbers_say_how_many_were_caught_and_warned_about() -> None:
    scam = run(world())["scam"]

    assert scam["messages_checked"] == 9
    assert scam["scams_caught"] == 8
    assert scam["scams_caught_high_risk"] == 7
    assert scam["scams_reported_to_radar"] == 1
    assert scam["share_that_were_scams"] == round(8 / 9, 3)
    # A repeat is not a new message, but it was asked again.
    assert scam["times_asked_including_repeats"] == 9 + 2
    assert scam["workers_who_checked"] == 4


def test_a_cell_under_the_limit_is_hidden_and_a_total_is_not() -> None:
    result = run(world())

    caught = result["scam"]["caught_by_type"]
    assert caught == {"lottery": 7, "loan_app_trap": f"<{MIN_CELL}"}
    assert result["scam"]["scams_caught"] == 8
    assert all(
        isinstance(n, str) or n >= MIN_CELL
        for table in (result["coach"]["plans_by_band"], result["coach"]["interviews_by_language"])
        for n in table.values()
    )


def test_the_demo_workers_and_loose_documents_are_left_out() -> None:
    client = world()

    without = run(client)
    with_demo = run(client, include_demo=True)

    assert without["documents_read"]["scam_checks"] == 9
    assert with_demo["documents_read"]["scam_checks"] == 10
    assert with_demo["coach"]["interviews_started"] == without["coach"]["interviews_started"] + 1


def test_since_leaves_out_what_was_created_before() -> None:
    client = world()
    client.put("users/w1/scam_checks/old", check(scam=True, created_at=T0 - timedelta(days=20)))

    everything = run(client)
    recent = run(client, since=date(2026, 10, 1))

    assert everything["scam"]["messages_checked"] == recent["scam"]["messages_checked"] + 1


def test_a_second_run_gives_the_same_figures() -> None:
    client = world()

    first, second = run(client), run(client)

    for result in (first, second):
        result.pop("generated_at")
    assert first == second


def test_nothing_that_identifies_a_worker_reaches_the_output() -> None:
    client = world()
    client.put(
        "users/w1/scam_checks/c9", check(scam=True, redacted_text="Pay 800 SGD to 0000-1234")
    )

    text = json.dumps(run(client)) + to_markdown(run(client))

    for forbidden in ("w1", "w2", "w3", "w4", "uid_", "Pay 800", "0000-1234", "users/"):
        assert forbidden not in text


def test_an_empty_project_gives_zeros_and_no_division() -> None:
    result = run(FakeClient())

    assert result["coach"]["interviews_started"] == 0
    assert result["coach"]["completion_rate"] is None
    assert result["scam"]["share_that_were_scams"] is None
    assert "n/a" in to_markdown(result)


def test_the_markdown_headlines_the_two_numbers_of_the_pitch() -> None:
    table = to_markdown(run(world()))

    assert "**Coach completion rate** | **60%**" in table
    assert "**Scams caught** | **8**" in table


def test_the_command_writes_the_json_and_prints_the_table(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(adoption_snapshot, "get_firestore_client", lambda: world())
    target = tmp_path / "snapshot.json"

    code = adoption_snapshot.main(["--json", str(target), "--since", "2026-10-01"])

    assert code == 0
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["coach"]["interviews_started"] == 5 and saved["since"] == "2026-10-01"
    assert "Coach completion rate" in capsys.readouterr().out
