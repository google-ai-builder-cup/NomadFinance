from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.core.errors import ApiError
from app.dependencies import get_coach_sessions, get_current_user, require_flag
from app.schemas.coach_session import (
    CoachOverview,
    CoachSession,
    CoachSessionCreateRequest,
    CoachSessionCreateResponse,
)
from app.schemas.user import AuthenticatedUser
from app.services.coach.session_service import CoachSessions
from app.services.coach.session_types import SessionConflictError, SessionNotFoundError

# A missing token is a 401 first; a caller without the `coach` flag gets the 404 an unknown path
# gets (docs/api/v2-coach.md, "What every route shares").
router = APIRouter(prefix="/coach", tags=["coach"], dependencies=[Depends(require_flag("coach"))])

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing, invalid, expired or revoked token"},
    404: {"description": "The `coach` flag is off for the caller"},
    429: {"description": "More than 60 calls a minute; see Retry-After"},
}
# What Firestore accepts as an id and what the backend hands out; anything else cannot exist.
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@router.post(
    "/sessions",
    response_model=CoachSessionCreateResponse,
    status_code=201,
    responses={
        **_RESPONSES,
        200: {"model": CoachSessionCreateResponse, "description": "The open session was resumed"},
        409: {"description": "Many starts at once gave up (`request_in_progress`); retry"},
        422: {"description": "A language outside the six"},
    },
    summary="Start the interview, or resume the open one",
)
async def start_coach_session(
    body: CoachSessionCreateRequest,
    response: Response,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    sessions: Annotated[CoachSessions, Depends(get_coach_sessions)],
) -> CoachSessionCreateResponse:
    """A worker has one active session: asking twice gives the same one (`resumed: true`, 200).

    A new session (201) has no messages; the screen opens the interview with a turn that has no
    text. `restart` closes the open session as `abandoned` and starts a new one. A resumed
    session keeps its own language. No Gemini call is made here.
    """
    try:
        result = await sessions.start(
            user.uid, body.language, restart=body.restart, now=datetime.now(UTC)
        )
    except SessionConflictError as exc:
        raise ApiError(
            409,
            "request_in_progress",
            "Another request is starting the interview. Try again in a moment.",
            headers={"Retry-After": "2"},
        ) from exc
    response.status_code = 200 if result.resumed else 201
    return CoachSessionCreateResponse.model_validate(
        {**result.session.model_dump(), "resumed": result.resumed}
    )


@router.get(
    "/sessions/{session_id}",
    response_model=CoachSession,
    responses=_RESPONSES,
    summary="One interview: answers, transcript, next question and score",
)
async def get_coach_session(
    session_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    sessions: Annotated[CoachSessions, Depends(get_coach_sessions)],
) -> CoachSession:
    """The session as it stands. Another worker's session, a missing one and an expired one are
    the same `404`, so a stranger cannot learn which ids exist. An active session with no turn
    for 14 days is closed as `abandoned` when it is read."""
    if not _SESSION_ID.match(session_id):
        raise ApiError(404, "not_found", "Not Found")
    try:
        return await sessions.get(user.uid, session_id, datetime.now(UTC))
    except SessionNotFoundError as exc:
        raise ApiError(404, "not_found", "Not Found") from exc


@router.get(
    "/overview",
    response_model=CoachOverview,
    responses=_RESPONSES,
    summary="The open session and the newest plan, for the dashboard card",
)
async def get_coach_overview(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    sessions: Annotated[CoachSessions, Depends(get_coach_sessions)],
) -> CoachOverview:
    """What the dashboard card needs to say Start, Resume or View plan. Creates nothing."""
    return await sessions.overview(user.uid, datetime.now(UTC))
