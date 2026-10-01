from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.integrations.gemini import (
    GeminiClient,
    GeminiResponseError,
    GeminiTimeoutError,
    ModelTier,
)
from app.prompts.loader import load_prompt
from app.repositories.fib_repo import EntryKind, FibRepository
from app.repositories.rate_repo import RateRepository
from app.repositories.user_repo import UserRepository
from app.schemas.fib_profile import NarrativeAnswer
from app.services.fib.narrative import write_narrative
from app.services.fib.profile_builder import recompute_all, recompute_profile

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 15, 2, 0, tzinfo=UTC)


class FakeGemini:
    def __init__(
        self,
        outcome: NarrativeAnswer | Exception | None = None,
        fail_if: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self.outcome = outcome or NarrativeAnswer(text="Line one.\n\nLine two.")
        self.fail_if = fail_if
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> NarrativeAnswer:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        if self.fail_if is not None and self.fail_if(self.profile_sent(len(self.calls) - 1)):
            raise GeminiTimeoutError("slow")
        return self.outcome

    def profile_sent(self, call: int = 0) -> dict[str, Any]:
        text = self.calls[call]["contents"]
        return cast(dict[str, Any], json.loads(text.split("<profile>")[1].split("</profile>")[0]))


class FakeFib:
    def __init__(self, data: dict[str, dict[str, list[tuple[str, dict[str, Any]]]]]) -> None:
        self.data = data
        self.saved: dict[str, dict[str, Any]] = {}

    def list_entries(self, uid: str, kind: EntryKind) -> list[tuple[str, dict[str, Any]]]:
        return self.data.get(uid, {}).get(kind, [])

    def save_profile(self, uid: str, profile: dict[str, Any]) -> None:
        self.saved[uid] = profile


class FakeUsers:
    def __init__(self, profiles: dict[str, dict[str, Any]]) -> None:
        self.profiles = profiles

    def list_user_ids(self) -> list[str]:
        return list(self.profiles)

    def get_profile(self, uid: str) -> dict[str, Any]:
        return self.profiles.get(uid, {})


class FakeRates:
    def __init__(self, rates: dict[str, float] | None = None) -> None:
        self.rates = rates if rates is not None else {"SGD_INR": 60.0}

    def get_rate(self, pair_id: str) -> dict[str, Any] | None:
        return {"rate": self.rates[pair_id]} if pair_id in self.rates else None


def _entries(*items: tuple[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    return list(items)


def _priya() -> dict[str, list[tuple[str, dict[str, Any]]]]:
    income = {"currency": "SGD", "employer_name": "Mrs Tan Example", "category": "salary"}
    return {
        "income": _entries(
            ("i1", {"entry_date": "2026-08-25", "amount": 650} | income),
            ("i2", {"entry_date": "2026-09-25", "amount": 650} | income),
        ),
        "transfers": _entries(
            (
                "t1",
                {"entry_date": "2026-08-26", "receive_amount": 25000, "receive_currency": "INR"},
            ),
            (
                "t2",
                {"entry_date": "2026-09-26", "receive_amount": 25650, "receive_currency": "INR"},
            ),
        ),
        "bills": _entries(
            ("b1", {"entry_date": "2026-09-24", "amount": 38.5, "currency": "SGD", "paid": True}),
            ("b2", {"entry_date": "2026-09-25", "amount": 20, "currency": "SGD", "paid": False}),
        ),
        "savings": _entries(
            (
                "s1",
                {
                    "entry_date": "2026-09-25",
                    "amount": 130,
                    "currency": "SGD",
                    "direction": "deposit",
                },
            ),
        ),
    }


def _run(
    fib: FakeFib,
    users: FakeUsers,
    gemini: FakeGemini,
    rates: FakeRates | None = None,
    uid: str = "u1",
) -> Any:
    return recompute_profile(
        uid,
        cast(GeminiClient, gemini),
        cast(FibRepository, fib),
        cast(UserRepository, users),
        cast(RateRepository, rates or FakeRates()),
        NOW,
    )


async def test_a_full_history_is_stored_as_the_data_model_describes() -> None:
    fib = FakeFib({"u1": _priya()})
    users = FakeUsers({"u1": {"home_country": "IN", "preferred_language": "hi"}})
    gemini = FakeGemini()

    outcome = await _run(fib, users, gemini)

    profile = fib.saved["u1"]
    assert outcome == "recomputed"
    assert profile["reporting_currency"] == "INR"
    assert profile["period_start"] == "2026-08-25"
    assert profile["period_end"] == "2026-10-15"
    assert profile["months_of_data"] == 3
    assert profile["entry_counts"] == {"income": 2, "transfers": 2, "bills": 2, "savings": 1}
    assert set(profile["metrics"]) == {
        "income_stability",
        "savings_rate",
        "remittance_consistency",
        "bill_payment_reliability",
    }
    assert profile["metrics"]["income_stability"]["score"] == 100
    assert profile["metrics"]["income_stability"]["detail"]["mean_monthly_income"] == 39000
    assert profile["metrics"]["bill_payment_reliability"]["score"] == 50
    # 130 saved of 1300 income: 10%, half of the 20% target.
    assert profile["metrics"]["savings_rate"]["score"] == 50
    assert profile["overall_score"] == round((100 + 50 + 100 + 50) / 4)
    assert profile["narrative"] == {
        "language": "hi",
        "text": "Line one.\n\nLine two.",
        "model": "gemini-3.5-flash",
    }
    assert profile["prompt_versions"] == {"fib.synthesize_narrative": 1}
    assert profile["computed_at"] == NOW
    assert "verified_employment" not in profile


async def test_the_narrative_prompt_gets_the_metrics_but_no_overall_score_or_names() -> None:
    fib = FakeFib({"u1": _priya()})
    gemini = FakeGemini()

    await _run(fib, FakeUsers({"u1": {"home_country": "IN"}}), gemini)

    call = gemini.calls[0]
    prompt = load_prompt("fib", "synthesize_narrative", 1)
    assert call["tier"] is ModelTier.REASONING
    assert call["operation"] == "fib.synthesize_narrative"
    assert call["system_instruction"] == prompt.system
    assert call["timeout_seconds"] == 90.0
    assert call["contents"].startswith("Write the report in English.")
    sent = gemini.profile_sent()
    assert set(sent) == {
        "period_start",
        "period_end",
        "months_of_data",
        "reporting_currency",
        "entry_counts",
        "metrics",
        "income_verified_by_contract",
    }
    assert sent["income_verified_by_contract"] is False
    assert "Tan" not in call["contents"]


async def test_the_report_language_is_the_workers_with_english_as_the_fallback() -> None:
    for preferred, expected in (("tl", "Tagalog"), ("xx", "English"), (None, "English")):
        gemini = FakeGemini()
        profile = {"home_country": "IN", "preferred_language": preferred}

        await _run(FakeFib({"u1": _priya()}), FakeUsers({"u1": profile}), gemini)

        assert gemini.calls[0]["contents"].startswith(f"Write the report in {expected}")


async def test_income_backed_by_a_contract_is_listed_and_flagged_to_the_prompt() -> None:
    data = _priya()
    data["income"].append(
        (
            "i3",
            {
                "entry_date": "2026-09-01",
                "amount": 650,
                "currency": "SGD",
                "employer_name": "Example Household",
                "verified": True,
                "contract_ref": "c1",
            },
        )
    )
    fib, gemini = FakeFib({"u1": data}), FakeGemini()

    await _run(fib, FakeUsers({"u1": {"home_country": "IN"}}), gemini)

    assert fib.saved["u1"]["verified_employment"] == [
        {
            "employer_name": "Example Household",
            "salary_amount": 650,
            "salary_currency": "SGD",
            "contract_ref": "c1",
        }
    ]
    assert gemini.profile_sent()["income_verified_by_contract"] is True
    assert "Example Household" not in gemini.calls[0]["contents"]


async def test_without_a_rate_to_the_home_currency_the_workers_own_currency_is_used() -> None:
    fib = FakeFib({"u1": _priya()})
    gemini = FakeGemini()

    # NP is not one of the six corridors: there is no SGD_NPR rate.
    await _run(fib, FakeUsers({"u1": {"home_country": "NP"}}), gemini)

    profile = fib.saved["u1"]
    assert profile["reporting_currency"] == "SGD"
    assert profile["metrics"]["income_stability"]["detail"]["mean_monthly_income"] == 650
    # The transfers' INR amounts have no rate to SGD: left out of the total, and counted.
    detail = profile["metrics"]["remittance_consistency"]["detail"]
    assert detail["total_received"] == 0
    assert detail["excluded_entries"] == 2


async def test_a_worker_with_only_bills_gets_the_one_metric_they_have() -> None:
    data = {"bills": _priya()["bills"]}
    fib = FakeFib({"u1": data})

    outcome = await _run(fib, FakeUsers({"u1": {"home_country": "IN"}}), FakeGemini())

    profile = fib.saved["u1"]
    assert outcome == "recomputed"
    assert profile["reporting_currency"] == "INR"
    assert profile["metrics"]["income_stability"]["score"] is None
    assert profile["overall_score"] == 50


async def test_no_activity_in_the_period_writes_nothing_and_calls_no_gemini() -> None:
    old = {
        "income": _entries(("i1", {"entry_date": "2024-01-25", "amount": 650, "currency": "SGD"}))
    }
    for data in ({}, old):
        fib, gemini = FakeFib({"u1": data}), FakeGemini()

        outcome = await _run(fib, FakeUsers({"u1": {"home_country": "IN"}}), gemini)

        assert outcome == "no_data"
        assert fib.saved == {}
        assert gemini.calls == []


async def test_entries_no_metric_can_use_write_nothing() -> None:
    data = {"savings": _priya()["savings"]}
    fib, gemini = FakeFib({"u1": data}), FakeGemini()

    outcome = await _run(fib, FakeUsers({"u1": {"home_country": "IN"}}), gemini)

    assert outcome == "no_data"
    assert gemini.calls == []


async def test_a_narrative_failure_keeps_the_previous_profile() -> None:
    fib = FakeFib({"u1": _priya()})

    with pytest.raises(GeminiTimeoutError):
        await _run(
            fib, FakeUsers({"u1": {"home_country": "IN"}}), FakeGemini(GeminiTimeoutError("slow"))
        )

    assert fib.saved == {}


async def test_the_narrative_turns_a_literal_backslash_n_into_a_line_break() -> None:
    gemini = FakeGemini(NarrativeAnswer(text="First.\\n\\nSecond.\\n"))

    text, model = await write_narrative({"metrics": {}}, "en", cast(GeminiClient, gemini))

    assert text == "First.\n\nSecond."
    assert model == "gemini-3.5-flash"


async def test_an_empty_narrative_is_an_error() -> None:
    gemini = FakeGemini(NarrativeAnswer(text="  \\n "))

    with pytest.raises(GeminiResponseError):
        await write_narrative({"metrics": {}}, "en", cast(GeminiClient, gemini))


async def test_one_users_failure_does_not_stop_the_run() -> None:
    slow = _priya()
    slow["bills"].append(
        ("b3", {"entry_date": "2026-09-26", "amount": 5, "currency": "SGD", "paid": True})
    )
    corrupt = {"income": _entries(("i1", {"entry_date": "2026-09-25", "currency": "SGD"}))}
    fib = FakeFib({"ok": _priya(), "empty": {}, "slow": slow, "corrupt": corrupt})
    users = FakeUsers({uid: {"home_country": "IN"} for uid in ("ok", "empty", "slow", "corrupt")})
    # Only the "slow" user has three bills, so only its narrative call times out.
    gemini = FakeGemini(fail_if=lambda sent: sent["entry_counts"]["bills"] == 3)

    response = await recompute_all(
        cast(GeminiClient, gemini),
        cast(FibRepository, fib),
        cast(UserRepository, users),
        cast(RateRepository, FakeRates()),
        NOW,
    )

    assert response.users_seen == 4
    assert response.recomputed == 1
    assert response.skipped_no_data == 1
    assert response.failed == 2
    assert list(fib.saved) == ["ok"]
