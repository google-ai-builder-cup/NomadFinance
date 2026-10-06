from __future__ import annotations

import pytest
from google.auth.credentials import AnonymousCredentials

from app.config import _EMULATOR_VARIABLES
from app.core.security import _credential, _EmulatorCredential


@pytest.fixture(autouse=True)
def _no_emulator(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _EMULATOR_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_without_an_emulator_firebase_admin_keeps_application_default_credentials() -> None:
    # None means "let firebase-admin look up ADC", which is what Cloud Run supplies.
    assert _credential() is None


@pytest.mark.parametrize("variable", _EMULATOR_VARIABLES)
def test_an_emulator_variable_swaps_in_an_anonymous_credential(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "127.0.0.1:8085")

    credential = _credential()

    assert isinstance(credential, _EmulatorCredential)
    assert isinstance(credential.get_credential(), AnonymousCredentials)


def test_an_empty_emulator_variable_does_not_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "")

    assert _credential() is None
