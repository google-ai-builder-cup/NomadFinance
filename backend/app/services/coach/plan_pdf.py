"""Rendering the plan to a PDF (NF-FC-014)."""

from __future__ import annotations

from app.schemas.coach_plan import CoachPlanResponse
from app.services.coach.plan_pdf_html import build_plan_html
from app.services.fib.exporter import render_pdf


def render_plan_pdf(response: CoachPlanResponse) -> bytes:
    """The PDF bytes of a stored plan. Blocking and CPU-bound: call it in a thread."""
    return render_pdf(build_plan_html(response))
