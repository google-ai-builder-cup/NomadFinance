"""An in-memory stand-in for the part of the Firestore client the demo loaders use."""

from __future__ import annotations

import copy
from typing import Any


class Snapshot:
    def __init__(self, ref: DocumentRef, data: dict[str, Any] | None) -> None:
        self.reference = ref
        self.id = ref.id
        self.exists = data is not None
        self._data = data

    def to_dict(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._data) if self._data is not None else None


class DocumentRef:
    def __init__(self, client: FakeClient, path: str) -> None:
        self.client = client
        self.path = path
        self.id = path.rsplit("/", 1)[-1]

    def collection(self, name: str) -> CollectionRef:
        return CollectionRef(self.client, f"{self.path}/{name}")

    def get(self) -> Snapshot:
        return Snapshot(self, self.client.store.get(self.path))

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        self.client.write(self.path, data, merge)


class _Count:
    def __init__(self, value: int) -> None:
        self.value = value


class _CountQuery:
    def __init__(self, value: int) -> None:
        self._value = value

    def get(self) -> list[list[_Count]]:
        return [[_Count(self._value)]]


class CollectionRef:
    def __init__(
        self,
        client: FakeClient,
        path: str,
        where: tuple[str, Any] | None = None,
    ) -> None:
        self.client = client
        self.path = path
        self._where = where

    def document(self, doc_id: str) -> DocumentRef:
        return DocumentRef(self.client, f"{self.path}/{doc_id}")

    def where(self, *, filter: Any) -> CollectionRef:  # noqa: A002 - the client's own keyword
        assert filter.op_string == "=="
        return CollectionRef(self.client, self.path, (filter.field_path, filter.value))

    def select(self, _fields: list[str]) -> CollectionRef:
        return self

    def stream(self) -> list[Snapshot]:
        prefix = f"{self.path}/"
        found = []
        for path, data in sorted(self.client.store.items()):
            rest = path.removeprefix(prefix)
            if not path.startswith(prefix) or "/" in rest:
                continue
            if self._where is not None and data.get(self._where[0]) != self._where[1]:
                continue
            found.append(Snapshot(DocumentRef(self.client, path), data))
        return found

    def count(self) -> _CountQuery:
        return _CountQuery(len(self.stream()))


class CollectionGroupRef:
    """Every document in a collection of this name, wherever it sits (a collection-group query)."""

    def __init__(self, client: FakeClient, name: str) -> None:
        self.client = client
        self.name = name
        self.selected: list[str] | None = None

    def select(self, fields: list[str]) -> CollectionGroupRef:
        self.selected = fields
        return self

    def stream(self) -> list[Snapshot]:
        found = []
        for path, data in sorted(self.client.store.items()):
            parts = path.split("/")
            if len(parts) % 2 == 0 and parts[-2] == self.name:
                found.append(Snapshot(DocumentRef(self.client, path), data))
        return found


class Batch:
    def __init__(self, client: FakeClient) -> None:
        self._client = client
        self._ops: list[tuple[str, str, dict[str, Any] | None, bool]] = []

    def set(self, ref: DocumentRef, data: dict[str, Any], merge: bool = False) -> None:
        self._ops.append(("set", ref.path, data, merge))

    def delete(self, ref: DocumentRef) -> None:
        self._ops.append(("delete", ref.path, None, False))

    def commit(self) -> None:
        self._client.commits += 1
        for op, path, data, merge in self._ops:
            if op == "set" and data is not None:
                self._client.write(path, data, merge)
            else:
                self._client.store.pop(path, None)


class FakeClient:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.commits = 0

    def write(self, path: str, data: dict[str, Any], merge: bool) -> None:
        stored = copy.deepcopy(data)
        if merge and path in self.store:
            self.store[path] = {**self.store[path], **stored}
        else:
            self.store[path] = stored

    def collection(self, name: str) -> CollectionRef:
        return CollectionRef(self, name)

    def document(self, path: str) -> DocumentRef:
        return DocumentRef(self, path)

    def collection_group(self, name: str) -> CollectionGroupRef:
        return CollectionGroupRef(self, name)

    def batch(self) -> Batch:
        return Batch(self)

    def put(self, path: str, data: dict[str, Any] | None = None) -> None:
        self.store[path] = data or {"x": 1}
