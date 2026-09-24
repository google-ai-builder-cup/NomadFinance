from __future__ import annotations

from unittest.mock import MagicMock

from app.repositories.base import FirestoreRepository


class _WidgetRepository(FirestoreRepository):
    collection_name = "widgets"


def test_get_returns_none_when_document_missing() -> None:
    client = MagicMock()
    snapshot = MagicMock(exists=False)
    client.collection.return_value.document.return_value.get.return_value = snapshot

    repo = _WidgetRepository(client=client)
    assert repo.get("missing-id") is None


def test_get_returns_document_data_when_present() -> None:
    client = MagicMock()
    snapshot = MagicMock(exists=True)
    snapshot.to_dict.return_value = {"name": "gadget"}
    client.collection.return_value.document.return_value.get.return_value = snapshot

    repo = _WidgetRepository(client=client)
    assert repo.get("widget-1") == {"name": "gadget"}


def test_set_writes_to_the_right_document() -> None:
    client = MagicMock()
    repo = _WidgetRepository(client=client)

    repo.set("widget-1", {"name": "gadget"}, merge=True)

    client.collection.assert_called_with("widgets")
    client.collection.return_value.document.assert_called_with("widget-1")
    client.collection.return_value.document.return_value.set.assert_called_once_with(
        {"name": "gadget"}, merge=True
    )


def test_delete_removes_the_right_document() -> None:
    client = MagicMock()
    repo = _WidgetRepository(client=client)

    repo.delete("widget-1")

    client.collection.return_value.document.return_value.delete.assert_called_once()
