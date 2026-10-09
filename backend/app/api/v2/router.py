from __future__ import annotations

from fastapi import APIRouter

from app.api.v2 import (
    coach,
    coach_checkins,
    coach_plans,
    coach_turns,
    flags,
    scam,
    scam_checks,
)

api_router = APIRouter()
api_router.include_router(flags.router)
api_router.include_router(coach.router)
api_router.include_router(coach_turns.router)
api_router.include_router(coach_plans.router)
api_router.include_router(coach_checkins.router)
api_router.include_router(scam.router)
api_router.include_router(scam_checks.router)
