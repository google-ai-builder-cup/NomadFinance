from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast

import pytest

from app.integrations.gemini import GeminiClient, GeminiTimeoutError, ModelTier
from app.prompts.loader import load_prompt
from app.repositories.fib_repo import EntryKind, FibRepository
from app.schemas.fib import CategorizeAnswer, CategorizeResult
from app.services.fib import categorizer
from app.services.fib.categorizer import categorize_pending

pytestmark = pytest.mark.anyio


def _answer(*pairs: tuple[str, str, float]) -> CategorizeAnswer:
    return CategorizeAnswer(
        results=[
            CategorizeResult.model_validate({"id": i, "category": c, "confidence": conf})
            for i, c, conf in pairs
        ]
    )


class FakeGemini:
    """Answers each call with `handler(entries_in_the_prompt)`."""

    def __init__(self, handler: Callable[[list[dict[str, Any]]], CategorizeAnswer | Exception]):
        self.handler = handler
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> CategorizeAnswer:
        self.calls.append(kwargs)
        entries = json.loads(kwargs["contents"].split("<entries>")[1].split("</entries>")[0])
        outcome = self.handler(entries)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeFib:
    def __init__(self, income: dict[str, dict[str, Any]], bills: dict[str, dict[str, Any]]):
        self.docs: dict[str, dict[str, dict[str, Any]]] = {"income": income, "bills": bills}
        self.updates: list[tuple[str, str, dict[str, Any]]] = []

    def list_entries(self, uid: str, kind: EntryKind) -> list[tuple[str, dict[str, Any]]]:
        return list(self.docs[kind].items())

    def update_entry(
        self, uid: str, kind: EntryKind, entry_id: str, fields: dict[str, Any]
    ) -> None:
        self.docs[kind][entry_id] |= fields
        self.updates.append((kind, entry_id, fields))


def _run(gemini: FakeGemini, fib: FakeFib) -> Any:
    return categorize_pending("u1", cast(GeminiClient, gemini), cast(FibRepository, fib))


def _bill(**fields: Any) -> dict[str, Any]:
    return {"entry_date": "2026-09-20", "amount": 38.5, "currency": "SGD", "paid": True} | fields


def _by_vendor(answers: dict[str, tuple[str, float]]) -> Callable[..., CategorizeAnswer]:
    """Gemini stand-in: pick the answer by the entry's vendor or payer."""

    def handler(entries: list[dict[str, Any]]) -> CategorizeAnswer:
        return _answer(
            *[(e["id"], *answers[e.get("vendor") or e.get("payer") or ""]) for e in entries]
        )

    return handler


async def test_a_bill_without_a_category_is_categorized_with_confidence() -> None:
    fib = FakeFib({}, {"b1": _bill(vendor="Example Telecom", notes="monthly plan")})
    gemini = FakeGemini(_by_vendor({"Example Telecom": ("phone_internet", 0.97)}))

    response = await _run(gemini, fib)

    assert fib.docs["bills"]["b1"]["category"] == "phone_internet"
    assert fib.docs["bills"]["b1"]["category_source"] == "model"
    assert fib.docs["bills"]["b1"]["category_confidence"] == 0.97
    assert response.skipped == 0
    assert response.remaining == 0
    assert [(e.entry_id, e.entry_type, e.category) for e in response.categorized] == [
        ("b1", "bill", "phone_internet")
    ]


async def test_sends_the_entries_to_the_classification_tier_with_the_versioned_prompt() -> None:
    fib = FakeFib(
        {
            "i1": {
                "entry_date": "2026-09-25",
                "amount": 650,
                "currency": "SGD",
                "employer_name": "Acme",
            }
        },
        {"b1": _bill(vendor="Example Telecom", notes="monthly plan")},
    )
    gemini = FakeGemini(
        _by_vendor({"Example Telecom": ("phone_internet", 0.9), "Acme": ("salary", 0.8)})
    )

    await _run(gemini, fib)

    call = gemini.calls[0]
    prompt = load_prompt("fib", "categorize", 1)
    assert call["tier"] is ModelTier.CLASSIFICATION
    assert call["operation"] == "fib.categorize"
    assert call["response_model"] is CategorizeAnswer
    assert call["system_instruction"] == prompt.system
    entries = json.loads(call["contents"].split("<entries>")[1].split("</entries>")[0])
    # Oldest first across both types: the bill (09-20) before the income (09-25).
    assert entries == [
        {
            "id": "b1",
            "type": "bill",
            "amount": 38.5,
            "currency": "SGD",
            "vendor": "Example Telecom",
            "note": "monthly plan",
        },
        {"id": "i1", "type": "income", "amount": 650, "currency": "SGD", "payer": "Acme"},
    ]


