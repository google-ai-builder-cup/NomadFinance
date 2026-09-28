"""Contract upload (NF-P2-007): step 1 once per file, and nothing of the file kept but text.

The same file from the same user is recognised by its SHA-256 and read only once. The file's
bytes are never stored: the blocks and text from step 1 are, in a backend-only document.
"""

from __future__ import annotations

import hashlib

from fastapi.concurrency import run_in_threadpool

from app.integrations.gemini import GeminiClient
from app.repositories.contract_repo import ContractRepository
from app.schemas.contract_pipeline import ContractUploadResponse
from app.services.contract.extractor import EXTRACT_PROMPT, extract_contract


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def upload_contract(
    uid: str,
    data: bytes,
    mime_type: str,
    filename: str | None,
    gemini: GeminiClient,
    contracts: ContractRepository,
) -> ContractUploadResponse:
    """Store a contract after step 1. The file itself is not kept, only what was read from it.

    A second upload of the same file returns the stored contract, unless it was read with an
    older extraction prompt; then it is read again into the same contract.

    Raises:
        NotADocumentError: No readable document in the file (from step 1).
        GeminiError: Any Gemini failure.
    """
    digest = content_hash(data)
    found = await run_in_threadpool(contracts.find_by_hash, uid, digest)
    if found is not None:
        contract_id, stored = found
        if stored.get("prompt_versions", {}).get(EXTRACT_PROMPT.key) == EXTRACT_PROMPT.version:
            return ContractUploadResponse(
                contract_id=contract_id,
                status=stored["status"],
                reused=True,
                page_count=stored["page_count"],
                title=stored.get("title"),
                legibility=stored["legibility"],
            )
    else:
        contract_id = await run_in_threadpool(contracts.new_id, uid)

    extracted, text = await extract_contract(data, mime_type, gemini)
    contract = {
        "status": "uploaded",
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": len(data),
        "page_count": extracted.page_count,
        "title": extracted.title,
        "legibility": extracted.legibility,
        "content_hash": digest,
        "prompt_versions": {EXTRACT_PROMPT.key: EXTRACT_PROMPT.version},
    }
    extraction = {"blocks": [block.model_dump() for block in extracted.blocks], "text": text}
    await run_in_threadpool(contracts.save_upload, uid, contract_id, contract, extraction)
    return ContractUploadResponse(
        contract_id=contract_id,
        status="uploaded",
        reused=found is not None,
        page_count=extracted.page_count,
        title=extracted.title,
        legibility=extracted.legibility,
    )
