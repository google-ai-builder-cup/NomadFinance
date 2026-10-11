from __future__ import annotations

from functools import lru_cache

from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import GoogleAuthError
from google.cloud.firestore import SERVER_TIMESTAMP, Client, DocumentReference, Increment

from app.integrations.gemini.budget import DayUsage, UsageStoreError
from app.repositories.base import get_firestore_client

SCHEMA_VERSION = 1
_STORE_ERRORS = (GoogleAPIError, GoogleAuthError)


class GeminiUsageRepository:
    """`gemini_usage/{YYYY-MM-DD}`: the Gemini requests made on one quota day (Pacific).

    One document per day, `calls.<feature>.<tier>` counted with server-side increments so two
    Cloud Run instances never overwrite each other, and `exhausted.<tier>` set when Google
    answered a per-day 429 for that tier's model. Backend only: no client rule matches the
    collection. It implements the budget's `UsageStore`, turning every Firestore or credential
    failure into a `UsageStoreError`, which the budget treats as "carry on with my own count".
    """

    collection_name = "gemini_usage"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    def _document(self, day: str) -> DocumentReference:
        # The client is looked up on first use, so a missing credential is a `UsageStoreError`
        # on the first request, not an error when the app builds its Gemini client.
        client = self._client or get_firestore_client()
        return client.collection(self.collection_name).document(day)

    def read(self, day: str) -> DayUsage:
        try:
            snapshot = self._document(day).get()
        except _STORE_ERRORS as exc:
            raise UsageStoreError(type(exc).__name__) from exc
        data = snapshot.to_dict() or {}
        calls = {
            (feature, tier): count
            for feature, tiers in (data.get("calls") or {}).items()
            for tier, count in tiers.items()
            if isinstance(count, int)
        }
        return DayUsage(calls=calls, exhausted=set((data.get("exhausted") or {}).keys()))

    def add(self, day: str, feature: str, tier: str, count: int) -> None:
        self._write(day, {"calls": {feature: {tier: Increment(count)}}})

    def mark_exhausted(self, day: str, tier: str) -> None:
        self._write(day, {"exhausted": {tier: SERVER_TIMESTAMP}})

    def _write(self, day: str, fields: dict[str, object]) -> None:
        document = {**fields, "updated_at": SERVER_TIMESTAMP, "schema_version": SCHEMA_VERSION}
        try:
            self._document(day).set(document, merge=True)
        except _STORE_ERRORS as exc:
            raise UsageStoreError(type(exc).__name__) from exc


@lru_cache
def get_gemini_usage_repository() -> GeminiUsageRepository:
    return GeminiUsageRepository()
