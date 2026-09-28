from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.v1.contract_analysis import NOT_A_DOCUMENT, read_contract_upload
from app.config import Settings, get_settings
from app.core.rate_limit import limit_ai_calls
from app.dependencies import get_current_user
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.repositories.complaint_template_repo import (
    ComplaintTemplateRepository,
    get_complaint_template_repository,
)
from app.repositories.labor_law_repo import LaborLawRepository, get_labor_law_repository
from app.schemas.contract import (
    ContractDetectRequest,
    ContractExtractResponse,
    DetectedContract,
    HostCountryCode,
    JobTypeId,
    LaborLawContext,
)
from app.schemas.contract_compare import ContractCompareRequest, ContractComparison
from app.schemas.contract_complaint import ContractComplaint, ContractComplaintRequest
from app.schemas.contract_translate import ContractReportTranslation, ContractTranslateRequest
from app.schemas.user import AuthenticatedUser
from app.services.contract.comparator import NotComparableError, NoTermsError, compare_contract
from app.services.contract.complaint import (
    ComplaintIncompleteError,
    ComplaintTemplateNotFoundError,
    NoViolationsError,
    generate_complaint,
)
from app.services.contract.detector import detect_contract
from app.services.contract.extractor import NotADocumentError, extract_contract
from app.services.contract.rag import LaborLawNotFoundError, get_labor_law_context
from app.services.contract.translator import TranslationIncompleteError, translate_report

router = APIRouter(prefix="/contracts", tags=["contracts"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"description": "Empty file"},
    401: {"description": "Missing or invalid Firebase ID token"},
    413: {"description": "File larger than the upload limit (default 10 MB)"},
    415: {"description": "Not a PDF, PNG, JPEG, WebP or HEIC/HEIF file"},
    422: {"description": "No readable document in the file, or no file sent"},
    429: {"description": "Too many uploads (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/extract",
    response_model=ContractExtractResponse,
    responses=_ERROR_RESPONSES,
    summary="Extract the text and structure of an uploaded contract",
    dependencies=[Depends(limit_ai_calls)],
)
async def extract_contract_text(
    file: Annotated[UploadFile, File(description="Contract as PDF, PNG, JPEG, WebP or HEIC")],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ContractExtractResponse:
    """Transcribe a contract PDF or photo in its original language, clause by clause.

    Returns the document as ordered blocks (headings, numbered clauses, list items, tables)
    and as plain text. A `legibility` of "poor" means the photo should be retaken. The file
    is only held in memory for this request; nothing is stored.
    """
    data, mime_type = await read_contract_upload(file, settings)
    try:
        extracted, text = await extract_contract(data, mime_type, gemini)
    except NotADocumentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NOT_A_DOCUMENT) from exc

    return ContractExtractResponse(
        filename=file.filename,
        mime_type=mime_type,
        size_bytes=len(data),
        page_count=extracted.page_count,
        title=extracted.title,
        legibility=extracted.legibility,
        text=text,
        blocks=extracted.blocks,
    )


_DETECT_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    422: {"description": "No text, or text longer than 200,000 characters"},
    429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/detect",
    response_model=DetectedContract,
    responses=_DETECT_ERROR_RESPONSES,
    summary="Detect the language, host country and kind of a contract",
    dependencies=[Depends(limit_ai_calls)],
)
async def detect_contract_facts(
    body: ContractDetectRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
) -> DetectedContract:
    """Find the contract's language, the country whose labor law applies, its kind and job type.

    Send the `text` returned by `/contracts/extract`. Also returns the employer, agency and
    salary when the document states them. `host_country` is null when the contract is for a
    country outside SG, KR, MY, JP, HK, AU or shows none: ask the worker. Nothing is stored.
    """
    return await detect_contract(body.text, gemini)


_LAW_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    404: {"description": "No curated labor-law data is loaded for this country yet"},
    429: {"description": "Too many requests (default 60 a minute); see Retry-After"},
}


@router.get(
    "/labor-law/{host_country}",
    response_model=LaborLawContext,
    responses=_LAW_ERROR_RESPONSES,
    summary="Fetch a host country's curated labor-law rules",
)
async def get_labor_law(
    host_country: HostCountryCode,
    job_type: Annotated[
        JobTypeId, Query(description="Worker's job type, to pick each rule's applicable variant.")
    ],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repo: Annotated[LaborLawRepository, Depends(get_labor_law_repository)],
) -> LaborLawContext:
    """Look up the labor law of a contract's host country. Step 3 of Contract Shield.

    Send the `host_country` and `job_type` returned by `/contracts/detect`. Returns all 15
    curated categories, each with the variant that applies to `job_type`, and the
    `law_version` a stored report would be cached against. No Gemini call; not rate-limited
    beyond the API-wide budget.
    """
    try:
        return await get_labor_law_context(host_country, job_type, repo)
    except LaborLawNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No labor-law data is available yet for {host_country}.",
        ) from exc


