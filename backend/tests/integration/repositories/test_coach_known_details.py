"""NF-FC-023 against the Firestore emulator: the real profile and Financial Identity collections
are read, the offer is stored on the session, and what the worker keeps is written back whole."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from google.cloud.firestore import Client

from app.repositories.coach_session_repo import CoachPlanRepository, CoachSessionRepository
from app.repositories.fib_repo import FibRepository
from app.repositories.user_repo import UserRepository
from app.services.coach.known_details import known_finder
from app.services.coach.session_service import CoachSessions

pytestmark = pytest.mark.anyio

UID = "worker-known"
NOW = datetime.now(UTC).replace(microsecond=0)
DAY = date.today()


def _on(days_ago: int) -> str:
    return (DAY - timedelta(days=days_ago)).isoformat()


def _entry(**fields: Any) -> dict[str, Any]:
    return {"created_at": NOW, "updated_at": NOW, "schema_version": 1, "source": "manual", **fields}


def _service(client: Client) -> CoachSessions:
    return CoachSessions(
        CoachSessionRepository(client),
        CoachPlanRepository(client),
        known=known_finder(UserRepository(client), FibRepository(client)),
    )


def _worker(seed: Callable[[Mapping[str, dict[str, Any]]], None]) -> None:
    seed(
        {
            f"users/{UID}": {
                "host_country": "SG",
                "home_country": "IN",
                "job_type": "domestic_worker",
                "preferred_language": "en",
            },
            f"users/{UID}/income/i1": _entry(
                entry_date=_on(40), amount=600, currency="SGD", category="salary", verified=False
            ),
            f"users/{UID}/income/i2": _entry(
                entry_date=_on(10), amount=650, currency="SGD", category="salary", verified=False
            ),
            f"users/{UID}/income/i3": _entry(
                entry_date=_on(5), amount=80, currency="SGD", category="overtime", verified=False
            ),
            f"users/{UID}/savings/s1": _entry(
                entry_date=_on(30),
                amount=1500,
                currency="SGD",
                direction="deposit",
                account_type="bank",
            ),
            f"users/{UID}/savings/s2": _entry(
                entry_date=_on(12),
                amount=300,
                currency="SGD",
                direction="withdrawal",
                account_type="bank",
            ),
            f"users/{UID}/transfers/t1": _entry(
                entry_date=_on(35), send_amount=400, send_currency="SGD", corridor_id="SG-IN"
            ),
            f"users/{UID}/transfers/t2": _entry(
                entry_date=_on(8), send_amount=600, send_currency="SGD", corridor_id="SG-IN"
            ),
        }
    )


async def test_a_new_session_offers_what_the_real_collections_hold(
    clean_firestore: Client, seed_documents: Callable[[Mapping[str, dict[str, Any]]], None]
) -> None:
    _worker(seed_documents)
    service = _service(clean_firestore)

    started = await service.start(UID, "en", restart=False, now=NOW)

    assert started.session.known is not None
    items = {item.slot: item for item in started.session.known.items}
    assert list(items) == [
        "destination_country",
        "job_type",
        "monthly_salary",
        "remittance_target",
        "savings",
        "bank_or_wallet",
    ]
    assert items["destination_country"].value == "SG"
    assert items["monthly_salary"].value == {"amount": 650.0, "currency": "SGD", "period": "month"}
    assert items["monthly_salary"].as_of == _on(10)  # the overtime of a later day is not the pay
    assert items["savings"].value["amount"] == 1200.0  # 1,500 in, 300 out
    assert items["bank_or_wallet"].value == "bank_account"
    # Two months with a transfer: (400 + 600) / 2.
    assert items["remittance_target"].value["amount"] == 500.0
    assert started.session.slots == {} and started.session.messages == []


async def test_keeping_writes_confirmed_answers_and_the_session_resumes_without_the_offer(
    clean_firestore: Client, seed_documents: Callable[[Mapping[str, dict[str, Any]]], None]
) -> None:
    _worker(seed_documents)
    service = _service(clean_firestore)
    session_id = (await service.start(UID, "en", restart=False, now=NOW)).session.id

    kept = await service.apply_known(
        UID, session_id, ["destination_country", "job_type", "savings"], NOW
    )

    assert {name: slot.source for name, slot in kept.slots.items()} == {
        "destination_country": "profile_prefill",
        "job_type": "profile_prefill",
        "savings": "identity_prefill",
    }
    assert kept.known is None and kept.next_slot == "departure_date"
    stored = clean_firestore.document(f"users/{UID}/coach_sessions/{session_id}").get().to_dict()
    assert stored is not None
    assert stored["known"]["state"] == "resolved"
    assert stored["known"]["kept"] == ["destination_country", "job_type", "savings"]
    assert stored["slots"]["savings"]["confirmed"] is True
    again = await service.start(UID, "en", restart=False, now=NOW)
    assert again.resumed and again.session.known is None


async def test_a_worker_with_nothing_recorded_gets_an_ordinary_session(
    clean_firestore: Client, seed_documents: Callable[[Mapping[str, dict[str, Any]]], None]
) -> None:
    seed_documents({f"users/{UID}": {"preferred_language": "en"}})
    service = _service(clean_firestore)

    started = await service.start(UID, "en", restart=False, now=NOW)

    stored = (
        clean_firestore.document(f"users/{UID}/coach_sessions/{started.session.id}").get().to_dict()
    )
    assert started.session.known is None
    assert stored is not None and "known" not in stored
