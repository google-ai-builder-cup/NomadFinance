from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.config import Settings, get_settings
from app.dependencies import get_current_user
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.schemas.contract import ContractExtractResponse
from app.schemas.user import AuthenticatedUser
from app.services.contract.extractor import NotADocumentError, extract_text
from app.utils.validators import sniff_document_mime_type

router = APIRouter(prefix="/contracts", tags=["contracts"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"description": "Empty file"},
    401: {"description": "Missing or invalid Firebase ID token"},
    413: {"description": "File larger than the upload limit (default 10 MB)"},
    415: {"description": "Not a PDF, PNG, JPEG, WebP or HEIC/HEIF file"},
    422: {"description": "No readable document in the file, or no file sent"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/extract",
    response_model=ContractExtractResponse,
    responses=_ERROR_RESPONSES,
    summary="Extract the text of an uploaded contract",
)
async def extract_contract_text(
    file: Annotated[UploadFile, File(description="Contract as PDF, PNG, JPEG, WebP or HEIC")],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ContractExtractResponse:
    """Transcribe a contract PDF or photo into text in its original language.

    The file is only held in memory for this request; nothing is stored.
    """
    # Read one byte past the limit so an oversized file is detected without loading all of it.
    data = await file.read(settings.upload_max_bytes + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty.")
    if len(data) > settings.upload_max_bytes:
        limit_mb = settings.upload_max_bytes // (1024 * 1024)
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"The file is larger than {limit_mb} MB."
        )

    mime_type = sniff_document_mime_type(data)
    if mime_type is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Upload a PDF or a photo (PNG, JPEG, WebP or HEIC).",
        )

    try:
        extracted = await extract_text(data, mime_type, gemini)
    except NotADocumentError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "No readable document found. Upload a clear photo or PDF of the contract.",
        ) from exc

    return ContractExtractResponse(
        filename=file.filename,
        mime_type=mime_type,
        size_bytes=len(data),
        page_count=extracted.page_count,
        text=extracted.text,
    )
