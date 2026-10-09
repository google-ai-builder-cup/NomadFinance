from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse

from app.core.errors import ApiError, request_id_from_scope
from app.core.rate_limit import limit_ai_calls
from app.core.sse import SSE_HEADERS, SSE_MEDIA_TYPE, with_heartbeat
from app.dependencies import get_coach_turns, get_current_user, require_flag
from app.schemas.coach_session import CoachTurnRequest
from app.schemas.user import AuthenticatedUser
from app.services.coach.session_types import (
    SessionFullError,
    SessionNotActiveError,
    SessionNotFoundError,
)
from app.services.coach.turn_service import CoachTurns
from app.services.coach.turn_types import (
    KeyReusedError,
    ReplayTurn,
    RequestInProgressError,
    TextRequiredError,
    TurnInProgressError,
)

# The guard of the other Coach routes: a 401 first, then the 404 of an unknown path if the flag
# is off.
router = APIRouter(prefix="/coach", tags=["coach"], dependencies=[Depends(require_flag("coach"))])

_KEY = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_RETRY = {"Retry-After": "2"}


async def _replayed(frames: tuple[str, ...]) -> AsyncIterator[str]:
    for frame in frames:
        yield frame


@router.post(
    "/sessions/{session_id}/messages",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "The turn, as events"},
        400: {"description": "`Idempotency-Key` missing or malformed (`idempotency_key_invalid`)"},
        401: {"description": "Missing, invalid, expired or revoked token"},
        404: {"description": "The `coach` flag is off, or no such session of the caller's"},
        409: {
            "description": "`session_not_active`, `session_full`, `turn_in_progress` or "
            "`request_in_progress` (the last two send `Retry-After: 2`)"
        },
        422: {
            "description": "Empty or over-long text, text left out, a language outside the six, "
            "or the key reused with another body (`idempotency_key_reused`)"
        },
        429: {"description": "More than 10 turns a minute; see Retry-After"},
        502: {"description": "Gemini returned an unusable answer (`ai_bad_response`)"},
        503: {"description": "Gemini busy or unavailable (`ai_busy`, `ai_unavailable`)"},
        504: {"description": "Gemini timed out (`ai_timeout`)"},
    },
    dependencies=[Depends(limit_ai_calls)],
    summary="One turn of the interview: the worker speaks, the coach answers as a stream",
)
async def post_coach_turn(
    session_id: str,
    body: CoachTurnRequest,
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    turns: Annotated[CoachTurns, Depends(get_coach_turns)],
    idempotency_key: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """The coach's reply, token by token, as Server-Sent Events (`docs/api/v2-coach.md`).

    Events: `slot_update`, `token`, then exactly one `done` (the turn is saved) or `error`
    (nothing was saved). `Idempotency-Key` is required: a retry with the same key and body after
    a finished turn replays it (`Idempotency-Replayed: true`) and runs nothing. Omit `text` and
    the coach speaks without a new answer: the first question of a session, or the current one
    again after a change of `language`. Closing the connection cancels the Gemini call.
    """
    if idempotency_key is None or not _KEY.match(idempotency_key):
        raise ApiError(
            400,
            "idempotency_key_invalid",
            "Send an Idempotency-Key of 16 to 64 letters, digits, - or _.",
        )
    if not _SESSION_ID.match(session_id):
        raise ApiError(404, "not_found", "Not Found")
    try:
        turn = await turns.start(user.uid, session_id, body, idempotency_key, datetime.now(UTC))
    except SessionNotFoundError as exc:
        raise ApiError(404, "not_found", "Not Found") from exc
    except SessionNotActiveError as exc:
        raise ApiError(409, "session_not_active", "This interview has ended.") from exc
    except SessionFullError as exc:
        raise ApiError(
            409, "session_full", "This conversation is too long. Start a new one."
        ) from exc
    except TurnInProgressError as exc:
        raise ApiError(
            409,
            "turn_in_progress",
            "Another message of this session is still being answered.",
            _RETRY,
        ) from exc
    except RequestInProgressError as exc:
        raise ApiError(
            409, "request_in_progress", "This message is still being answered.", _RETRY
        ) from exc
    except KeyReusedError as exc:
        raise ApiError(
            422, "idempotency_key_reused", "This Idempotency-Key was used with another message."
        ) from exc
    except TextRequiredError as exc:
        raise RequestValidationError(
            [{"type": "missing", "loc": ("body", "text"), "msg": "The message is missing."}]
        ) from exc
    headers: dict[str, Any] = dict(SSE_HEADERS)
    if isinstance(turn, ReplayTurn):
        headers["Idempotency-Replayed"] = "true"
        frames = _replayed(turn.frames)
    else:
        frames = turns.frames(turn, request_id_from_scope(request.scope))
    return StreamingResponse(with_heartbeat(frames), media_type=SSE_MEDIA_TYPE, headers=headers)
