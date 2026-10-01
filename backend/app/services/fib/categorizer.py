"""Financial Identity Builder: transaction categorization (NF-P3-012), step 3 of the FIB pipeline.

Flash-Lite (classification tier) gives a category and a confidence to the entries that have no
trusted one, in batches. A category the worker chose (`category_source: "user"`) is never
touched. A bill photo's category (NF-P3-011) has no confidence yet, so it is categorized again
here, which gives every model category a confidence that can be compared.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal, get_args

from fastapi.concurrency import run_in_threadpool

from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.repositories.fib_repo import EntryKind, FibRepository
from app.schemas.fib import (
    BillCategory,
    CategorizeAnswer,
    CategorizedEntry,
    CategorizeResult,
    FibCategorizeResponse,
    IncomeCategory,
)

logger = logging.getLogger(__name__)

# Loaded at import so a missing or malformed prompt file stops the app at startup.
CATEGORIZE_PROMPT = load_prompt("fib", "categorize", 1)

BATCH_SIZE = 25
# No calibration behind this: it bounds one request to 4 Gemini calls. The rest stays pending
# and is reported as `remaining`.
MAX_ENTRIES_PER_CALL = 100

EntryType = Literal["income", "bill"]


@dataclass(frozen=True)
class _Kind:
    collection: EntryKind
    entry_type: EntryType
    # Field that names the other party in the stored entry, and the key the prompt expects.
    party_field: str
    party_key: str
    allowed: frozenset[str]


_KINDS = (
    _Kind("income", "income", "employer_name", "payer", frozenset(get_args(IncomeCategory))),
    _Kind("bills", "bill", "vendor", "vendor", frozenset(get_args(BillCategory))),
)


@dataclass(frozen=True)
class _Pending:
    kind: _Kind
    entry_id: str
    data: dict[str, Any]

    def for_prompt(self) -> dict[str, Any]:
        entry = {
            "id": self.entry_id,
            "type": self.kind.entry_type,
            "amount": self.data.get("amount"),
            "currency": self.data.get("currency"),
            self.kind.party_key: self.data.get(self.kind.party_field),
            "note": self.data.get("notes"),
        }
        return {key: value for key, value in entry.items() if value is not None}


def _is_pending(data: dict[str, Any]) -> bool:
    if not data.get("category"):
        return True
    return data.get("category_source") == "model" and data.get("category_confidence") is None


async def _find_pending(uid: str, fib: FibRepository) -> list[_Pending]:
    pending: list[_Pending] = []
    for kind in _KINDS:
        entries = await run_in_threadpool(fib.list_entries, uid, kind.collection)
        pending += [
            _Pending(kind, entry_id, data) for entry_id, data in entries if _is_pending(data)
        ]
    pending.sort(key=lambda item: (item.data.get("entry_date", ""), item.entry_id))
    return pending


async def _categorize_batch(
    batch: list[_Pending], gemini: GeminiClient
) -> dict[str, CategorizeResult]:
    answer = await gemini.generate_structured(
        operation=CATEGORIZE_PROMPT.key,
        tier=ModelTier.CLASSIFICATION,
        contents=CATEGORIZE_PROMPT.render_user(
            entries_json=json.dumps([item.for_prompt() for item in batch], ensure_ascii=False)
        ),
        response_model=CategorizeAnswer,
        system_instruction=CATEGORIZE_PROMPT.system,
    )
    # First answer for an id wins; a repeated id is not trusted to be the better one.
    by_id: dict[str, CategorizeResult] = {}
    for result in answer.results:
        by_id.setdefault(result.id, result)
    return by_id


async def categorize_pending(
    uid: str, gemini: GeminiClient, fib: FibRepository
) -> FibCategorizeResponse:
    """Categorize the caller's pending income and bill entries, oldest first.

    Batches run one after another. An entry Gemini answers badly for (no result, or a category
    that does not fit its type) stays pending and is counted in `skipped`; it does not fail
    the batch.

    Raises:
        GeminiError: Any Gemini failure. Batches already written stay written, and a new call
            picks up only what is still pending.
    """
    pending = await _find_pending(uid, fib)
    selected = pending[:MAX_ENTRIES_PER_CALL]

    categorized: list[CategorizedEntry] = []
    skipped = 0
    for start in range(0, len(selected), BATCH_SIZE):
        batch = selected[start : start + BATCH_SIZE]
        by_id = await _categorize_batch(batch, gemini)
        for item in batch:
            result = by_id.get(item.entry_id)
            if result is None or result.category not in item.kind.allowed:
                skipped += 1
                logger.warning("fib_categorize_unusable entry_type=%s", item.kind.entry_type)
                continue
            fields = {
                "category": result.category,
                "category_source": "model",
                "category_confidence": result.confidence,
            }
            await run_in_threadpool(
                fib.update_entry, uid, item.kind.collection, item.entry_id, fields
            )
            categorized.append(
                CategorizedEntry(
                    entry_id=item.entry_id,
                    entry_type=item.kind.entry_type,
                    category=result.category,
                    confidence=result.confidence,
                )
            )

    remaining = len(pending) - len(selected)
    logger.info(
        "fib_categorized categorized=%d skipped=%d remaining=%d",
        len(categorized),
        skipped,
        remaining,
    )
    return FibCategorizeResponse(categorized=categorized, skipped=skipped, remaining=remaining)
