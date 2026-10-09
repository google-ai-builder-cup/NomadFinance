from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from google.cloud.firestore import (
    DELETE_FIELD,
    SERVER_TIMESTAMP,
    ArrayUnion,
    Client,
    CollectionReference,
    DocumentReference,
    FieldFilter,
    Query,
    Transaction,
    transactional,
)

from app.repositories.base import get_firestore_client

SCHEMA_VERSION = 1


class ContractRepository:
    """users/{uid}/contracts/{id} with its `extraction/current` and `reports/{lang}` documents.

    See docs/data-model/collections/contracts.md. Only the backend writes here; the owner reads
    the contract and its reports straight from Firestore (firestore.rules). `extraction` is
    backend-only: the rules deny subcollections they do not name.
    """

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    def _contracts(self, uid: str) -> CollectionReference:
        contracts: CollectionReference = (
            self._client.collection("users").document(uid).collection("contracts")
        )
        return contracts

    def _contract(self, uid: str, contract_id: str) -> DocumentReference:
        return self._contracts(uid).document(contract_id)

    def new_id(self, uid: str) -> str:
        return str(self._contracts(uid).document().id)

    def get(self, uid: str, contract_id: str) -> dict[str, Any] | None:
        snapshot = self._contract(uid, contract_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def recent(self, uid: str, limit: int) -> list[tuple[str, dict[str, Any]]]:
        """The worker's newest contracts as `(id, data)`, newest first (one field ordered, so no
        composite index)."""
        query = self._contracts(uid).order_by("created_at", direction=Query.DESCENDING)
        return [(str(s.id), s.to_dict() or {}) for s in query.limit(limit).stream()]

    def find_by_hash(self, uid: str, content_hash: str) -> tuple[str, dict[str, Any]] | None:
        """This user's contract with these file bytes, if they uploaded the same file before."""
        query = self._contracts(uid).where(filter=FieldFilter("content_hash", "==", content_hash))
        for snapshot in query.limit(1).stream():
            return str(snapshot.id), snapshot.to_dict() or {}
        return None

    def save_upload(
        self, uid: str, contract_id: str, contract: dict[str, Any], extraction: dict[str, Any]
    ) -> None:
        """Write the contract and its extraction together, replacing any earlier upload."""
        ref = self._contract(uid, contract_id)
        batch = self._client.batch()
        batch.set(
            ref,
            contract
            | {
                "created_at": SERVER_TIMESTAMP,
                "updated_at": SERVER_TIMESTAMP,
                "schema_version": SCHEMA_VERSION,
            },
        )
        batch.set(
            ref.collection("extraction").document("current"),
            extraction | {"created_at": SERVER_TIMESTAMP, "schema_version": SCHEMA_VERSION},
        )
        batch.commit()

    def get_extraction(self, uid: str, contract_id: str) -> dict[str, Any] | None:
        snapshot = (
            self._contract(uid, contract_id).collection("extraction").document("current").get()
        )
        return snapshot.to_dict() if snapshot.exists else None

    def update(self, uid: str, contract_id: str, changes: dict[str, Any]) -> None:
        """Update fields; a value of None removes the field."""
        data = {key: DELETE_FIELD if value is None else value for key, value in changes.items()}
        self._contract(uid, contract_id).update(data | {"updated_at": SERVER_TIMESTAMP})

    def claim_for_analysis(self, uid: str, contract_id: str, stale_after: timedelta) -> bool:
        """Mark the contract `processing`, unless another analysis of it is still running.

        A `processing` contract not updated for `stale_after` counts as abandoned (the request
        died), so the claim succeeds. Returns False when the contract is busy.
        """
        ref = self._contract(uid, contract_id)

        @transactional
        def claim(transaction: Transaction) -> bool:
            data = ref.get(transaction=transaction).to_dict() or {}
            updated = data.get("updated_at")
            if data.get("status") == "processing" and isinstance(updated, datetime):
                if datetime.now(UTC) - updated < stale_after:
                    return False
            transaction.update(
                ref,
                {
                    "status": "processing",
                    "step": "detect",
                    "error": DELETE_FIELD,
                    "updated_at": SERVER_TIMESTAMP,
                },
            )
            return True

        return bool(claim(self._client.transaction()))

    def get_report(self, uid: str, contract_id: str, language: str) -> dict[str, Any] | None:
        snapshot = self._contract(uid, contract_id).collection("reports").document(language).get()
        return snapshot.to_dict() if snapshot.exists else None

    def save_report(self, uid: str, contract_id: str, report: dict[str, Any]) -> None:
        """Write `reports/{language}` and list the language on the contract."""
        ref = self._contract(uid, contract_id)
        language = report["language"]
        batch = self._client.batch()
        batch.set(
            ref.collection("reports").document(language), report | {"created_at": SERVER_TIMESTAMP}
        )
        batch.update(
            ref, {"report_languages": ArrayUnion([language]), "updated_at": SERVER_TIMESTAMP}
        )
        batch.commit()


@lru_cache
def get_contract_repository() -> ContractRepository:
    return ContractRepository(get_firestore_client())
