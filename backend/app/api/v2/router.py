from __future__ import annotations

from fastapi import APIRouter

from app.api.v2 import flags, scam

api_router = APIRouter()
api_router.include_router(flags.router)
api_router.include_router(scam.router)
