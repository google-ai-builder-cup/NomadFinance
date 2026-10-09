"""The words of a 90-day plan, written by Gemini around figures made in code (NF-FC-012).

`CoachPlanWriter.write` gives the model the facts (`plan_facts.build_facts`) and asks only for
sentences. What comes back is checked by `plan_validator.check_text`: a number that is not one of
the facts is rejected, and the model is asked once more with the reasons. A second failure is a
`GeminiResponseError` (502 `ai_bad_response`) and nothing is stored. The plan is then put together
from the code's figures and the model's sentences, so a figure can never come from the model.
"""

from __future__ import annotations

import json
import logging

from app.config import get_settings
from app.integrations.gemini import GeminiClient, ModelTier
from app.integrations.gemini.errors import GeminiResponseError
from app.prompts.loader import load_prompt
from app.schemas.coach_plan import ChecklistItem, CoachPlan, PlanWarning, PlanWeek
from app.schemas.coach_plan_text import PlanText
from app.services.coach.plan_facts import (
    CHECKLIST_ABOUT,
    WARNING_ABOUT,
    PlanContext,
    build_facts,
    checklist_ids,
    warnings_for,
)
from app.services.coach.plan_validator import check_figures, check_text

logger = logging.getLogger(__name__)

PLAN_PROMPT = load_prompt("coach", "plan", 1)
ATTEMPTS = 2
# The standard note on every plan and PDF (design 4.4, NF-FC-013). Fixed text, not the model's.
DISCLAIMER = (
    "This plan is a guide to help you think ahead. It is not professional financial advice. "
    "Check important decisions with a trusted adviser or a worker support organisation."
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class CoachPlanWriter:
    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini
        self._settings = get_settings()

    async def write(self, ctx: PlanContext) -> CoachPlan:
        """The plan: the code's figures and the model's checked sentences.

        Raises:
            GeminiError: The call failed (a `GeminiResponseError` when the sentences were
                unusable twice).
        """
        facts = build_facts(ctx)
        specs = warnings_for(ctx)
        warning_ids = [spec.id for spec in specs]
        item_ids = checklist_ids(ctx)
        warnings_json = _json(
            [
                {
                    "id": s.id,
                    "severity": s.severity,
                    "about": WARNING_ABOUT[s.id],
                    "figures": s.about,
                }
                for s in specs
            ]
        )
        checklist_json = _json([{"id": i, "about": CHECKLIST_ABOUT[i]} for i in item_ids])
        fix_these = "none"
        for attempt in range(1, ATTEMPTS + 1):
            text = await self._gemini.generate_structured(
                operation=PLAN_PROMPT.key,
                tier=ModelTier(self._settings.gemini_coach_plan_tier),
                contents=PLAN_PROMPT.render_user(
                    facts_json=_json(facts),
                    warnings_json=warnings_json,
                    checklist_json=checklist_json,
                    fix_these=fix_these,
                ),
                response_model=PlanText,
                system_instruction=PLAN_PROMPT.system,
                temperature=0.3,
                thinking_budget=self._settings.gemini_coach_plan_thinking_budget,
                timeout_seconds=90,
            )
            problems = check_text(text, facts, warning_ids, item_ids)
            if not problems:
                return self._assemble(ctx, text)
            # Only the reasons are logged, never the sentences or the worker's figures.
            logger.warning("coach_plan_rejected attempt=%d problems=%d", attempt, len(problems))
            fix_these = "\n".join(problems)
        raise GeminiResponseError("The plan's sentences used numbers that were not given.")

    @staticmethod
    def _assemble(ctx: PlanContext, text: PlanText) -> CoachPlan:
        by_warning = {n.id: n.text for n in text.warnings}
        by_item = {n.id: n.text for n in text.checklist}
        figures = ctx.figures
        plan = CoachPlan(
            summary=text.summary,
            monthly_budget=figures.budget,
            remittance=figures.remittance,
            debt=figures.debt,
            emergency_fund=figures.emergency_fund,
            weeks=[PlanWeek(week=w.week, title=w.title, actions=w.actions) for w in text.weeks],
            warnings=[
                PlanWarning(id=spec.id, severity=spec.severity, text=by_warning[spec.id])
                for spec in warnings_for(ctx)
            ],
            checklist=[ChecklistItem(id=i, text=by_item[i]) for i in checklist_ids(ctx)],
            disclaimer=DISCLAIMER,
        )
        if problems := check_figures(plan, figures):
            raise GeminiResponseError("; ".join(problems))
        return plan
