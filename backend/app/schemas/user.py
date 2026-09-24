from __future__ import annotations

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Identity decoded from a verified Firebase Auth ID token.

    Not the Firestore user profile (home_country, host_country, job_type, ...) —
    that schema lands with the onboarding flow (NF-P1-022).
    """

    uid: str
    email: str | None = None
    email_verified: bool = False
    phone_number: str | None = None
    name: str | None = None
    picture: str | None = None
