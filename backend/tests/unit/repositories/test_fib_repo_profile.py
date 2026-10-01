from __future__ import annotations

from unittest.mock import MagicMock

from app.repositories.fib_repo import FibRepository
from app.repositories.user_repo import UserRepository


def _profile_document(client: MagicMock) -> MagicMock:
    """The mock at users/{uid}/financial_profile/current."""
    users = client.collection.return_value
    return users.document.return_value.collection.return_value.document.return_value  # type: ignore[no-any-return]


def test_the_profile_is_written_to_financial_profile_current() -> None:
    client = MagicMock()
    _profile_document(client).get.return_value = MagicMock(exists=False)

    FibRepository(client).save_profile("u1", {"overall_score": 80})

    client.collection.assert_called_with("users")
    client.collection.return_value.document.assert_called_with("u1")
    client.collection.return_value.document.return_value.collection.assert_called_with(
        "financial_profile"
    )
    _profile_document(client).set.assert_called_once_with(
        {"overall_score": 80, "schema_version": 1}
    )


def test_saving_replaces_the_old_profile_but_keeps_the_pdf_export() -> None:
    client = MagicMock()
    document = _profile_document(client)
    document.get.return_value = MagicMock(exists=True)
    document.get.return_value.to_dict.return_value = {
        "overall_score": 50,
        "verified_employment": [{"contract_ref": "c1"}],
        "latest_export": {"storage_path": "exports/u1/report.pdf"},
    }

    FibRepository(client).save_profile("u1", {"overall_score": 80})

    document.set.assert_called_once_with(
        {
            "overall_score": 80,
            "latest_export": {"storage_path": "exports/u1/report.pdf"},
            "schema_version": 1,
        }
    )


def test_get_profile_is_none_before_the_first_recompute() -> None:
    client = MagicMock()
    _profile_document(client).get.return_value = MagicMock(exists=False)

    assert FibRepository(client).get_profile("u1") is None


def test_list_user_ids_reads_ids_only() -> None:
    client = MagicMock()
    docs = [MagicMock(id="u1"), MagicMock(id="u2")]
    client.collection.return_value.select.return_value.stream.return_value = docs

    assert UserRepository(client).list_user_ids() == ["u1", "u2"]
    client.collection.return_value.select.assert_called_once_with([])


def test_the_latest_export_is_set_on_the_profile_without_touching_the_rest() -> None:
    client = MagicMock()
    export = {"storage_path": "exports/u1/financial-identity-20261002T093015Z.pdf"}

    FibRepository(client).set_latest_export("u1", export)

    _profile_document(client).update.assert_called_once_with({"latest_export": export})
    _profile_document(client).set.assert_not_called()
