"""Exploitation Radar report submission (NF-P3-001): steps 2 to 4 and 7 of the pipeline
(docs/mermaid/exploitation-radar-pipeline.mmd).

Steps 5 to 6 (embedding and similarity clustering) live in `clustering.py` (NF-P3-002).
Steps 8 to 9 (radar_entities risk profile and community rating, NF-P3-003) are not built yet.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.config import Settings
from app.integrations.gemini import GeminiClient, ModelTier, model_for
from app.prompts.loader import load_prompt
from app.repositories.radar_repo import RadarRepository
from app.schemas.contract import HostCountryCode
from app.schemas.radar import RadarEntityType, RadarReport, RadarValidation
from app.schemas.radar_report import (
    ExtractedEntity,
    RadarPersonalDataKind,
    RadarReportRequest,
    RadarReportResponse,
    ReportScreen,
    ViolationClassification,
)
from app.schemas.remittance_compare import CorridorId
from app.services.radar.clustering import embed_report, find_cluster
from app.utils.hashing import hash_reporter
from app.utils.slugs import slugify

logger = logging.getLogger(__name__)

# Loaded at import so a missing or malformed prompt file stops the app at startup.
EXTRACT_ENTITY_PROMPT = load_prompt("radar", "extract_entity", 1)
VALIDATE_PROMPT = load_prompt("radar", "validate", 1)
CATEGORIZE_PROMPT = load_prompt("radar", "categorize", 1)

# Above this, validate.v1's own spam_score is treated as spam: refused, never stored
# (radar.md). No demo data has calibrated a better number yet.
SPAM_SCORE_THRESHOLD = 0.7


class SpamDetectedError(Exception):
    """Step 3's `spam_score` was at or above `SPAM_SCORE_THRESHOLD`. Not stored."""

    def __init__(self, spam_score: float, reason: str) -> None:
        super().__init__(f"spam_score {spam_score:.2f}: {reason}")
        self.spam_score = spam_score
        self.reason = reason


class AbusiveContentError(Exception):
    """Step 3 found threats, hate speech or sexual content. Not stored."""


class PersonalDataError(Exception):
    """Step 3 found personal data (a phone number, an address, ...) in the free text. Not
    stored: this becomes a public community database."""

    def __init__(self, kinds: list[RadarPersonalDataKind]) -> None:
        super().__init__(f"contains personal data: {', '.join(kinds)}")
        self.kinds = kinds


class EntityUnknownError(Exception):
    """Neither the form nor step 2 could name who the report is about."""


class LocationUnknownError(Exception):
    """Neither the form nor step 2 gave a corridor or a host country."""


def _untag(raw: str, *tags: str) -> str:
    """Stop text a worker supplied from closing one of the prompt's data blocks early.

    The prompt says everything inside a block is data; a public, unmoderated report is the
    most adversarial free text this backend accepts, more so than a contract's clause text.
    """
    for tag in tags:
        raw = raw.replace(f"</{tag}", f"< /{tag}")
    return raw


def _form_json(request: RadarReportRequest) -> str:
    payload = {
        "entity_type": request.entity_type,
        "entity_name": request.entity_name,
        "corridor_id": request.corridor_id,
        "host_country": request.host_country,
    }
    return _untag(json.dumps(payload, ensure_ascii=False), "form")


def _entity_json(
    entity_type: RadarEntityType,
    entity_name: str,
    corridor_id: CorridorId | None,
    host_country: HostCountryCode | None,
) -> str:
    payload = {
        "entity_type": entity_type,
        "entity_name": entity_name,
        "corridor_id": corridor_id,
        "host_country": host_country,
    }
    return _untag(json.dumps(payload, ensure_ascii=False), "entity")


async def extract_entity(request: RadarReportRequest, gemini: GeminiClient) -> ExtractedEntity:
    """Step 2: who and where the report is about, filling gaps the form left blank."""
    return await gemini.generate_structured(
        operation=EXTRACT_ENTITY_PROMPT.key,
        tier=ModelTier.EXTRACTION,
        contents=EXTRACT_ENTITY_PROMPT.render_user(
            form_json=_form_json(request),
            report_text=_untag(request.description, "report"),
        ),
        response_model=ExtractedEntity,
        system_instruction=EXTRACT_ENTITY_PROMPT.system,
        temperature=0.0,
    )


async def screen_report(
    description: str,
    entity_type: RadarEntityType,
    entity_name: str,
    corridor_id: CorridorId | None,
    host_country: HostCountryCode | None,
    gemini: GeminiClient,
) -> ReportScreen:
    """Step 3: spam, abuse and personal-data screening."""
    return await gemini.generate_structured(
        operation=VALIDATE_PROMPT.key,
        tier=ModelTier.CLASSIFICATION,
        contents=VALIDATE_PROMPT.render_user(
            entity_json=_entity_json(entity_type, entity_name, corridor_id, host_country),
            report_text=_untag(description, "report"),
        ),
        response_model=ReportScreen,
        system_instruction=VALIDATE_PROMPT.system,
        temperature=0.0,
    )


