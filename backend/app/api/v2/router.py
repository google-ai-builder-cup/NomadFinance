from __future__ import annotations

from fastapi import APIRouter

from app.api.v2 import coach, flags, scam, scam_checks

api_router = APIRouter()
api_router.include_router(flags.router)
api_router.include_router(coach.router)
api_router.include_router(scam.router)
api_router.include_router(scam_checks.router)
