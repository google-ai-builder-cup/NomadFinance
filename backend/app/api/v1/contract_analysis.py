"""Contract Shield as the app uses it (NF-P2-007): upload, analyze, report in a language.

The per-step endpoints in contracts.py stay for testing; these store every result under
users/{uid}/contracts/{id}, which the app reads (and watches for progress) in Firestore.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Path, UploadFile, status

from app.config import Settings, get_settings
from app.core.rate_limit import limit_ai_calls
from app.dependencies import get_current_user
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.repositories.complaint_template_repo import (
    ComplaintTemplateRepository,
    get_complaint_template_repository,
)
from app.repositories.contract_repo import ContractRepository, get_contract_repository
from app.repositories.labor_law_repo import LaborLawRepository, get_labor_law_repository
from app.repositories.radar_repo import RadarRepository, get_radar_repository
from app.repositories.user_repo import UserRepository, get_user_repository
from app.schemas.contract import ReportLanguage
from app.schemas.contract_pipeline import (
    AnalyzeRequest,
    ContractAnalysis,
    ContractReport,
    ContractUploadResponse,
    PipelineErrorCode,
)
from app.schemas.user import AuthenticatedUser
from app.services.contract.extractor import NotADocumentError
from app.services.contract.pipeline import (
    AnalysisInProgressError,
    PipelineDeps,
    PipelineStopError,
    analyze_contract,
)
from app.services.contract.report_store import (
    ContractNotFoundError,
    ReportNotReadyError,
    ensure_report,
)
from app.services.contract.translator import TranslationIncompleteError
from app.services.contract.upload import upload_contract
from app.utils.validators import sniff_document_mime_type

router = APIRouter(prefix="/contracts", tags=["contracts"])

NOT_A_DOCUMENT = "No readable document found. Upload a clear photo or PDF of the contract."
# Firestore's auto ids: 20 letters and digits. Anything else cannot be a contract of ours.
ContractId = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{20}$", description="The contract's id.")]

# What the worker can do about each stop; the code is also stored on the contract.
_STOP_RESPONSES: dict[PipelineErrorCode, tuple[int, str]] = {
    "poor_legibility": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The contract is too hard to read. Take a clearer photo in good light, whole page in view.",
    ),
    "country_unknown": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Choose the country where you work, then try again.",
    ),
    "not_employment_contract": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The labor-law check covers employment contracts and recruitment agreements only.",
    ),
    "no_law_data": (
        status.HTTP_404_NOT_FOUND,
        "Labor-law data for this country is not available yet.",
    ),
    "no_terms": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "No contract terms were found to check. Upload the full contract.",
    ),
}
_COMMON_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy, unavailable or out of quota; see Retry-After"},
    504: {"description": "Gemini timed out"},
}


async def read_contract_upload(file: UploadFile, settings: Settings) -> tuple[bytes, str]:
    """The uploaded bytes and their real type, or the HTTP error for a file we cannot take."""
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
    return data, mime_type


def get_pipeline_deps(
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    contracts: Annotated[ContractRepository, Depends(get_contract_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    laws: Annotated[LaborLawRepository, Depends(get_labor_law_repository)],
    templates: Annotated[ComplaintTemplateRepository, Depends(get_complaint_template_repository)],
    radar: Annotated[RadarRepository, Depends(get_radar_repository)],
) -> PipelineDeps:
    return PipelineDeps(gemini, contracts, users, laws, templates, radar)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ContractUploadResponse,
    responses=_COMMON_RESPONSES
    | {
        400: {"description": "Empty file"},
        413: {"description": "File larger than the upload limit (default 10 MB)"},
        415: {"description": "Not a PDF, PNG, JPEG, WebP or HEIC/HEIF file"},
        422: {"description": "No readable document in the file"},
    },
    summary="Upload a contract: read it (step 1) and store it",
    dependencies=[Depends(limit_ai_calls)],
)
async def upload(
    file: Annotated[UploadFile, File(description="Contract as PDF, PNG, JPEG, WebP or HEIC")],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    contracts: Annotated[ContractRepository, Depends(get_contract_repository)],
) -> ContractUploadResponse:
    """Read the contract and store it as `users/{uid}/contracts/{contract_id}`.

    Usually 3 to 40 s. The same file uploaded again by the same user returns the stored
    contract (`reused`). The file itself is not kept, only what was read from it. Next: call
    `/contracts/{contract_id}/analyze`, unless `legibility` is `poor` (ask for a new photo).
    """
    data, mime_type = await read_contract_upload(file, settings)
    try:
        return await upload_contract(user.uid, data, mime_type, file.filename, gemini, contracts)
    except NotADocumentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NOT_A_DOCUMENT) from exc


@router.post(
    "/{contract_id}/analyze",
    response_model=ContractAnalysis,
    responses=_COMMON_RESPONSES
    | {
        404: {"description": "No such contract, or no labor-law data for its country"},
        409: {"description": "This contract is being analysed by another request"},
        422: {"description": "Unreadable, no country, not an employment contract, no terms"},
    },
    summary="Analyse a stored contract: steps 2 to 6, results stored",
    dependencies=[Depends(limit_ai_calls)],
)
async def analyze(
    contract_id: ContractId,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    deps: Annotated[PipelineDeps, Depends(get_pipeline_deps)],
    body: Annotated[AnalyzeRequest | None, Body()] = None,
) -> ContractAnalysis:
    """Check the contract against the host country's labor law and store the reports.

    Usually 30 s to 2 minutes. While it runs, `status` is `processing` and `step` names the
    current step on the contract document, for the app to show progress. The English report
    and the worker's language report are stored under `reports/`. A stored analysis that is
    still current is returned at once (`cached`). On failure, `status` is `failed` and
    `error` holds `{step, code}`.
    """
    try:
        return await analyze_contract(user.uid, contract_id, body or AnalyzeRequest(), deps)
    except ContractNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such contract.") from exc
    except AnalysisInProgressError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This contract is already being analysed. Please wait."
        ) from exc
    except PipelineStopError as exc:
        status_code, detail = _STOP_RESPONSES.get(
            exc.code, (status.HTTP_500_INTERNAL_SERVER_ERROR, "The analysis failed.")
        )
        raise HTTPException(status_code, detail) from exc
    except TranslationIncompleteError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The translation was incomplete. Please try again.",
        ) from exc


@router.post(
    "/{contract_id}/reports/{language}",
    response_model=ContractReport,
    responses=_COMMON_RESPONSES
    | {
        404: {"description": "No such contract"},
        409: {"description": "The contract has no current analysis yet: analyze it first"},
    },
    summary="The report in a language: stored, or translated once and stored",
    dependencies=[Depends(limit_ai_calls)],
)
async def report_in_language(
    contract_id: ContractId,
    language: ReportLanguage,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    deps: Annotated[PipelineDeps, Depends(get_pipeline_deps)],
) -> ContractReport:
    """Switch a report's language without uploading again.

    A stored, current report is returned at once; otherwise the English report is translated
    (a few seconds), stored under `reports/{language}` and returned.
    """
    try:
        return await ensure_report(
            deps.contracts, deps.laws, deps.gemini, user.uid, contract_id, language
        )
    except ContractNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such contract.") from exc
    except ReportNotReadyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This contract has not been analysed yet."
        ) from exc
    except TranslationIncompleteError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The translation was incomplete. Please try again.",
        ) from exc
