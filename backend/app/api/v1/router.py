from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import contracts, internal

# Pillar routers (remittance, radar, fib, users) are included here by their own tasks.
api_router = APIRouter()
api_router.include_router(contracts.router)
api_router.include_router(internal.router)
