"""The offer of what the Coach already knows, through a session (NF-FC-023): stored when a session
starts, kept or changed by the worker in one step, and never counted before that."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from google.api_core.exceptions import ServiceUnavailable

from app.services.coach.known_details import (
    Item,
    UnknownKnownSlotError,
    collect_known,
    known_finder,
)
from app.services.coach.prefill import Prefill
from app.services.coach.session_service import CoachSessions
from app.services.coach.session_types import (
    NewMessage,
    SessionConflictError,
    SessionNotActiveError,
    SessionNotFoundError,
    SlotUpdate,
)
from tests.fixtures.coach_sessions import NOW, make_sessions
from tests.unit.services.test_coach_known_details import TODAY, salary, saved, sent

pytestmark = pytest.mark.anyio

UID = "worker-1"
PROFILE = {"host_country": "SG", "job_type": "domestic_worker"}
CONTRACT = Prefill("c1", 700.0, "SGD", "month", None)


def offer(
    contract: Prefill | None = None, income: list[dict[str, Any]] | None = None
) -> dict[str, Item]:
    return collect_known(
        profile=PROFILE,
        contract=contract,
        income=income if income is not None else [salary()],
        savings=[saved(1200, account_type="bank")],
        transfers=[sent(500, "2026-09-26")],
        today=TODAY,
    )


def finder(items: dict[str, Item]) -> Any:
    async def find(uid: str, contract: Prefill | None) -> dict[str, Item]:
        return items

    return find


def contract_finder(found: Prefill | None) -> Any:
    async def find(uid: str) -> Prefill | None:
        return found

    return find


async def started(
    items: dict[str, Item] | None = None, contract: Prefill | None = None
) -> tuple[CoachSessions, Any, str]:
    service, repo, _ = make_sessions()
    service._known = finder(offer(contract) if items is None else items)  # noqa: SLF001
    service._prefills = contract_finder(contract)  # noqa: SLF001
    result = await service.start(UID, "en", restart=False, now=NOW)
    return service, repo, result.session.id


async def keep(service: CoachSessions, session_id: str, slots: list[Any]) -> Any:
    return await service.apply_known(UID, session_id, slots, NOW + timedelta(minutes=1))


# --- the offer ----------------------------------------------------------------------------------


async def test_a_new_session_shows_the_offer_in_order_and_has_no_answer_yet() -> None:
    service, repo, session_id = await started()

    session = await service.get(UID, session_id, NOW)

    assert session.known is not None
    assert [item.slot for item in session.known.items] == [
        "destination_country",
        "job_type",
        "monthly_salary",
        "remittance_target",
        "savings",
        "bank_or_wallet",
    ]
    assert session.slots == {} and session.messages == []
    assert repo.docs[(UID, session_id)]["known"]["state"] == "offered"


async def test_the_offer_says_where_each_answer_came_from_and_how_old_it_is() -> None:
    service, _, session_id = await started()

    items = {i.slot: i for i in (await service.get(UID, session_id, NOW)).known.items}  # type: ignore[union-attr]

    assert (items["destination_country"].source, items["destination_country"].as_of) == (
        "profile",
        None,
    )
    assert (items["monthly_salary"].source, items["monthly_salary"].as_of) == (
        "income",
        "2026-09-25",
    )
    assert items["savings"].source == "savings" and items["remittance_target"].source == "transfers"


async def test_nothing_known_means_no_offer_at_all() -> None:
    service, repo, session_id = await started({})

    assert (await service.get(UID, session_id, NOW)).known is None
    assert "known" not in repo.docs[(UID, session_id)]


async def test_a_failed_read_never_stops_the_interview_from_starting() -> None:
    service, repo, _ = make_sessions()

    async def broken(uid: str, contract: Prefill | None) -> dict[str, Item]:
        raise ServiceUnavailable("no")

    service._known = broken  # noqa: SLF001
    result = await service.start(UID, "en", restart=False, now=NOW)

    assert result.session.known is None and result.session.stage == "intro"
    assert "known" not in repo.docs[(UID, result.session.id)]


async def test_a_resumed_session_still_shows_an_offer_that_was_never_answered() -> None:
    service, _, session_id = await started()

    again = await service.start(UID, "en", restart=False, now=NOW + timedelta(minutes=5))

    assert again.resumed and again.session.id == session_id and again.session.known is not None


# --- keeping ------------------------------------------------------------------------------------


async def test_keeping_everything_stores_confirmed_answers_with_their_sources() -> None:
    service, repo, session_id = await started()
    everything = [i.slot for i in (await service.get(UID, session_id, NOW)).known.items]  # type: ignore[union-attr]

    session = await keep(service, session_id, everything)

    assert {n: (s.confirmed, s.source) for n, s in session.slots.items()} == {
        "destination_country": (True, "profile_prefill"),
        "job_type": (True, "profile_prefill"),
        "monthly_salary": (True, "identity_prefill"),
        "remittance_target": (True, "identity_prefill"),
        "savings": (True, "identity_prefill"),
        "bank_or_wallet": (True, "identity_prefill"),
    }
    assert session.known is None  # answered: no longer offered
    stored = repo.docs[(UID, session_id)]
    assert stored["known"]["state"] == "resolved" and len(stored["known"]["kept"]) == 6
    assert session.messages == [] and session.turn_count == 0


async def test_the_interview_then_asks_only_what_is_missing() -> None:
    service, _, session_id = await started()
    everything = [i.slot for i in (await service.get(UID, session_id, NOW)).known.items]  # type: ignore[union-attr]

    session = await keep(service, session_id, everything)

    # Country and kind of work are known; the departure date is still asked.
    assert (session.stage, session.next_slot) == ("intro", "departure_date")
    after = await service.record_turn(
        UID,
        session_id,
        language="en",
        now=NOW + timedelta(minutes=2),
        updates=[SlotUpdate("departure_date", "2026-12-05", 0.95, True)],
        messages=[NewMessage("user", "5 December", "en")],
    )
    # Income is known, so the next question is the family's, not the pay.
    assert (after.stage, after.next_slot) == ("obligations", "dependents")


async def test_what_the_worker_changes_is_not_stored_and_is_asked_as_usual() -> None:
    service, _, session_id = await started()

    session = await keep(service, session_id, ["destination_country", "savings"])

    assert set(session.slots) == {"destination_country", "savings"}
    assert session.next_slot == "job_type"


async def test_keeping_nothing_is_allowed_and_everything_is_asked() -> None:
    service, _, session_id = await started()

    session = await keep(service, session_id, [])

    assert session.slots == {} and session.next_slot == "destination_country"
    assert session.known is None


async def test_asking_again_after_answering_changes_nothing() -> None:
    service, repo, session_id = await started()
    first = await keep(service, session_id, ["job_type"])
    revision = repo.docs[(UID, session_id)]["revision"]

    again = await keep(service, session_id, ["destination_country", "savings"])

    assert set(again.slots) == set(first.slots) == {"job_type"}
    assert repo.docs[(UID, session_id)]["revision"] == revision  # nothing was written


async def test_an_answer_the_worker_gave_in_the_chat_is_never_overwritten() -> None:
    service, repo, session_id = await started()
    repo.docs[(UID, session_id)]["slots"]["job_type"] = {
        "value": "care_worker",
        "confidence": 0.9,
        "source": "user",
        "confirmed": True,
        "updated_at": NOW,
        "turn": 1,
    }

    session = await keep(service, session_id, ["job_type", "destination_country"])

    assert session.slots["job_type"].value == "care_worker"
    assert session.slots["job_type"].source == "user"


async def test_an_answer_that_was_never_offered_is_refused_and_nothing_is_written() -> None:
    only_country = {"destination_country": offer()["destination_country"]}
    service, repo, session_id = await started(only_country)
    revision = repo.docs[(UID, session_id)]["revision"]

    with pytest.raises(UnknownKnownSlotError):
        await keep(service, session_id, ["destination_country", "savings"])

    assert repo.docs[(UID, session_id)]["revision"] == revision


async def test_a_finished_or_missing_session_cannot_take_it() -> None:
    service, repo, session_id = await started()
    repo.docs[(UID, session_id)]["status"] = "abandoned"

    with pytest.raises(SessionNotActiveError):
        await keep(service, session_id, [])
    with pytest.raises(SessionNotFoundError):
        await keep(service, "s_99", [])


async def test_a_session_changed_meanwhile_is_a_conflict_not_a_lost_answer() -> None:
    service, repo, session_id = await started()
    repo.stale_next_write = True

    with pytest.raises(SessionConflictError):
        await keep(service, session_id, ["job_type"])

    assert (await service.get(UID, session_id, NOW)).known is not None


async def test_a_session_with_no_offer_answers_the_same_session() -> None:
    service, _, session_id = await started({})

    session = await keep(service, session_id, [])

    assert session.id == session_id and session.slots == {}


# --- the contract's salary ----------------------------------------------------------------------


async def test_keeping_the_contract_salary_settles_that_offer_so_the_chat_does_not_ask() -> None:
    service, repo, session_id = await started(contract=CONTRACT)
    assert repo.docs[(UID, session_id)]["prefill"]["state"] == "offered"

    session = await keep(service, session_id, ["monthly_salary"])

    assert session.slots["monthly_salary"].source == "contract_prefill"
    assert session.slots["monthly_salary"].confirmed is True
    assert repo.docs[(UID, session_id)]["prefill"]["state"] == "resolved"
    assert repo.docs[(UID, session_id)]["prefill"]["confirmed"] is True


async def test_changing_the_contracts_salary_also_ends_that_offer_instead_of_asking_again() -> None:
    service, repo, session_id = await started(contract=CONTRACT)

    session = await keep(service, session_id, ["destination_country"])

    assert "monthly_salary" not in session.slots
    prefill = repo.docs[(UID, session_id)]["prefill"]
    assert prefill["state"] == "resolved" and prefill["confirmed"] is False


async def test_the_logged_salary_is_not_offered_when_a_contract_states_one() -> None:
    service, _, session_id = await started(contract=CONTRACT)

    items = {i.slot: i for i in (await service.get(UID, session_id, NOW)).known.items}  # type: ignore[union-attr]

    assert items["monthly_salary"].source == "contract"
    assert items["monthly_salary"].value["amount"] == 700.0


# --- reading the real repositories --------------------------------------------------------------


async def test_the_finder_reads_the_profile_and_the_three_kinds_of_entry() -> None:
    class Users:
        def get_profile(self, uid: str) -> dict[str, Any]:
            assert uid == UID
            return PROFILE

    class Fib:
        def list_entries(self, uid: str, kind: str) -> list[tuple[str, dict[str, Any]]]:
            return {
                "income": [("i1", salary())],
                "savings": [("s1", saved(300, account_type="mobile_wallet"))],
                "transfers": [("t1", {**sent(100, "2026-09-26")})],
            }[kind]

    find = known_finder(Users(), Fib())  # type: ignore[arg-type]

    found = await find(UID, None)

    assert found["destination_country"]["value"] == "SG"
    assert found["monthly_salary"]["value"]["amount"] == 650.0
    assert found["savings"]["value"]["amount"] == 300.0
    assert found["bank_or_wallet"]["value"] == "mobile_wallet"
