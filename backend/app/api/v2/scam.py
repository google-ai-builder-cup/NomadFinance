from __future__ import annotations

import json
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from starlette.datastructures import UploadFile

from app.core.errors import ApiError
from app.dependencies import (
    get_current_user,
    get_scam_check_store,
    get_similar_scam_finder,
    require_flag,
)
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.repositories.scam_taxonomy_repo import (
    ScamTaxonomyRepository,
    get_scam_taxonomy_repository,
)
from app.schemas.scam import ScamAnalyzeResponse, ScamAnalyzeTextRequest
from app.schemas.scam_screenshot import ScamAnalyzeFormFields
from app.schemas.user import AuthenticatedUser
from app.services.scam.analyzer import analyze_screenshot, analyze_text
from app.services.scam.check_store import CheckStore
from app.services.scam.retrieval import SimilarScamFinder
from app.services.scam.screenshot import IMAGE_MIME_TYPES, MAX_IMAGE_BYTES, ImageUnreadableError
from app.utils.validators import sniff_document_mime_type

ModelT = TypeVar("ModelT", bound=BaseModel)

# The flag guard also verifies the token, so a missing token is a 401 before anything else
# and a caller without the flag gets the same 404 an unknown path does (docs/api/v2-scam.md).
router = APIRouter(prefix="/scam", tags=["scam"], dependencies=[Depends(require_flag("scam"))])

_UNSUPPORTED_MEDIA = "Send the message as text, or the screenshot as a JPEG, PNG or WebP image."
_IMAGE_UNREADABLE = (
    "No message text could be read from this image. Try a clearer screenshot or paste the text."
)

_ANALYZE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing, invalid, expired or revoked token"},
    404: {"description": "The `scam` flag is off for the caller"},
    413: {"description": "Image over 5 MB (`payload_too_large`)"},
    415: {"description": "Body is neither JSON nor a form, or the image is not JPEG, PNG or WebP"},
    422: {
        "description": "Empty text, text over 4,000 characters, a language outside the six, no "
        "image, or no message text could be read from the image (`image_unreadable`)"
    },
    429: {
        "description": "The worker has used 20 checks that call Gemini this hour (a repeated "
        "message answered from storage does not count), or 60 calls a minute; see Retry-After"
    },
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}

# One path takes two kinds of body, so FastAPI cannot derive the request body from a parameter.
_ANALYZE_REQUEST_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": ScamAnalyzeTextRequest.model_json_schema()},
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["image", "language"],
                    "properties": {
                        "image": {
                            "type": "string",
                            "format": "binary",
                            "description": "JPEG, PNG or WebP screenshot, at most 5 MB",
                        },
                        **ScamAnalyzeFormFields.model_json_schema()["properties"],
                    },
                }
            },
        },
    }
}


def _invalid(exc: ValidationError) -> RequestValidationError:
    """The standard 422 for a body that failed a model, with each field named as `body.<name>`."""
    return RequestValidationError(
        [{**error, "loc": ("body", *error["loc"])} for error in exc.errors()]
    )


def _field_error(message: str, name: str | None = None) -> RequestValidationError:
    loc = ("body", name) if name else ("body",)
    return RequestValidationError([{"type": "value_error", "loc": loc, "msg": message}])


def _validated(model: type[ModelT], payload: object) -> ModelT:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise _invalid(exc) from exc


async def _text_request(request: Request) -> ScamAnalyzeTextRequest:
    try:
        payload = json.loads(await request.body())
    except ValueError as exc:  # bad JSON or bad UTF-8
        raise _field_error("The body is not valid JSON.") from exc
    return _validated(ScamAnalyzeTextRequest, payload)


async def _screenshot_request(request: Request) -> tuple[bytes, ScamAnalyzeFormFields]:
    """The image bytes and form fields of a multipart body, checked from cheapest to dearest."""
    form = await request.form()
    try:
        fields = _validated(
            ScamAnalyzeFormFields,
            {"language": form.get("language"), "corridor_id": form.get("corridor_id") or None},
        )
        upload = form.get("image")
        if not isinstance(upload, UploadFile):
            raise _field_error("A screenshot is required in the `image` field.", "image")
        # One byte past the limit shows it is too big without reading all of it.
        data = await upload.read(MAX_IMAGE_BYTES + 1)
    finally:
        await form.close()
    if not data:
        raise _field_error("The image file is empty.", "image")
    if len(data) > MAX_IMAGE_BYTES:
        raise ApiError(413, "payload_too_large", "The image is larger than 5 MB.")
    # What the file's bytes are, not what the client says: filename and Content-Type can lie.
    if sniff_document_mime_type(data) not in IMAGE_MIME_TYPES:
        raise ApiError(415, "unsupported_media_type", _UNSUPPORTED_MEDIA)
    return data, fields


@router.post(
    "/analyze",
    response_model=ScamAnalyzeResponse,
    responses=_ANALYZE_RESPONSES,
    summary="Check a pasted message or a screenshot for a scam",
    openapi_extra=_ANALYZE_REQUEST_BODY,
)
async def analyze_scam_message(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    taxonomy_repo: Annotated[ScamTaxonomyRepository, Depends(get_scam_taxonomy_repository)],
    finder: Annotated[SimilarScamFinder, Depends(get_similar_scam_finder)],
    store: Annotated[CheckStore, Depends(get_scam_check_store)],
) -> ScamAnalyzeResponse:
    """Say whether a message is a scam, of which type, how risky, and which words gave it away.

    Send the message as JSON (`text`, `language`, `corridor_id`), or a screenshot as
    `multipart/form-data` (`image`, `language`, `corridor_id`). The message is masked (phone
    numbers, emails, IDs, accounts, links) before anything else happens, and only the masked
    text is returned. Its content is data: instructions inside it are never followed. A
    screenshot is read once and discarded; it is never stored. A scam also gets an explainer
    in the worker's language, and up to three known scams and Radar reports it resembles
    (`similar`, `corridor_report_count`); if either cannot be made it is left empty and the
    verdict is still returned.

    The masked text is stored as the worker's check and found again by its hash: the same
    message in the same language is answered from storage (`cached: true`) with no Gemini call
    and no use of the hourly budget. A new message spends one of the worker's 20 checks an
    hour; a screenshot always does, because it is read by Gemini first.
    """
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type == "application/json":
        return await analyze_text(
            await _text_request(request), user.uid, gemini, taxonomy_repo, finder, store
        )
    if content_type == "multipart/form-data":
        image, fields = await _screenshot_request(request)
        try:
            return await analyze_screenshot(
                image, fields, user.uid, gemini, taxonomy_repo, finder, store
            )
        except ImageUnreadableError as exc:
            raise ApiError(422, "image_unreadable", _IMAGE_UNREADABLE) from exc
    raise ApiError(415, "unsupported_media_type", _UNSUPPORTED_MEDIA)
