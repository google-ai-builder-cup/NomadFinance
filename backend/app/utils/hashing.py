from __future__ import annotations

import hashlib
import hmac


def hash_user_id(uid: str) -> str:
    """Return a short, stable stand-in for a Firebase uid so log lines can be correlated.

    Unsalted on purpose: uids are random, so the hash cannot be reversed, and a salt would
    be one more secret to manage. It links a person's log lines; it does not identify them.
    """
    return hashlib.sha256(uid.encode()).hexdigest()[:16]


def hash_reporter(uid: str, secret: str) -> str:
    """`radar_reports.reporter_hash` (radar.md): HMAC-SHA-256 of a uid, never the uid itself.

    Keyed, unlike `hash_user_id`: a report is public-adjacent (read through the API by
    anyone building on it), so it must not be feasible to search for a known uid's hash
    without the secret, the way an unsalted hash would allow.
    """
    return hmac.new(secret.encode(), uid.encode(), hashlib.sha256).hexdigest()