async def test_a_photo_bill_with_a_model_category_but_no_confidence_is_categorized_again() -> None:
    fib = FakeFib(
        {}, {"b1": _bill(vendor="Example Telecom", category="utilities", category_source="model")}
    )
    gemini = FakeGemini(_by_vendor({"Example Telecom": ("phone_internet", 0.95)}))

    await _run(gemini, fib)

    assert fib.docs["bills"]["b1"]["category"] == "phone_internet"
    assert fib.docs["bills"]["b1"]["category_confidence"] == 0.95


async def test_user_and_already_confident_categories_are_left_alone_without_a_gemini_call() -> None:
    fib = FakeFib(
        {"i1": {"entry_date": "2026-09-25", "category": "salary", "category_source": "user"}},
        {
            "b1": _bill(category="rent", category_source="user"),
            "b2": _bill(category="food", category_source="model", category_confidence=0.9),
        },
    )
    gemini = FakeGemini(lambda entries: _answer())

    response = await _run(gemini, fib)

    assert gemini.calls == []
    assert fib.updates == []
    assert (response.categorized, response.skipped, response.remaining) == ([], 0, 0)


async def test_income_gets_an_income_category() -> None:
    fib = FakeFib({"i1": {"entry_date": "2026-09-25", "amount": 90, "employer_name": "Acme"}}, {})
    gemini = FakeGemini(_by_vendor({"Acme": ("overtime", 0.6)}))

    response = await _run(gemini, fib)

    assert fib.docs["income"]["i1"]["category"] == "overtime"
    assert response.categorized[0].entry_type == "income"


async def test_a_category_from_the_wrong_type_is_skipped_and_stays_pending() -> None:
    fib = FakeFib({}, {"b1": _bill(vendor="X"), "b2": _bill(vendor="Y")})
    gemini = FakeGemini(_by_vendor({"X": ("salary", 0.9), "Y": ("food", 0.8)}))

    response = await _run(gemini, fib)

    assert "category" not in fib.docs["bills"]["b1"]
    assert fib.docs["bills"]["b2"]["category"] == "food"
    assert response.skipped == 1
    assert len(response.categorized) == 1


async def test_a_missing_unknown_or_repeated_result_is_handled_per_entry() -> None:
    fib = FakeFib({}, {"b1": _bill(vendor="A"), "b2": _bill(vendor="B")})
    gemini = FakeGemini(
        lambda entries: _answer(
            ("b1", "rent", 0.9),
            ("b1", "food", 0.99),  # repeated: the first one counts
            ("not-an-entry", "food", 0.9),  # unknown: ignored
        )
    )

    response = await _run(gemini, fib)

    assert fib.docs["bills"]["b1"]["category"] == "rent"
    assert "category" not in fib.docs["bills"]["b2"]
    assert response.skipped == 1
    assert [e.entry_id for e in response.categorized] == ["b1"]


async def test_entries_are_sent_in_batches_oldest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(categorizer, "BATCH_SIZE", 2)
    fib = FakeFib(
        {},
        {
            "b3": _bill(entry_date="2026-09-03"),
            "b1": _bill(entry_date="2026-09-01"),
            "b2": _bill(entry_date="2026-09-02"),
        },
    )
    gemini = FakeGemini(
        lambda entries: _answer(*[(e["id"], "other_expense", 0.3) for e in entries])
    )

    response = await _run(gemini, fib)

    sent = [
        [e["id"] for e in json.loads(c["contents"].split("<entries>")[1].split("</entries>")[0])]
        for c in gemini.calls
    ]
    assert sent == [["b1", "b2"], ["b3"]]
    assert len(response.categorized) == 3


async def test_the_per_call_limit_leaves_the_rest_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(categorizer, "MAX_ENTRIES_PER_CALL", 2)
    fib = FakeFib({}, {f"b{n}": _bill(entry_date=f"2026-09-0{n}") for n in range(1, 5)})
    gemini = FakeGemini(lambda entries: _answer(*[(e["id"], "food", 0.9) for e in entries]))

    first = await _run(gemini, fib)

    assert [e.entry_id for e in first.categorized] == ["b1", "b2"]
    assert first.remaining == 2
    second = await _run(gemini, fib)
    assert [e.entry_id for e in second.categorized] == ["b3", "b4"]
    assert second.remaining == 0


async def test_a_gemini_failure_keeps_earlier_batches_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(categorizer, "BATCH_SIZE", 1)
    fib = FakeFib({}, {"b1": _bill(entry_date="2026-09-01"), "b2": _bill(entry_date="2026-09-02")})
    answers: list[CategorizeAnswer | Exception] = [
        _answer(("b1", "rent", 0.9)),
        GeminiTimeoutError("slow"),
    ]
    gemini = FakeGemini(lambda entries: answers.pop(0))

    with pytest.raises(GeminiTimeoutError):
        await _run(gemini, fib)

    assert fib.docs["bills"]["b1"]["category"] == "rent"
    assert "category" not in fib.docs["bills"]["b2"]
