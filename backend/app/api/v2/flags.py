from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, get_feature_flag_service
from app.schemas.feature_flags import FeatureFlagsResponse
from app.schemas.user import AuthenticatedUser
from app.services.feature_flag_service import FeatureFlagService

router = APIRouter(prefix="/flags", tags=["flags"])

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing, invalid, expired or revoked token"},
}


@router.get("", response_model=FeatureFlagsResponse, responses=_RESPONSES, summary="My flags")
async def get_my_flags(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> FeatureFlagsResponse:
    """Which Future Scope modules are on for the caller.

    The answer is for the token's own uid. The frontend asks here instead of reading
    `config/feature_flags`, so other people's allow-listed uids never reach a browser.
    """
    return FeatureFlagsResponse(**await service.enabled_for(user.uid))