_COMPARE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    404: {"description": "No curated labor-law data is loaded for this country yet"},
    422: {
        "description": (
            "Not an employment contract or recruitment agreement, no term could be assessed, "
            "or an invalid body"
        )
    },
    429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/compare",
    response_model=ContractComparison,
    responses=_COMPARE_ERROR_RESPONSES,
    summary="Check each term of a contract against the host country's labor law",
    dependencies=[Depends(limit_ai_calls)],
)
async def compare_contract_terms(
    body: ContractCompareRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    repo: Annotated[LaborLawRepository, Depends(get_labor_law_repository)],
) -> ContractComparison:
    """Give every term a risk (safe, caution, danger) with a plain explanation. Step 4.

    Send the `blocks` from `/contracts/extract` and the `host_country`, `job_type` and
    `document_kind` from `/contracts/detect`. The law is fetched here, never taken from the
    request. Returns the clauses with law references, the health score, risk level and
    counts, in English (step 5 translates). Nothing is stored. Usually 20 to 35 s.
    """
    try:
        law = await get_labor_law_context(body.host_country, body.job_type, repo)
    except LaborLawNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No labor-law data is available yet for {body.host_country}.",
        ) from exc
    try:
        return await compare_contract(body.blocks, law, gemini, body.document_kind)
    except NotComparableError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The labor-law check covers employment contracts and recruitment agreements only.",
        ) from exc
    except NoTermsError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "No contract terms were found to check. Upload the full contract.",
        ) from exc


_TRANSLATE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    422: {"description": "Invalid body: empty text, no clauses, or text over the length limit"},
    429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/translate",
    response_model=ContractReportTranslation,
    responses=_TRANSLATE_ERROR_RESPONSES,
    summary="Translate a finished contract report into a worker's language",
    dependencies=[Depends(limit_ai_calls)],
)
async def translate_contract_report(
    body: ContractTranslateRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
) -> ContractReportTranslation:
    """Translate `full_text`, `summary` and each clause's text into `target_language`. Step 5.

    Send the `text` from `/contracts/extract` as `full_text`, and the `summary` and `clauses`
    from `/contracts/compare`. `category`, `risk`, `law_reference` and every number are kept
    exactly as sent; only the text fields are translated. Nothing is stored.
    """
    try:
        return await translate_report(
            body.full_text, body.summary, body.clauses, body.target_language, gemini
        )
    except TranslationIncompleteError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The AI service returned an unusable answer. Please try again.",
        ) from exc


_COMPLAINT_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    404: {"description": "No complaint template is loaded for this country yet"},
    422: {"description": "No clause with risk `danger`, or an invalid body"},
    429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/complaint",
    response_model=ContractComplaint,
    responses=_COMPLAINT_ERROR_RESPONSES,
    summary="Write the complaint letter for the clauses that break the law",
    dependencies=[Depends(limit_ai_calls)],
)
async def write_complaint_letter(
    body: ContractComplaintRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    repo: Annotated[ComplaintTemplateRepository, Depends(get_complaint_template_repository)],
) -> ContractComplaint:
    """Write a formal complaint to the host country's labor authority. Step 6.

    Send the `clauses` from `/contracts/compare` and the employer, agency and salary from
    `/contracts/detect` as `contract_facts`. Only clauses with risk `danger` go in the letter.
    `letter_text` is in the language the authority works in; `worker_copy` is the same letter
    in `worker_language`, for the worker to read (null when both are the same language). The
    worker's name, contact details and start date are left as [bracketed blanks] to fill in.
    The authority and where to send the letter come from curated data, not from Gemini.
    Nothing is stored.
    """
    try:
        return await generate_complaint(
            body.host_country,
            body.clauses,
            body.contract_facts,
            body.worker_language,
            repo,
            gemini,
        )
    except NoViolationsError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "No term of this contract was found to break the law, so there is nothing to report.",
        ) from exc
    except ComplaintTemplateNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No complaint letter is available yet for {body.host_country}.",
        ) from exc
    except ComplaintIncompleteError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The AI service returned an unusable answer. Please try again.",
        ) from exc
