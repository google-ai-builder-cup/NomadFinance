"""Firebase Cloud Messaging: push notifications for Exploitation Radar alerts (NF-P3-004)."""

from __future__ import annotations

import logging

from firebase_admin import messaging  # type: ignore[import-untyped]

from app.core.security import get_firebase_app

logger = logging.getLogger(__name__)


def send_push(tokens: list[str], title: str, body: str, deep_link: str) -> list[str]:
    """Push one notification to every token; return the ones FCM reports gone for good.

    Args:
        tokens: The recipient's FCM tokens (a worker may have several browsers).
        title, body: Already written in the recipient's language.
        deep_link: In-app path opened on tap, sent as data (the client reads it itself; a
            webpush message has no server-side click action to set here).

    Returns:
        Tokens that failed with `UnregisteredError` — the caller should remove these
        (`UserRepository.remove_fcm_token`) so the list doesn't grow forever. A token that
        failed for another reason (quota, a transient error) is left alone.
    """
    if not tokens:
        return []
    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data={"deep_link": deep_link},
    )
    response = messaging.send_each_for_multicast(message, app=get_firebase_app())
    invalid: list[str] = []
    for token, result in zip(tokens, response.responses, strict=True):
        if result.success:
            continue
        if isinstance(result.exception, messaging.UnregisteredError):
            invalid.append(token)
        else:
            logger.warning("fcm_send_failed error=%s", type(result.exception).__name__)
    return invalid