async def classify_violation(
    description: str,
    entity_type: RadarEntityType,
    entity_name: str,
    corridor_id: CorridorId | None,
    host_country: HostCountryCode | None,
    gemini: GeminiClient,
) -> ViolationClassification:
    """Step 4: the violation type actually stored, classified fresh from the text (never the
    worker's own pick, which this endpoint does not even accept)."""
    return await gemini.generate_structured(
        operation=CATEGORIZE_PROMPT.key,
        tier=ModelTier.CLASSIFICATION,
        contents=CATEGORIZE_PROMPT.render_user(
            entity_json=_entity_json(entity_type, entity_name, corridor_id, host_country),
            report_text=_untag(description, "report"),
        ),
        response_model=ViolationClassification,
        system_instruction=CATEGORIZE_PROMPT.system,
        temperature=0.0,
    )


def _resolve_entity(
    request: RadarReportRequest, extracted: ExtractedEntity
) -> tuple[RadarEntityType, str, str]:
    """The entity actually reported: form values win when given, step 2 fills the rest.

    Returns:
        (entity_type, entity_name, entity_slug).

    Raises:
        EntityUnknownError: Neither the form nor step 2 named a business.
    """
    entity_type = request.entity_type or extracted.entity_type
    entity_name = request.entity_name or extracted.entity_name
    if entity_name is None:
        raise EntityUnknownError("no business named in the form or the report text")
    slug_source = extracted.entity_name_normalized or entity_name
    return entity_type, entity_name, slugify(slug_source)


def _resolve_location(
    request: RadarReportRequest, extracted: ExtractedEntity
) -> tuple[CorridorId | None, HostCountryCode | None]:
    """The corridor and/or host country actually reported: form values win when given.

    Raises:
        LocationUnknownError: Neither the form nor step 2 gave either one.
    """
    corridor_id = request.corridor_id or extracted.corridor_id
    host_country = request.host_country or extracted.host_country
    if corridor_id is None and host_country is None:
        raise LocationUnknownError("no corridor or host country in the form or the report text")
    return corridor_id, host_country


async def _store_embedding(
    radar: RadarRepository,
    report_id: str,
    embedding: list[float],
    report: RadarReport,
    settings: Settings,
) -> None:
    # After the report: the report is what the worker submitted, the vector only helps
    # cluster later ones. A failed write costs one future match, not the report.
    try:
        await run_in_threadpool(
            radar.create_embedding,
            report_id,
            embedding,
            model=settings.gemini_model_embedding,
            corridor_id=report.corridor_id,
            entity_type=report.entity_type,
            entity_slug=report.entity_slug,
            created_at=report.created_at,
        )
    except GoogleAPICallError:
        logger.exception("radar_embedding_store_failed report_id=%s", report_id)


async def submit_report(
    uid: str,
    request: RadarReportRequest,
    gemini: GeminiClient,
    radar: RadarRepository,
    settings: Settings,
    now: datetime,
) -> RadarReportResponse:
    """Run steps 2 to 7 and store the report. Cross-pillar Pillar 3 entry point.

    Raises:
        EntityUnknownError: No business named, by the form or by step 2.
        LocationUnknownError: No corridor or host country, by the form or by step 2.
        SpamDetectedError: Step 3's spam score was at or above the threshold; not stored.
        AbusiveContentError: Step 3 found threats, hate speech or sexual content; not stored.
        PersonalDataError: Step 3 found personal data in the free text; not stored.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    extracted = await extract_entity(request, gemini)
    entity_type, entity_name, entity_slug = _resolve_entity(request, extracted)
    corridor_id, host_country = _resolve_location(request, extracted)

    screen = await screen_report(
        request.description, entity_type, entity_name, corridor_id, host_country, gemini
    )
    if screen.spam_score >= SPAM_SCORE_THRESHOLD:
        raise SpamDetectedError(screen.spam_score, screen.reason)
    if screen.is_abusive:
        raise AbusiveContentError("contains threats, hate speech or sexual content")
    if screen.personal_data:
        raise PersonalDataError(screen.personal_data)

    classification = await classify_violation(
        request.description, entity_type, entity_name, corridor_id, host_country, gemini
    )

    report_id = radar.new_report_id()
    embedding = await embed_report(request.description, gemini)
    cluster_id = await find_cluster(embedding, corridor_id, entity_slug, report_id, radar)
    report = RadarReport(
        entity_type=entity_type,
        entity_name=entity_name,
        entity_slug=entity_slug,
        violation_type=classification.violation_type,
        corridor_id=corridor_id,
        host_country=host_country,
        description=request.description,
        language=request.language,
        cluster_id=cluster_id,
        source="user",
        reporter_hash=hash_reporter(uid, settings.radar_reporter_hash_secret.get_secret_value()),
        validation=RadarValidation(
            spam_score=screen.spam_score,
            category_confidence=classification.category_confidence,
            model=model_for(ModelTier.CLASSIFICATION, settings),
        ),
        created_at=now,
    )
    await run_in_threadpool(radar.create_report, report_id, report)
    if embedding is not None:
        await _store_embedding(radar, report_id, embedding, report, settings)
    logger.info(
        "radar_report_created slug=%s violation=%s corridor=%s country=%s",
        entity_slug,
        classification.violation_type,
        corridor_id,
        host_country,
    )
    return RadarReportResponse(
        report_id=report_id,
        entity_type=entity_type,
        entity_name=entity_name,
        violation_type=classification.violation_type,
        corridor_id=corridor_id,
        host_country=host_country,
        description=request.description,
        summary=classification.summary,
        created_at=now,
    )
