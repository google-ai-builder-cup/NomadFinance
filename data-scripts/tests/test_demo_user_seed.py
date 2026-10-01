from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.config import SEED_USERS_DIR
from src.loaders import seed as seed_loader
from src.loaders.seed import entry_date, entry_documents, load_user, main, user_document
from src.validators.demo_user import UserSeed, is_blank, load, seed_files

PRIYA = SEED_USERS_DIR / "priya_sg_domestic.json"
NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
TODAY = NOW.date()


class _Snapshot:
    def __init__(self, exists: bool) -> None:
        self.exists = exists


class _Doc:
    def __init__(self, doc_id: str) -> None:
        self.id = doc_id


class _Ref:
    def __init__(self, client: _FakeClient, path: str) -> None:
        self.client = client
        self.path = path

    def document(self, doc_id: str) -> _Ref:
        return _Ref(self.client, f"{self.path}/{doc_id}")

    def collection(self, name: str) -> _Ref:
        return _Ref(self.client, f"{self.path}/{name}")

    def get(self) -> _Snapshot:
        return _Snapshot(self.path in self.client.store)

    def stream(self) -> list[_Doc]:
        prefix = f"{self.path}/"
        return [
            _Doc(path.removeprefix(prefix))
            for path in self.client.store
            if path.startswith(prefix) and "/" not in path.removeprefix(prefix)
        ]


class _Batch:
    def __init__(self, client: _FakeClient) -> None:
        self._client = client
        self._ops: list[tuple[str, str, dict[str, Any] | None]] = []

    def set(self, ref: _Ref, data: dict[str, Any]) -> None:
        self._ops.append(("set", ref.path, data))

    def delete(self, ref: _Ref) -> None:
        self._ops.append(("delete", ref.path, None))

    def commit(self) -> None:
        self._client.commits += 1
        for op, path, data in self._ops:
            if op == "set" and data is not None:
                self._client.store[path] = data
            else:
                self._client.store.pop(path, None)


class _FakeClient:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.commits = 0

    def collection(self, name: str) -> _Ref:
        return _Ref(self, name)

    def batch(self) -> _Batch:
        return _Batch(self)


@pytest.fixture
def priya() -> UserSeed:
    return load(PRIYA)


def _raw() -> dict[str, Any]:
    return json.loads(PRIYA.read_text(encoding="utf-8"))


def _check(raw: dict[str, Any]) -> UserSeed:
    return UserSeed.model_validate(raw)


# --- the committed file ---------------------------------------------------------------


def test_priyas_file_is_valid_and_has_the_planned_history(priya: UserSeed) -> None:
    assert priya.uid == "uid_priya_demo"
    assert (len(priya.income), len(priya.transfers), len(priya.bills), len(priya.savings)) == (
        9,
        6,
        12,
        4,
    )
    assert (priya.user.host_country, priya.user.home_country) == ("SG", "IN")
    assert priya.user.preferred_language == "hi"


def test_priya_has_six_months_of_salary_and_transfers(priya: UserSeed) -> None:
    salary_months = {e.months_ago for e in priya.income if e.category == "salary"}
    transfer_months = {t.months_ago for t in priya.transfers}

    assert salary_months == set(range(6))
    assert transfer_months == set(range(6))


def test_the_story_holds_in_the_numbers(priya: UserSeed) -> None:
    income = sum(e.amount for e in priya.income)
    net_savings = sum(s.amount if s.direction == "deposit" else -s.amount for s in priya.savings)
    by_month = sorted(priya.transfers, key=lambda t: -t.months_ago)

    assert income == 4230
    assert net_savings == 470  # 11% of income: below the 20% target, so a middling score
    # She moved to a cheaper provider after comparing, and the logged cost shows it.
    assert [t.provider_name for t in by_month] == ["Ample Transfer"] * 3 + ["Wise"] * 3
    assert all(t.cost_pct is not None and t.cost_pct > 2 for t in by_month[:3])
    assert all(t.cost_pct is not None and t.cost_pct < 1 for t in by_month[3:])
    # Every transfer's cost follows from its own numbers: 1 - received / (sent x mid-market).
    for t in priya.transfers:
        assert t.mid_market_rate is not None and t.cost_pct is not None
        expected = round((1 - t.receive_amount / (t.send_amount * t.mid_market_rate)) * 100, 2)
        assert t.cost_pct == expected


