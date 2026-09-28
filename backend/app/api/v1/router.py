from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import contract_analysis, contracts, internal, users

# Pillar routers (remittance, radar, fib) are included here by their own tasks.
api_router = APIRouter()
api_router.include_router(contracts.router)
api_router.include_router(contract_analysis.router)
api_router.include_router(internal.router)
api_router.include_router(users.router)
