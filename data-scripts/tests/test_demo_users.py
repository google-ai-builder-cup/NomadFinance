"""The three demo workers together (NF-P3-021): the numbers behind each story and the accounts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from src.config import SEED_USERS_DIR
from src.loaders import demo_accounts
from src.loaders.demo_accounts import ACCOUNTS, AccountConflictError, ensure_account
from src.loaders.seed import entry_documents
from src.validators.demo_user import UserSeed, load

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)


def _seed(name: str) -> UserSeed:
    return load(SEED_USERS_DIR / f"{name}.json")


@pytest.fixture
def rajesh() -> UserSeed:
    return _seed("rajesh_kr_manufacturing")


@pytest.fixture
def miguel() -> UserSeed:
    return _seed("miguel_jp_care")


def test_each_worker_is_who_the_tracker_says() -> None:
    expected = {
        "priya_sg_domestic": ("SG", "domestic_worker", "IN"),
        "rajesh_kr_manufacturing": ("KR", "manufacturing_worker", "IN"),
        "miguel_jp_care": ("JP", "care_worker", "PH"),
    }
    for name, (host, job, home) in expected.items():
        user = _seed(name).user
        assert (user.host_country, user.job_type, user.home_country) == (host, job, home)


def test_uids_are_distinct_and_match_the_accounts() -> None:
    uids = {a.seed_name: _seed(a.seed_name).uid for a in ACCOUNTS}

    assert len(set(uids.values())) == 3
    assert uids == {
        "priya_sg_domestic": "uid_priya_demo",
        "rajesh_kr_manufacturing": "uid_rajesh_demo",
        "miguel_jp_care": "uid_miguel_demo",
    }


def test_every_worker_has_six_months_of_salary() -> None:
    for account in ACCOUNTS:
        seed = _seed(account.seed_name)
        months = {e.months_ago for e in seed.income if e.category == "salary"}
        assert months == set(range(6)), account.seed_name
        assert len(seed.bills) >= 12 and len(seed.savings) >= 4


# --- Rajesh ---------------------------------------------------------------------------


def test_rajesh_has_no_transfers_because_no_corridor_starts_in_korea(rajesh: UserSeed) -> None:
    assert rajesh.transfers == []


def test_rajeshs_pay_is_his_contract_wage_less_deductions(rajesh: UserSeed) -> None:
    salaries = {e.amount for e in rajesh.income if e.category == "salary"}
    contract_wage = 1_950_000  # kr_manufacturing_worker (NF-P3-020), clause 3

    assert len(salaries) == 1
    # Dormitory 400,000 and agency fee 150,000 come off first (clauses 8 and 9).
    assert salaries.pop() <= contract_wage - 400_000 - 150_000
    assert {e.currency for e in rajesh.income + rajesh.bills + rajesh.savings} == {"KRW"}


def test_rajesh_saves_almost_nothing_and_pays_two_bills_late(rajesh: UserSeed) -> None:
    income = sum(e.amount for e in rajesh.income)
    net = sum(s.amount if s.direction == "deposit" else -s.amount for s in rajesh.savings)

    assert 0 < net / income < 0.03
    assert [b.months_ago for b in rajesh.bills if not b.paid] == [2, 1]
    assert any(s.direction == "withdrawal" for s in rajesh.savings)


# --- Miguel ---------------------------------------------------------------------------


def test_miguel_moves_from_the_flagged_operator_to_a_cheaper_one(miguel: UserSeed) -> None:
    by_month = sorted(miguel.transfers, key=lambda t: -t.months_ago)

    assert [t.provider_name for t in by_month] == ["Kapitan Padala"] * 3 + [
        "DCOM Money Express"
    ] * 3
    assert all(t.cost_pct is not None and t.cost_pct > 5 for t in by_month[:3])
    assert all(t.cost_pct is not None and t.cost_pct < 2.1 for t in by_month[3:])
    assert {t.corridor_id for t in by_month} == {"JP-PH"}
    # The flagged operator is invented, so it has no World Bank id; the real one does.
    assert all(t.provider_rpw_id is None for t in by_month[:3])
    assert all(t.provider_rpw_id == 521253120 for t in by_month[3:])


def test_miguels_transfer_costs_follow_from_their_own_numbers(miguel: UserSeed) -> None:
    for t in miguel.transfers:
        assert t.mid_market_rate is not None and t.cost_pct is not None
        expected = round((1 - t.receive_amount / (t.send_amount * t.mid_market_rate)) * 100, 2)
        assert t.cost_pct == expected


def test_miguel_saves_close_to_the_target_and_pays_all_but_one_bill(miguel: UserSeed) -> None:
    income = sum(e.amount for e in miguel.income)
    net = sum(s.amount if s.direction == "deposit" else -s.amount for s in miguel.savings)

    assert 0.15 < net / income < 0.20
    assert len([b for b in miguel.bills if not b.paid]) == 1
    assert {e.category for e in miguel.income} == {"salary", "overtime", "bonus"}


def test_the_flagged_operator_is_one_the_radar_seed_knows() -> None:
    from src.validators.radar_seed import load as load_radar

    names = {r.entity_name for r in load_radar().reports}

    assert "Kapitan Padala" in names


# --- every file loads on any run day --------------------------------------------------


@pytest.mark.parametrize("run_day", [date(2026, 10, 1), date(2026, 10, 14), date(2026, 10, 30)])
def test_every_worker_loads_on_any_run_day(run_day: date) -> None:
    for account in ACCOUNTS:
        seed = _seed(account.seed_name)
        now = datetime(run_day.year, run_day.month, run_day.day, 9, tzinfo=UTC)
        docs, ahead = entry_documents(seed, run_day, now)
        written = sum(len(v) for v in docs.values())
        total = len(seed.income) + len(seed.transfers) + len(seed.bills) + len(seed.savings)

        assert written + ahead == total
        # Paydays are on the 25th, so only entries of the running month can still be ahead.
        assert all(
            doc["entry_date"] <= run_day.isoformat()
            for kind in docs.values()
            for doc in kind.values()
        )
        assert ahead <= 6


# --- the Auth accounts ----------------------------------------------------------------


class _AuthUser:
    def __init__(self, uid: str, phone: str, name: str | None) -> None:
        self.uid, self.phone_number, self.display_name = uid, phone, name


class _FakeAuth:
    """Stands in for firebase_admin.auth: users by uid, with the same lookups and errors."""

    UserNotFoundError = type("UserNotFoundError", (Exception,), {})

    def __init__(self) -> None:
        self.users: dict[str, _AuthUser] = {}
        self.calls: list[str] = []

    def get_user(self, uid: str, app: Any = None) -> _AuthUser:
        if uid not in self.users:
            raise self.UserNotFoundError()
        return self.users[uid]

    def get_user_by_phone_number(self, phone: str, app: Any = None) -> _AuthUser:
        for user in self.users.values():
            if user.phone_number == phone:
                return user
        raise self.UserNotFoundError()

    def create_user(self, uid: str, phone_number: str, display_name: str, app: Any = None) -> None:
        self.calls.append("create")
        self.users[uid] = _AuthUser(uid, phone_number, display_name)

    def update_user(self, uid: str, phone_number: str, display_name: str, app: Any = None) -> None:
        self.calls.append("update")
        self.users[uid] = _AuthUser(uid, phone_number, display_name)


@pytest.fixture
def fake_auth(monkeypatch: pytest.MonkeyPatch) -> _FakeAuth:
    fake = _FakeAuth()
    monkeypatch.setattr(demo_accounts, "auth", fake)
    monkeypatch.setattr(demo_accounts, "get_firebase_app", lambda: None)
    return fake


def test_phone_numbers_are_the_three_firebase_test_numbers() -> None:
    assert [a.phone_number for a in ACCOUNTS] == ["+61491570156", "+61491570157", "+61491570158"]


def test_ensure_account_creates_then_leaves_alone(fake_auth: _FakeAuth) -> None:
    account = ACCOUNTS[0]

    assert ensure_account("uid_priya_demo", account) == "created"
    assert ensure_account("uid_priya_demo", account) == "unchanged"
    assert fake_auth.calls == ["create"]


def test_ensure_account_repairs_a_changed_name_or_number(fake_auth: _FakeAuth) -> None:
    fake_auth.users["uid_priya_demo"] = _AuthUser("uid_priya_demo", "+61400000000", None)

    assert ensure_account("uid_priya_demo", ACCOUNTS[0]) == "updated"
    assert fake_auth.users["uid_priya_demo"].phone_number == ACCOUNTS[0].phone_number


def test_a_number_owned_by_another_uid_is_never_taken_over(fake_auth: _FakeAuth) -> None:
    fake_auth.users["real_uid"] = _AuthUser("real_uid", ACCOUNTS[0].phone_number, "Someone")

    with pytest.raises(AccountConflictError, match="--uid real_uid"):
        ensure_account("uid_priya_demo", ACCOUNTS[0])

    assert set(fake_auth.users) == {"real_uid"}


def test_main_creates_all_three_and_is_repeatable(fake_auth: _FakeAuth) -> None:
    assert demo_accounts.main([]) == 0
    assert set(fake_auth.users) == {"uid_priya_demo", "uid_rajesh_demo", "uid_miguel_demo"}
    assert demo_accounts.main([]) == 0
    assert fake_auth.calls == ["create"] * 3


def test_main_dry_run_never_reaches_firebase(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_: Any, **__: Any) -> None:
        raise AssertionError("a dry run must not call Firebase Auth")

    monkeypatch.setattr(demo_accounts, "ensure_account", fail)

    assert demo_accounts.main(["--dry-run"]) == 0


def test_main_reports_a_conflict_and_still_does_the_others(fake_auth: _FakeAuth) -> None:
    fake_auth.users["real_uid"] = _AuthUser("real_uid", ACCOUNTS[1].phone_number, None)

    assert demo_accounts.main([]) == 1
    assert {"uid_priya_demo", "uid_miguel_demo"} <= set(fake_auth.users)
    assert "uid_rajesh_demo" not in fake_auth.users


def test_main_rejects_an_unknown_name_and_a_blank_file(tmp_path: Any, fake_auth: _FakeAuth) -> None:
    assert demo_accounts.main(["--only", "nobody"]) == 1
    (tmp_path / "priya_sg_domestic.json").write_text(" \n", encoding="utf-8")

    assert demo_accounts.main(["--input-dir", str(tmp_path), "--only", "priya_sg_domestic"]) == 1
    assert fake_auth.users == {}