def test_one_bill_is_unpaid_and_both_entry_paths_appear(priya: UserSeed) -> None:
    assert [b.id for b in priya.bills if not b.paid] == ["demo_b_05"]
    assert {b.source for b in priya.bills} == {"manual", "bill_ocr"}
    assert {b.category_source for b in priya.bills} == {"model", "user"}


def test_the_other_demo_files_are_still_empty_stubs() -> None:
    blanks = {p.stem for p in seed_files() if is_blank(p)}

    assert blanks == {"miguel_jp_care", "rajesh_kr_manufacturing"}


# --- dates ----------------------------------------------------------------------------


def test_entry_dates_count_back_in_calendar_months() -> None:
    assert entry_date(date(2026, 10, 15), 5, 1) == date(2026, 5, 1)
    assert entry_date(date(2026, 10, 15), 0, 8) == date(2026, 10, 8)
    # Across a year boundary.
    assert entry_date(date(2026, 2, 10), 3, 12) == date(2025, 11, 12)
    assert entry_date(date(2026, 1, 31), 1, 28) == date(2025, 12, 28)


def test_every_entry_is_dated_up_to_today(priya: UserSeed) -> None:
    documents, ahead = entry_documents(priya, TODAY, NOW)

    assert ahead == 0
    assert [len(documents[k]) for k in ("income", "transfers", "bills", "savings")] == [9, 6, 12, 4]
    assert all(
        date.fromisoformat(doc["entry_date"]) <= TODAY
        for kind in documents.values()
        for doc in kind.values()
    )


def test_entries_dated_after_today_are_left_out_and_counted(priya: UserSeed) -> None:
    early = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

    documents, ahead = entry_documents(priya, early.date(), early)

    # This month's transfer (the 3rd) and phone bill (the 8th) are still ahead.
    assert ahead == 2
    assert "demo_t_06" not in documents["transfers"]
    assert "demo_b_12" not in documents["bills"]
    assert "demo_i_09" in documents["income"]  # the salary on the 1st is already paid


# --- documents ------------------------------------------------------------------------


def test_income_documents_are_a_workers_own_unverified_entries(priya: UserSeed) -> None:
    income, _ = entry_documents(priya, TODAY, NOW)

    doc = income["income"]["demo_i_01"]
    assert doc == {
        "entry_date": "2026-05-01",
        "amount": 650,
        "currency": "SGD",
        "category": "salary",
        "employer_name": "Example Household",
        "category_source": "user",
        "verified": False,
        "source": "manual",
        "created_at": datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        "schema_version": 1,
    }


def test_transfer_documents_follow_the_transfer_log_shape(priya: UserSeed) -> None:
    transfers, _ = entry_documents(priya, TODAY, NOW)

    doc = transfers["transfers"]["demo_t_01"]
    assert doc["source"] == "remittance_log"
    assert doc["corridor_id"] == "SG-IN"
    assert (doc["send_currency"], doc["receive_currency"]) == ("SGD", "INR")
    assert doc["provider_rpw_id"] == 521253376
    assert "fx_rate_applied" not in doc  # never set by the log (NF-P2-017)
    assert {"id", "months_ago", "day"}.isdisjoint(doc)


def test_bill_documents_carry_their_category_and_extraction(priya: UserSeed) -> None:
    bills = entry_documents(priya, TODAY, NOW)[0]["bills"]

    scanned = bills["demo_b_10"]
    assert scanned["source"] == "bill_ocr"
    assert scanned["extraction"] == {
        "confidence": 0.94,
        "model": "gemini-3.5-flash-lite",
        "prompt_version": 1,
    }
    assert scanned["bill_date"] == "2026-09-05"
    assert scanned["entry_date"] == "2026-09-08"
    assert "bill_day" not in scanned
    assert "image_path" not in scanned  # no photo exists for demo data

    typed = bills["demo_b_01"]
    assert typed["source"] == "manual"
    assert "extraction" not in typed and "bill_date" not in typed
    assert (typed["category"], typed["category_source"]) == ("phone_internet", "model")
    assert typed["category_confidence"] == 0.97

    clinic = bills["demo_b_09"]
    assert (clinic["category"], clinic["category_source"]) == ("medical", "user")
    assert "category_confidence" not in clinic
    assert bills["demo_b_05"]["paid"] is False


def test_savings_documents_keep_the_direction_and_a_positive_amount(priya: UserSeed) -> None:
    savings = entry_documents(priya, TODAY, NOW)[0]["savings"]

    assert savings["demo_s_03"]["direction"] == "withdrawal"
    assert savings["demo_s_03"]["amount"] == 80
    assert savings["demo_s_01"]["source"] == "manual"


