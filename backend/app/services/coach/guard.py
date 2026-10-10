"""The Coach guard: rules first, a Flash-Lite check for what the rules cannot judge (NF-FC-013).

`CoachGuard.check` runs before slot extraction on every worker message (design 4.2). The common
turn, an ordinary answer, is let through by `guard_rules.screen` with no model call. Danger, orders
to the coach and requests for a financial product are decided by the same rules. Only a message the
rules cannot place goes to one classifier call (`coach/guard.v1`). A turn the guard blocks is
answered with fixed text (`guard_texts`), so neither the extractor nor the reply model sees it.

Every decision is logged with its reason code and never with the message. A Gemini failure in the
classifier is not swallowed: the turn fails and the worker retries it, like any Gemini failure of a
turn, so the guard cannot be skipped by making the call fail.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.core.redact import redact_text
from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.coach_guard import ScopeVerdict
from app.schemas.contract import ReportLanguage
from app.services.coach.guard_rules import contains_link, fence, recommends_product, screen
from app.services.coach.guard_types import GuardDecision, GuardReason
from app.services.coach.question_bank import load_question_bank
from app.services.coach.session_machine import next_slot

logger = logging.getLogger(__name__)

GUARD_PROMPT = load_prompt("coach", "guard", 1)
# A block needs this much confidence. Distress needs less: a referral sent to a false alarm costs
# one kind message, a missed one costs far more.
BLOCK_AT = 0.7
DISTRESS_AT = 0.5


def decide(verdict: ScopeVerdict) -> GuardDecision:
    """The decision a classifier verdict leads to; an unsure label lets the turn through."""
    if verdict.label == "on_topic":
        return GuardDecision("allow", "on_topic_model")
    if verdict.label == "distress" and verdict.confidence >= DISTRESS_AT:
        return GuardDecision("refer", "distress_model")
    if verdict.confidence >= BLOCK_AT:
        if verdict.label == "injection":
            return GuardDecision("redirect", "injection_model")
        if verdict.label == "product_request":
            return GuardDecision("redirect", "product_request_model")
        if verdict.label == "off_topic":
            return GuardDecision("redirect", "off_topic_model")
    return GuardDecision("allow", "model_unsure")


class CoachGuard:
    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini
        self._bank = load_question_bank()
        self._settings = get_settings()

    async def check(
        self, document: dict[str, Any], text: str, language: ReportLanguage
    ) -> GuardDecision:
        """What to do with the worker's `text`: go on, redirect, or refer.

        Raises:
            GeminiError: The classifier call failed (only for a message the rules cannot judge).
        """
        decision = screen(text)
        if decision is None:
            decision = await self._ask_model(document, text, language)
        logger.info(
            "coach_guard action=%s reason=%s source=%s",
            decision.action,
            decision.reason,
            decision.source,
        )
        return decision

    def check_reply(self, reply: str) -> GuardReason | None:
        """`reply_recommends_product` when the coach's finished reply recommends a loan, an
        investment or an app, `reply_contains_link` when it holds a web link or an e-mail address;
        the turn then ends in an error and nothing is saved."""
        if recommends_product(reply):
            logger.warning("coach_guard action=block_reply reason=reply_recommends_product")
            return "reply_recommends_product"
        if contains_link(reply):
            logger.warning("coach_guard action=block_reply reason=reply_contains_link")
            return "reply_contains_link"
        return None

    async def _ask_model(
        self, document: dict[str, Any], text: str, language: ReportLanguage
    ) -> GuardDecision:
        verdict = await self._gemini.generate_structured(
            operation=GUARD_PROMPT.key,
            tier=ModelTier(self._settings.gemini_coach_guard_tier),
            contents=GUARD_PROMPT.render_user(
                worker_language=language,
                asking=self._asking(document),
                message=fence(redact_text(text)),
            ),
            response_model=ScopeVerdict,
            system_instruction=GUARD_PROMPT.system,
            temperature=0.0,
            thinking_budget=self._settings.gemini_coach_guard_thinking_budget,
        )
        return decide(verdict)

    def _asking(self, document: dict[str, Any]) -> str:
        stage = document["stage"]
        slot = next_slot(self._bank, stage, document["slots"], document.get("declined_slots", []))
        if slot is None:
            return f"nothing: the worker is at the {stage} step, confirming their answers"
        return self._bank.question(slot).prompt_en
