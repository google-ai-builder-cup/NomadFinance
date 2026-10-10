"""The read-only check that a project can run the finale demo (NF-HR-003)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from google.cloud.firestore import Client

from src.loaders import demo_preflight
from src.loaders.demo_preflight import (
    DEMO_UIDS,
    HOSTS,
    MIN_PATTERNS,
    MIN_TAXONOMY,
    RATE_PAIRS,
    count,
    run,
)
from tests.fake_firestore import FakeClient

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
CORRIDORS = ("SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH")


def ready_project() -> FakeClient:
    """Everything the demo needs, as the loaders and the demo seed leave it."""
    client = FakeClient()
    for corridor in CORRIDORS:
        client.put(f"corridors/{corridor}")
    for host in HOSTS:
        client.put(f"labor_laws/{host}")
        client.put(f"cost_baselines/{host}")
        client.put(f"complaint_templates/{host}")
    for pair in RATE_PAIRS:
        client.put(f"rates_cache/{pair}", {"rate": 1.0, "fetched_at": NOW - timedelta(hours=1)})
    client.put("scam_taxonomy/_meta", {"version": 1})
    for n in range(MIN_TAXONOMY):
        client.put(f"scam_taxonomy/t{n}")
    for n in range(MIN_PATTERNS):
        client.put(f"scam_patterns/p{n}")
    client.put(
        "config/feature_flags",
        {"flags": {"coach": {"enabled": True}, "scam": {"enabled": True}}},
    )
    for uid in DEMO_UIDS:
        client.put(f"users/{uid}")
        client.put(f"users/{uid}/income/demo_i_01")
        client.put(f"users/{uid}/coach_plans/{'a' * 20}", {"demo_seed": True})
        for n in range(5):
            client.put(f"users/{uid}/scam_checks/{n:032d}", {"demo_seed": True})
    return client


def statuses(client: FakeClient) -> dict[str, str]:
    return {i.name: i.status for i in run(cast(Client, client), NOW)}


def test_a_project_with_everything_is_ready() -> None:
    items = run(cast(Client, ready_project()), NOW)

    assert [i for i in items if i.status != "ok"] == []
    assert len(items) == 7 + 2 + 3  # reference data, the two flags, the three workers


def test_each_missing_reference_collection_is_named_with_its_fix() -> None:
    client = ready_project()
    del client.store["cost_baselines/KR"]

    items = {i.name: i for i in run(cast(Client, client), NOW)}
    baseline = items["cost baselines (the Coach score and plan)"]

    assert baseline.status == "fail"
    assert "KR" in baseline.detail and "src.loaders.cost_baselines" in baseline.fix


@pytest.mark.parametrize(
    ("path", "name"),
    [
        ("corridors/SG-PH", "corridors"),
        ("labor_laws/JP", "labor laws"),
        ("complaint_templates/AU", "complaint templates"),
        ("rates_cache/SGD_PHP", "exchange rates"),
        ("scam_taxonomy/_meta", "scam taxonomy"),
    ],
)
def test_every_required_collection_is_checked(path: str, name: str) -> None:
    client = ready_project()
    del client.store[path]

    assert statuses(client)[name] == "fail"


def test_too_few_scam_patterns_fail_and_say_how_many() -> None:
    client = ready_project()
    for n in range(100):
        del client.store[f"scam_patterns/p{n}"]

    item = {i.name: i for i in run(cast(Client, client), NOW)}[
        "scam patterns (needs an embedding key)"
    ]

    assert item.status == "fail" and f"{MIN_PATTERNS - 100} of {MIN_PATTERNS}" == item.detail


def test_old_rates_are_a_warning_not_a_failure() -> None:
    client = ready_project()
    client.put("rates_cache/AUD_PHP", {"rate": 37.0, "fetched_at": NOW - timedelta(days=5)})

    item = {i.name: i for i in run(cast(Client, client), NOW)}["exchange rates"]

    assert item.status == "warn" and "refresh-rates" in item.fix


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({"coach": {"enabled": True}, "scam": {"enabled": True}}, ("ok", "ok")),
        ({"coach": {"enabled": False}, "scam": {"enabled": True}}, ("fail", "ok")),
        ({"coach": {"enabled": True}}, ("ok", "fail")),
        (
            {
                "coach": {"enabled": False, "allow_uids": list(DEMO_UIDS)},
                "scam": {"enabled": False, "allow_uids": ["uid_priya_demo"]},
            },
            ("ok", "fail"),
        ),
    ],
)
def test_the_module_flags_are_on_for_everyone_or_for_the_demo_workers(
    flags: dict[str, dict[str, object]], expected: tuple[str, str]
) -> None:
    client = ready_project()
    client.put("config/feature_flags", {"flags": flags})

    result = statuses(client)

    assert (result["flag coach"], result["flag scam"]) == expected


def test_a_missing_flag_document_fails_both() -> None:
    client = ready_project()
    del client.store["config/feature_flags"]

    result = statuses(client)

    assert result["flag coach"] == result["flag scam"] == "fail"


def test_a_worker_missing_the_demo_data_is_told_which_loader_to_run() -> None:
    client = ready_project()
    del client.store["users/uid_priya_demo/coach_plans/" + "a" * 20]
    del client.store[f"users/uid_rajesh_demo/scam_checks/{0:032d}"]
    del client.store["users/uid_miguel_demo/income/demo_i_01"]

    items = {i.name: i for i in run(cast(Client, client), NOW)}

    assert "demo_coach" in items["uid_priya_demo"].detail
    assert (
        "4 of 5" in items["uid_rajesh_demo"].detail
        and "demo_scam" in items["uid_rajesh_demo"].detail
    )
    assert "loaders.seed" in items["uid_miguel_demo"].detail
    assert {items[u].status for u in DEMO_UIDS} == {"fail"}


def test_a_worker_with_no_user_document_fails() -> None:
    client = ready_project()
    del client.store["users/uid_priya_demo"]

    assert statuses(client)["uid_priya_demo"] == "fail"


def test_count_falls_back_to_reading_ids_when_the_server_cannot_count() -> None:
    class Reference:
        def count(self) -> object:
            raise AttributeError("no aggregation")

        def select(self, _fields: list[str]) -> Reference:
            return self

        def stream(self) -> list[int]:
            return [1, 2, 3]

    assert count(Reference()) == 3


def test_the_exit_code_is_one_while_anything_required_is_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    client = ready_project()
    monkeypatch.setattr(demo_preflight, "get_firestore_client", lambda: client)

    assert demo_preflight.main([]) == 0

    del client.store["cost_baselines/SG"]
    assert demo_preflight.main([]) == 1