def test_timestamps_are_noon_of_the_entry_day_but_never_in_the_future(priya: UserSeed) -> None:
    income = entry_documents(priya, TODAY, NOW)[0]["income"]

    assert income["demo_i_01"]["created_at"] == datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    # Today's noon is after NOW (09:00): clamped.
    today_entry = income["demo_i_09"]
    assert date.fromisoformat(today_entry["entry_date"]) == date(2026, 10, 1)
    clamp_now = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    early = entry_documents(priya, clamp_now.date(), clamp_now)[0]["income"]["demo_i_09"]
    assert early["created_at"] == clamp_now


def test_the_user_document_is_what_onboarding_leaves(priya: UserSeed) -> None:
    doc = user_document(priya, NOW)

    assert doc["home_country"] == "IN"
    assert doc["host_country"] == "SG"
    assert doc["job_type"] == "domestic_worker"
    assert doc["preferred_language"] == "hi"
    assert doc["onboarding_completed_at"] == NOW
    assert doc["notification_prefs"] == {
        "radar_alerts": True,
        "radar_corridors": ["SG-IN"],
        "reminders": True,
    }
    assert doc["fcm_tokens"] == []
    assert doc["schema_version"] == 1


# --- writing --------------------------------------------------------------------------


def test_load_writes_every_entry_and_a_new_user(priya: UserSeed) -> None:
    client = _FakeClient()

    result = load_user(client, priya, "uid_priya_demo", TODAY, NOW)  # type: ignore[arg-type]

    assert result.written == {"income": 9, "transfers": 6, "bills": 12, "savings": 4}
    assert (result.ahead, result.removed, result.user_created) == (0, 0, True)
    assert "users/uid_priya_demo" in client.store
    assert "users/uid_priya_demo/income/demo_i_01" in client.store
    assert "users/uid_priya_demo/financial_profile/current" not in client.store
    assert client.commits == 1
    assert len(client.store) == 1 + 9 + 6 + 12 + 4


def test_load_is_idempotent(priya: UserSeed) -> None:
    client = _FakeClient()
    load_user(client, priya, "uid_priya_demo", TODAY, NOW)  # type: ignore[arg-type]
    first = dict(client.store)

    result = load_user(client, priya, "uid_priya_demo", TODAY, NOW)  # type: ignore[arg-type]

    assert client.store == first
    assert (result.removed, result.user_created) == (0, False)


def test_an_existing_user_document_is_left_as_it_was(priya: UserSeed) -> None:
    client = _FakeClient()
    real = {"home_country": "PH", "host_country": "JP", "preferred_language": "tl"}
    client.store["users/real_uid"] = dict(real)

    result = load_user(client, priya, "real_uid", TODAY, NOW)  # type: ignore[arg-type]

    assert client.store["users/real_uid"] == real
    assert result.user_created is False
    assert "users/real_uid/income/demo_i_01" in client.store  # the entries still go to that uid


def test_stale_demo_entries_are_removed_and_other_entries_are_not_touched(
    priya: UserSeed,
) -> None:
    client = _FakeClient()
    client.store["users/uid_priya_demo/bills/demo_b_99"] = {"vendor": "gone from the file"}
    client.store["users/uid_priya_demo/bills/real_bill"] = {"vendor": "the worker's own"}
    client.store["users/uid_priya_demo/transfers/AbC123"] = {"provider_name": "real transfer"}

    result = load_user(client, priya, "uid_priya_demo", TODAY, NOW)  # type: ignore[arg-type]

    assert result.removed == 1
    assert "users/uid_priya_demo/bills/demo_b_99" not in client.store
    assert "users/uid_priya_demo/bills/real_bill" in client.store
    assert "users/uid_priya_demo/transfers/AbC123" in client.store


def test_a_later_run_adds_what_was_still_ahead_of_the_first(priya: UserSeed) -> None:
    client = _FakeClient()
    early = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    first = load_user(client, priya, "uid_priya_demo", early.date(), early)  # type: ignore[arg-type]

    second = load_user(client, priya, "uid_priya_demo", TODAY, NOW)  # type: ignore[arg-type]

    assert first.ahead == 2
    assert second.ahead == 0
    assert "users/uid_priya_demo/transfers/demo_t_06" in client.store


# --- the command ----------------------------------------------------------------------


def _fake_clock_and_client(monkeypatch: pytest.MonkeyPatch, client: _FakeClient | None) -> None:
    def fail() -> Any:
        raise AssertionError("a dry run must not reach Firestore")

    monkeypatch.setattr(seed_loader, "get_firestore_client", (lambda: client) if client else fail)


