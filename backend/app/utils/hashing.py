from __future__ import annotations

import hashlib


def hash_user_id(uid: str) -> str:
    """Return a short, stable stand-in for a Firebase uid so log lines can be correlated.

    Unsalted on purpose: uids are random, so the hash cannot be reversed, and a salt would
    be one more secret to manage. It links a person's log lines; it does not identify them.
    """
    return hashlib.sha256(uid.encode()).hexdigest()[:16]
