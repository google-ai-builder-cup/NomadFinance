from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from src.config import CORRIDORS
from src.loaders import frankfurter_backfill
from src.loaders.frankfurter_backfill import (
    FrankfurterSeries,
    Pair,
    backfill_pair,
    currency_pairs,
    main,
    new_entries,
)

START = date(2026, 9, 21)  # a Monday

SERIES = FrankfurterSeries.model_validate(
    {
        "amount": 1.0,
        "base": "SGD",
        "start_date": "2026-09-18",
        "end_date": "2026-09-25",
        "rates": {
            "2026-09-18": {"PHP": 43.0, "INR": 74.0},  # Friday before START: left out
            "2026-09-21": {"PHP": 43.1, "INR": 74.1},
            "2026-09-22": {"PHP": 43.2, "INR": 74.2},
            "2026-09-25": {"PHP": 43.5},
        },
    }
)


class _FakeSnapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


class _FakeDocument:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._store = store
        self._id = doc_id

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self._store.get(self._id))

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        assert merge, "the header must be merged, never replaced"
        current = self._store.setdefault(self._id, {})
        for key, value in data.items():
            if isinstance(value, dict):
                current.setdefault(key, {}).update(value)
            else:
                current[key] = value


class _FakeClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> Any:
        store = self.collections.setdefault(name, {})
        return type(
            "Collection", (), {"document": lambda _, doc_id: _FakeDocument(store, doc_id)}
        )()


def test_currency_pairs_follow_the_six_corridors() -> None:
    pairs = currency_pairs()

    assert [p.pair_id for p in pairs] == [
        f"{c.source_currency}_{c.destination_currency}" for c in CORRIDORS
    ]
    assert [p.pair_id for p in pairs] == [
        "SGD_PHP",
        "SGD_INR",
        "AUD_INR",
        "MYR_IDR",
        "JPY_PHP",
        "AUD_PHP",
    ]


def test_new_entries_skip_days_before_start_missing_quotes_and_stored_days() -> None:
    existing = {"2026-09-22": {"rate": 43.25, "provider": "frankfurter", "source": "cron"}}

    assert new_entries(SERIES, "PHP", existing, START) == {
        "2026-09-21": {"rate": 43.1, "provider": "frankfurter", "source": "backfill"},
        "2026-09-25": {"rate": 43.5, "provider": "frankfurter", "source": "backfill"},
    }
    assert list(new_entries(SERIES, "INR", {}, START)) == ["2026-09-21", "2026-09-22"]


def test_a_bad_rate_is_refused_before_anything_is_written() -> None:
    with pytest.raises(ValueError):
        FrankfurterSeries.model_validate({"base": "SGD", "rates": {"2026-09-21": {"PHP": 0}}})


def test_backfill_merges_missing_days_and_keeps_the_crons() -> None:
    client = _FakeClient()
    cron_day = {"rate": 43.25, "provider": "exchangerate_api", "source": "cron"}
    client.collections["rates_history"] = {
        "SGD_PHP": {"base_currency": "SGD", "updated_at": "kept", "daily": {"2026-09-22": cron_day}}
    }

    added, kept = backfill_pair(client, Pair("SGD", "PHP"), SERIES, START)  # type: ignore[arg-type]

    assert (added, kept) == (2, 1)
    doc = client.collections["rates_history"]["SGD_PHP"]
    assert doc["updated_at"] == "kept"
    assert doc["daily"]["2026-09-22"] == cron_day
    assert set(doc["daily"]) == {"2026-09-21", "2026-09-22", "2026-09-25"}


def test_a_second_run_adds_nothing() -> None:
    client = _FakeClient()
    pair = Pair("SGD", "INR")

    first = backfill_pair(client, pair, SERIES, START)  # type: ignore[arg-type]
    second = backfill_pair(client, pair, SERIES, START)  # type: ignore[arg-type]

    assert first == (2, 0)
    assert second == (0, 2)
    assert client.collections["rates_history"]["SGD_INR"]["quote_currency"] == "INR"


def test_dry_run_fetches_once_per_base_and_never_opens_firestore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, list[str], date, date]] = []

    def fake_fetch(base: str, quotes: list[str], start: date, end: date) -> FrankfurterSeries:
        calls.append((base, quotes, start, end))
        return FrankfurterSeries(base=base, rates={})

    def no_firestore() -> None:
        raise AssertionError("dry run must not open Firestore")

    monkeypatch.setattr(frankfurter_backfill, "fetch_series", fake_fetch)
    monkeypatch.setattr(frankfurter_backfill, "get_firestore_client", no_firestore)

    assert main(["--dry-run", "--days", "30", "--end", "2026-09-28"]) == 0

    assert [(base, quotes) for base, quotes, _, _ in calls] == [
        ("SGD", ["PHP", "INR"]),
        ("AUD", ["INR", "PHP"]),
        ("MYR", ["IDR"]),
        ("JPY", ["PHP"]),
    ]
    assert {(start, end) for _, _, start, end in calls} == {(date(2026, 8, 29), date(2026, 9, 28))}


@pytest.mark.parametrize(
    "argv", [["--days", "0"], ["--days", "4000"], ["--only", "EUR_USD"], ["--end", "yesterday"]]
)
def test_bad_arguments_stop_before_any_fetch(
    monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    monkeypatch.setattr(frankfurter_backfill, "fetch_series", pytest.fail)

    with pytest.raises(SystemExit):
        main(["--dry-run", *argv])