def test_main_dry_run_never_touches_firestore(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _fake_clock_and_client(monkeypatch, None)

    with caplog.at_level("INFO"):
        assert main(["--dry-run"]) == 0

    assert "[dry-run] priya_sg_domestic.json -> users/uid_priya_demo" in caplog.text
    assert "miguel_jp_care.json: empty, skipped" in caplog.text


def test_main_writes_under_a_chosen_uid(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    _fake_clock_and_client(monkeypatch, client)

    assert main(["--only", "priya_sg_domestic", "--uid", "FirebaseUid123"]) == 0

    assert any(path.startswith("users/FirebaseUid123/income/demo_i_") for path in client.store)
    assert not any(path.startswith("users/uid_priya_demo") for path in client.store)


def test_main_refuses_a_uid_when_two_users_would_get_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _FakeClient()
    _fake_clock_and_client(monkeypatch, client)
    for name in ("one", "two"):
        (tmp_path / f"{name}.json").write_text(json.dumps(_raw()), encoding="utf-8")

    assert main(["--input-dir", str(tmp_path), "--uid", "x"]) == 1

    assert client.store == {}


def test_main_rejects_an_unknown_file_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_clock_and_client(monkeypatch, None)

    assert main(["--only", "nobody"]) == 1


def test_main_writes_nothing_when_a_file_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _FakeClient()
    _fake_clock_and_client(monkeypatch, client)
    raw = _raw()
    (tmp_path / "good.json").write_text(json.dumps(raw), encoding="utf-8")
    raw["income"][0]["amount"] = -1
    (tmp_path / "bad.json").write_text(json.dumps(raw), encoding="utf-8")

    assert main(["--input-dir", str(tmp_path)]) == 1

    assert client.store == {}


def test_main_skips_blank_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    _fake_clock_and_client(monkeypatch, client)
    (tmp_path / "stub.json").write_text("  \n", encoding="utf-8")

    assert main(["--input-dir", str(tmp_path)]) == 0

    assert client.store == {}


# --- the schema -----------------------------------------------------------------------


def test_an_empty_file_is_not_a_valid_user() -> None:
    with pytest.raises(ValueError):
        load_text("")


def load_text(text: str) -> UserSeed:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(str(exc)) from exc
    return UserSeed.model_validate(raw)


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda r: r["income"][0].update(amount=0), "greater than 0"),
        (lambda r: r["income"][0].update(currency="sgd"), "pattern"),
        (lambda r: r["income"][0].update(category="rent"), "salary"),
        (lambda r: r["income"][0].update(months_ago=12), "less than or equal to 11"),
        (lambda r: r["income"][0].update(day=29), "less than or equal to 28"),
        (lambda r: r["income"][0].update(id="income_1"), "pattern"),
        (lambda r: r["income"][1].update(id="demo_i_01"), "duplicate entry ids"),
        (lambda r: r["income"][0].update(surprise=1), "Extra inputs"),
        (lambda r: r["transfers"][0].update(corridor_id="SG-XX"), "corridor_id"),
        (lambda r: r["transfers"][0].update(receive_currency="PHP"), "pays out INR"),
        (lambda r: r["bills"][0].update(category_confidence=None), "category_confidence"),
        (lambda r: r["bills"][8].update(category_confidence=0.9), "category_confidence"),
        (lambda r: r["bills"][9].pop("extraction"), "extraction"),
        (lambda r: r["bills"][0].update(source="bill_ocr"), "extraction"),
        (lambda r: r["bills"][9].update(bill_day=20), "dated after"),
        (lambda r: r["savings"][0].update(direction="sideways"), "deposit"),
        (lambda r: r["user"].update(host_country="AE"), "host_country"),
        (lambda r: r["user"].update(home_country="SG"), "PH"),
        (lambda r: r["user"].update(preferred_language="fr"), "en"),
        (lambda r: r.update(uid="has spaces"), "pattern"),
    ],
)
def test_the_schema_rejects_bad_files(edit: Any, message: str) -> None:
    raw = _raw()
    edit(raw)

    with pytest.raises(ValidationError, match=message):
        _check(raw)


def test_a_user_without_any_entry_is_rejected() -> None:
    raw = _raw()
    raw["income"], raw["transfers"], raw["bills"], raw["savings"] = [], [], [], []

    with pytest.raises(ValidationError, match="at least one entry"):
        _check(raw)
