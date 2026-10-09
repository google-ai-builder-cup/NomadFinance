"""Real Gemini: the Coach's streamed reply, its first piece and its language (NF-FC-009).

Opt-in because it needs GEMINI_API_KEY in .env.local and uses free-tier quota (3 calls, the
answers are invented):

    RUN_LIVE_GEMINI=1 pytest tests/integration/test_coach_reply_live.py -v -s

`-s` prints the time to the first piece on each tier, which is what the setting
`GEMINI_COACH_REPLY_TIER` and D-115 are decided on. The goal of NF-FC-009 is a first piece in
under 2 seconds at the 95th percentile; three calls do not measure a percentile, they show
whether a tier is in reach at all.
"""

from __future__ import annotations

import os
import re

import pytest

from app.config import get_settings
from app.integrations.gemini import GeminiClient, ModelTier
from app.schemas.coach_session import CoachTurnRequest
from app.services.coach.question_bank import load_question_bank
from app.services.coach.session_document import new_document
from app.services.coach.turn_prompt import REPLY_PROMPT, reply_message
from app.services.coach.turn_types import Understanding
from tests.fixtures.coach_sessions import NOW

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
    ),
]

BANK = load_question_bank()
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


@pytest.mark.parametrize(
    ("tier", "budget"),
    [(ModelTier.CLASSIFICATION, 0), (ModelTier.REASONING, 0), (ModelTier.REASONING, None)],
)
async def test_the_opening_reply_in_hindi_asks_the_first_question(
    tier: ModelTier, budget: int | None
) -> None:
    body = CoachTurnRequest(language="hi")
    document = new_document("hi", NOW, BANK)
    message = reply_message(BANK, document, Understanding(), body.text, body.language)

    async with await GeminiClient(get_settings()).stream(
        operation="coach.reply",
        tier=tier,
        message=message,
        system_instruction=REPLY_PROMPT.system,
        temperature=0.3,
        thinking_budget=budget,
    ) as stream:
        pieces = [piece async for piece in stream]
    print(
        f"\n{tier.value} budget={budget}: first piece {stream.time_to_first_token_ms} ms, "
        f"{len(pieces)} pieces: {stream.text}"
    )

    assert DEVANAGARI.search(stream.text), "the reply should be written in Hindi"
    assert "?" in stream.text or "?" in stream.text
