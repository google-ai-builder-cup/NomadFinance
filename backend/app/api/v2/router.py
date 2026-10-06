from __future__ import annotations

from fastapi import APIRouter

from app.api.v2 import flags

api_router = APIRouter()
api_router.include_router(flags.router)
