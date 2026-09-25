"""Process-wide Firestore client for data-scripts loaders.

No explicit credentials are passed: local dev either points FIRESTORE_EMULATOR_HOST at the
Firebase Emulator or runs `gcloud auth application-default login`; against real Firestore, the
caller's Application Default Credentials (a user account or GOOGLE_APPLICATION_CREDENTIALS
service account key) must have write access to the target project.
"""

from __future__ import annotations

import os
from functools import lru_cache

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import firestore  # type: ignore[import-untyped]
from google.cloud.firestore import Client

DEFAULT_PROJECT_ID = "nomadfinance-prod"


@lru_cache
def get_firebase_app() -> firebase_admin.App:
    """Return the process-wide Firebase Admin app, initializing it on first use."""
    project_id = os.environ.get("FIREBASE_PROJECT_ID", DEFAULT_PROJECT_ID)
    return firebase_admin.initialize_app(options={"projectId": project_id})


@lru_cache
def get_firestore_client() -> Client:
    """Return the process-wide Firestore client, honoring FIRESTORE_EMULATOR_HOST when set."""
    return firestore.client(app=get_firebase_app())  # type: ignore[no-any-return]
