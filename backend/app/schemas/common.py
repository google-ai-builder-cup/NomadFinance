from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness payload returned by `GET /health`."""

    status: Literal["ok"]
    version: str
    environment: str
