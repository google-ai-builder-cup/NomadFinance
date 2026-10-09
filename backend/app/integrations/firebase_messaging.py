"""Firebase Cloud Messaging: push notifications for Exploitation Radar alerts (NF-P3-004) and
Coach check-in reminders (NF-FC-016)."""

from __future__ import annotations

import logging
from typing import Any

from firebase_admin import messaging  # type: ignore[import-untyped]

from app.core.security import get_firebase_app

logger = logging.getLogger(__name__)

# A worker can store anything in `fcm_tokens` (the profile rules only cap the list at 5), so
# what reaches the push call is untrusted. Real FCM tokens are about 160 characters.
_MAX_TOKENS = 5
_MAX_TOKEN_CHARS = 1024


def usable_tokens(profile: dict[str, Any]) -> list[str]:
    """The push tokens of a profile that are plausible enough to hand to FCM."""
    raw = profile.get("fcm_tokens")
    if not isinstance(raw, list):
        return []
    usable = [t for t in raw if isinstance(t, str) and 0 < len(t) <= _MAX_TOKEN_CHARS]
    return usable[:_MAX_TOKENS]


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
