"""Exploitation Radar alert notifications (NF-P3-004): who gets told about a freshly
created alert, and in what words.

Called once per newly created alert (never for one already `active`, `alerts.py` already
deduped that). Best effort per recipient: one broken token or a Firestore hiccup for one
worker must not stop the rest of the fan-out, and never re-raises to the cron itself.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi.concurrency import run_in_threadpool
from firebase_admin.exceptions import FirebaseError  # type: ignore[import-untyped]

from app.integrations.firebase_messaging import send_push
from app.integrations.gemini import GeminiClient, GeminiError, ModelTier
from app.prompts.loader import load_prompt
from app.repositories.radar_repo import RadarRepository
from app.repositories.user_repo import UserRepository
from app.schemas.radar_alert import AlertNotificationText, RadarAlert
from app.utils.corridors import host_and_home
from app.utils.i18n import language_name

logger = logging.getLogger(__name__)

ALERT_NOTIFICATION_PROMPT = load_prompt("radar", "alert_notification", 1)

DEEP_LINK = "/radar"

# A worker can store anything in `fcm_tokens` (the profile rules only cap the list at 5), so
# what reaches the push call is untrusted. Real FCM tokens are about 160 characters.
_MAX_TOKENS = 5
_MAX_TOKEN_CHARS = 1024


def _push_tokens(profile: dict[str, Any]) -> list[str]:
    raw = profile.get("fcm_tokens")
    if not isinstance(raw, list):
        return []
    usable = [t for t in raw if isinstance(t, str) and 0 < len(t) <= _MAX_TOKEN_CHARS]
    return usable[:_MAX_TOKENS]


def _subscribed_profiles(corridor_id: str, users: UserRepository) -> dict[str, dict[str, Any]]:
    """Every profile subscribed to this corridor's alerts: uid -> profile.

    Two cohorts (users.md: "missing means all on for the user's own corridor"):
    explicit (`notification_prefs.radar_corridors` names this corridor) and default (no
    `notification_prefs` at all, or prefs that never narrowed to specific corridors, and
    the worker's own host/home country happens to form this corridor).
    """
    host_country, home_country = host_and_home(corridor_id)
    subscribed: dict[str, dict[str, Any]] = {}

    for uid, profile in users.by_host_and_home(host_country, home_country):
        prefs = profile.get("notification_prefs")
        if prefs is None or (
            prefs.get("radar_alerts") is not False and not prefs.get("radar_corridors")
        ):
            subscribed[uid] = profile

    for uid, profile in users.subscribed_to_corridor(corridor_id):
        prefs = profile.get("notification_prefs") or {}
        if prefs.get("radar_alerts") is not False:
            subscribed[uid] = profile

    return subscribed


def _untag(raw: str, tag: str) -> str:
    """Stop `entity_name` (a worker's own free text, via the original report) from closing
    the prompt's data block early."""
    return raw.replace(f"</{tag}", f"< /{tag}")


async def _text_for_language(
    alert: RadarAlert, language: str, gemini: GeminiClient
) -> AlertNotificationText:
    payload = {
        "corridor_id": alert.corridor_id,
        "entity_name": alert.entity_name,
        "violation_type": alert.violation_type,
        "report_count": alert.report_count,
        "window_days": alert.window_days,
    }
    alert_json = _untag(json.dumps(payload, ensure_ascii=False), "alert")
    return await gemini.generate_structured(
        operation=ALERT_NOTIFICATION_PROMPT.key,
        tier=ModelTier.CLASSIFICATION,
        contents=ALERT_NOTIFICATION_PROMPT.render_user(
            language=language_name(language),
            alert_json=alert_json,
        ),
        response_model=AlertNotificationText,
        system_instruction=ALERT_NOTIFICATION_PROMPT.system,
        temperature=0.3,
    )


async def notify_new_alert(
    alert_id: str,
    alert: RadarAlert,
    radar: RadarRepository,
    users: UserRepository,
    gemini: GeminiClient,
    now: datetime,
) -> int:
    """Tell every subscribed worker about one freshly created alert.

    Returns:
        Number of `users/{uid}/notifications` documents written (0 if nobody is
        subscribed, or every language's Gemini call failed).
    """
    subscribed = await run_in_threadpool(_subscribed_profiles, alert.corridor_id, users)
    if not subscribed:
        return 0

    # None marks a language whose Gemini call already failed this run, so a second worker
    # sharing that language doesn't retry the same failing call.
    texts: dict[str, AlertNotificationText | None] = {}
    sent = 0
    for uid, profile in subscribed.items():
        language = profile.get("preferred_language") or "en"
        if language not in texts:
            try:
                texts[language] = await _text_for_language(alert, language, gemini)
            except GeminiError:
                logger.exception("radar_alert_text_failed language=%s", language)
                texts[language] = None
        text = texts[language]
        if text is None:
            continue

        notification = {
            "type": "radar_alert",
            "title": text.title,
            "body": text.body,
            "language": language,
            "deep_link": DEEP_LINK,
            "source": {
                "kind": "radar_alert",
                "path": f"radar_alerts/{alert.corridor_id}/current/{alert_id}",
            },
            "read": False,
            "created_at": now,
            "schema_version": 1,
        }
        await run_in_threadpool(users.create_notification, uid, notification)
        sent += 1

        tokens = _push_tokens(profile)
        if tokens:
            try:
                invalid = await run_in_threadpool(
                    send_push, tokens, text.title, text.body, DEEP_LINK
                )
            except (ValueError, FirebaseError) as exc:
                # The in-app notification is already stored; the push is the extra. Only the
                # exception's type is logged: a message could echo the token.
                logger.warning("radar_push_failed error=%s", type(exc).__name__)
                continue
            for token in invalid:
                await run_in_threadpool(users.remove_fcm_token, uid, token)

    if sent:
        await run_in_threadpool(radar.set_alert_notified, alert.corridor_id, alert_id, now)
    return sent
