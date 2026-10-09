"""The plan in other languages, and as a PDF (NF-FC-014).

A translation is made on first request and stored (`coach_plans/{id}/translations/{lang}`); a PDF
is rendered on first request and kept in Cloud Storage (`exports/{uid}/coach-plan-{id}-{lang}.pdf`,
recorded in the plan's `pdf` map). Both are made once: the plan itself never changes.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.integrations.cloud_storage import ExportStore
from app.repositories.coach_session_repo import CoachPlanRepository
from app.schemas.coach_plan import CoachPlan, CoachPlanResponse
from app.schemas.contract import ReportLanguage
from app.services.coach.plan_document import ENGLISH, SCHEMA_VERSION
from app.services.coach.plan_pdf import render_plan_pdf
from app.services.coach.plan_translator import TRANSLATE_PROMPT, CoachPlanTranslator

# Called just before the model is asked, so a read that finds the translation stored does not
# spend the Gemini budget.
BeforeTranslation = Callable[[], Awaitable[None]]


class PlanFiles:
    def __init__(
        self, plans: CoachPlanRepository, translator: CoachPlanTranslator, store: ExportStore
    ) -> None:
        self._plans = plans
        self._translator = translator
        self._store = store

    async def plan_in(
        self,
        uid: str,
        plan_id: str,
        document: dict[str, Any],
        language: ReportLanguage,
        now: datetime,
        before_translation: BeforeTranslation | None = None,
    ) -> tuple[CoachPlan, list[ReportLanguage]]:
        """The plan in `language` and the languages now stored. Translates once if needed.

        Raises:
            GeminiError: The translation failed; nothing is stored.
        """
        english = CoachPlan.model_validate(document["plan"])
        if language == ENGLISH:
            return english, await self._available(uid, plan_id)
        stored = await run_in_threadpool(self._plans.get_translation, uid, plan_id, language)
        if stored is None:
            if before_translation is not None:
                await before_translation()
            translated = await self._translator.translate(english, language)
            entry = {
                "language": language,
                "plan": translated.model_dump(mode="json"),
                "model": self._translator.model,
                "prompt_version": TRANSLATE_PROMPT.version,
                "created_at": now,
                "schema_version": SCHEMA_VERSION,
            }
            if not await run_in_threadpool(
                self._plans.create_translation, uid, plan_id, language, entry
            ):  # another request stored one first: use that, so every reader sees the same text
                stored = await run_in_threadpool(
                    self._plans.get_translation, uid, plan_id, language
                )
                translated = CoachPlan.model_validate(stored["plan"]) if stored else translated
            plan = translated
        else:
            plan = CoachPlan.model_validate(stored["plan"])
        return plan, await self._available(uid, plan_id)

    async def pdf(
        self,
        uid: str,
        plan_id: str,
        document: dict[str, Any],
        response: CoachPlanResponse,
        now: datetime,
    ) -> bytes:
        """The PDF of `response` (a plan in one language), from storage or rendered now."""
        language = response.language
        entry = (document.get("pdf") or {}).get(language)
        if entry:
            kept = await run_in_threadpool(self._store.read, uid, entry["storage_path"])
            if kept is not None:
                return kept
        data = await run_in_threadpool(render_plan_pdf, response)
        path = await run_in_threadpool(
            self._store.upload, uid, f"coach-plan-{plan_id}-{language}.pdf", data
        )
        await run_in_threadpool(
            self._plans.set_pdf, uid, plan_id, language, {"storage_path": path, "created_at": now}
        )
        return data

    async def _available(self, uid: str, plan_id: str) -> list[ReportLanguage]:
        others = await run_in_threadpool(self._plans.translation_languages, uid, plan_id)
        return [ENGLISH, *others]  # type: ignore[list-item]
