from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from google.api_core.exceptions import GoogleAPICallError, NotFound

from app.integrations.cloud_storage import ExportStore
from app.repositories.fib_repo import FibRepository
from app.services.fib import exporter
from app.services.fib.exporter import (
    DOWNLOAD_NAME,
    NoExportError,
    NoProfileError,
    export_report,
    latest_report_link,
)
from app.services.fib.report_labels import LABELS
from app.services.fib.signals import NOT_SHARED, Sharing

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 2, 9, 30, 15, tzinfo=UTC)
EXPIRES = timedelta(hours=24)
NEW_PATH = "exports/u1/financial-identity-20261002T093015Z.pdf"
OLD_PATH = "exports/u1/financial-identity-20260920T020000Z.pdf"


def _profile(**overrides: Any) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "reporting_currency": "INR",
        "period_start": "2026-05-01",
        "period_end": "2026-10-01",
        "months_of_data": 6,
        "entry_counts": {"income": 1, "transfers": 1, "bills": 1, "savings": 1},
        "metrics": {},
        "narrative": {"language": "hi", "text": "पाठ", "model": "m"},
        "computed_at": datetime(2026, 10, 1, 2, tzinfo=UTC),
    }
    return profile | overrides


class FakeFib:
    def __init__(self, profile: dict[str, Any] | None, fail_update: bool = False) -> None:
        self.profile = profile
        self.fail_update = fail_update
        self.exports: list[dict[str, Any]] = []

    def get_profile(self, uid: str) -> dict[str, Any] | None:
        return self.profile

    def set_latest_export(self, uid: str, export: dict[str, Any]) -> None:
        if self.fail_update:
            raise NotFound("no profile")
        self.exports.append(export)


class FakeStore:
    def __init__(self, fail_delete: bool = False) -> None:
        self.fail_delete = fail_delete
        self.uploads: list[tuple[str, str, bytes]] = []
        self.deleted: list[str] = []
        self.signed: list[tuple[str, str, timedelta, str]] = []

    def upload(self, uid: str, filename: str, data: bytes) -> str:
        self.uploads.append((uid, filename, data))
        return f"exports/{uid}/{filename}"

    def delete(self, uid: str, path: str) -> None:
        if self.fail_delete:
            raise NotFound("gone")
        self.deleted.append(path)

    def signed_url(self, uid: str, path: str, expires: timedelta, download_name: str) -> str:
        self.signed.append((uid, path, expires, download_name))
        return f"https://signed.example/{path}"


@pytest.fixture(autouse=True)
def rendered(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the real render, so these tests need no system libraries."""
    html_seen: list[str] = []

    def fake_render(html: str) -> bytes:
        html_seen.append(html)
        return b"%PDF-1.7 fake"

    monkeypatch.setattr(exporter, "render_pdf", fake_render)
    return html_seen


async def _export(
    fib: FakeFib, store: FakeStore, holder: str | None = None, sharing: Sharing = NOT_SHARED
) -> Any:
    return await export_report(
        "u1", holder, cast(FibRepository, fib), cast(ExportStore, store), NOW, EXPIRES, sharing
    )


async def test_a_report_is_rendered_stored_recorded_and_linked(rendered: list[str]) -> None:
    fib, store = FakeFib(_profile()), FakeStore()

    response = await _export(fib, store, "Priya")

    assert store.uploads == [("u1", "financial-identity-20261002T093015Z.pdf", b"%PDF-1.7 fake")]
    assert fib.exports == [{"storage_path": NEW_PATH, "created_at": NOW}]
    assert store.signed == [("u1", NEW_PATH, EXPIRES, DOWNLOAD_NAME)]
    assert response.download_url == f"https://signed.example/{NEW_PATH}"
    assert response.expires_at == NOW + EXPIRES
    assert response.created_at == NOW
    assert response.language == "hi"
    assert response.filename == DOWNLOAD_NAME
    assert "Priya" in rendered[0]
    assert '<html lang="hi">' in rendered[0]


async def test_the_previous_export_is_deleted_after_the_new_one_is_recorded() -> None:
    fib = FakeFib(_profile(latest_export={"storage_path": OLD_PATH, "created_at": NOW}))
    store = FakeStore()

    await _export(fib, store)

    assert store.deleted == [OLD_PATH]
    assert fib.exports[0]["storage_path"] == NEW_PATH


async def test_a_first_export_deletes_nothing() -> None:
    store = FakeStore()

    await _export(FakeFib(_profile()), store)

    assert store.deleted == []


async def test_a_previous_file_that_cannot_be_deleted_does_not_fail_the_export() -> None:
    fib = FakeFib(_profile(latest_export={"storage_path": OLD_PATH, "created_at": NOW}))

    response = await _export(fib, FakeStore(fail_delete=True))

    assert response.download_url.endswith(NEW_PATH)
    assert fib.exports[0]["storage_path"] == NEW_PATH


async def test_a_failed_profile_update_removes_the_new_file_and_raises() -> None:
    fib, store = FakeFib(_profile(), fail_update=True), FakeStore()

    with pytest.raises(GoogleAPICallError):
        await _export(fib, store)

    assert store.deleted == [NEW_PATH]
    assert store.signed == []


async def test_without_a_profile_nothing_is_rendered_or_stored(rendered: list[str]) -> None:
    store = FakeStore()

    with pytest.raises(NoProfileError):
        await _export(FakeFib(None), store)

    assert rendered == []
    assert store.uploads == []


async def test_the_latest_link_does_not_render_again(rendered: list[str]) -> None:
    created = datetime(2026, 9, 20, 2, tzinfo=UTC)
    fib = FakeFib(_profile(latest_export={"storage_path": OLD_PATH, "created_at": created}))
    store = FakeStore()

    response = await latest_report_link(
        "u1", cast(FibRepository, fib), cast(ExportStore, store), NOW, EXPIRES
    )

    assert rendered == []
    assert store.uploads == []
    assert store.signed == [("u1", OLD_PATH, EXPIRES, DOWNLOAD_NAME)]
    assert response.created_at == created
    assert response.expires_at == NOW + EXPIRES
    assert response.language == "hi"


@pytest.mark.parametrize("profile", [None, _profile(), _profile(latest_export={})])
async def test_the_latest_link_needs_an_earlier_export(profile: dict[str, Any] | None) -> None:
    with pytest.raises(NoExportError):
        await latest_report_link(
            "u1",
            cast(FibRepository, FakeFib(profile)),
            cast(ExportStore, FakeStore()),
            NOW,
            EXPIRES,
        )


# --- NF-HR-001: the Coach and scam activity is printed only while it is shared -----------------

COACH = {
    "plan_id": "p1",
    "checkins_answered": 2,
    "remittance_on_track": 1,
    "savings_on_track": 1,
    "pay_on_time": 2,
    "last_checkin_at": datetime(2026, 9, 28, 9, tzinfo=UTC),
}
SCAM = {
    "window_days": 90,
    "checks": 7,
    "scams_found": 3,
    "last_check_at": datetime(2026, 9, 30, 9, tzinfo=UTC),
}


def _with_signals() -> dict[str, Any]:
    return _profile(
        coach_signal=COACH,
        scam_signal=SCAM,
        narrative={
            "language": "en",
            "text": "Report.",
            "activity_text": "Two check-ins.",
            "model": "m",
        },
    )


async def test_the_shared_activity_is_printed_and_recorded_on_the_export(
    rendered: list[str],
) -> None:
    fib = FakeFib(_with_signals())

    await _export(fib, FakeStore(), sharing=Sharing(True, True))

    assert "Activity the worker chose to share" in rendered[0]
    assert "Two check-ins." in rendered[0]
    assert fib.exports[0]["signals"] == ["coach", "scam"]


async def test_a_worker_who_stopped_sharing_gets_a_report_without_it(rendered: list[str]) -> None:
    # The stored profile still holds the signals until the next weekly recompute.
    fib = FakeFib(_with_signals())

    await _export(fib, FakeStore(), sharing=NOT_SHARED)

    assert "Activity the worker chose to share" not in rendered[0]
    assert "Two check-ins." not in rendered[0]
    assert "signals" not in fib.exports[0]
    assert fib.profile is not None and "coach_signal" in fib.profile  # not edited in place


async def test_one_signal_turned_off_removes_the_paragraph_and_that_signal(
    rendered: list[str],
) -> None:
    fib = FakeFib(_with_signals())

    await _export(fib, FakeStore(), sharing=Sharing(coach=False, scam=True))

    assert "Two check-ins." not in rendered[0]
    assert LABELS["en"]["scam_checks"] in rendered[0]
    assert LABELS["en"]["coach_checkins"] not in rendered[0]
    assert fib.exports[0]["signals"] == ["scam"]


async def test_the_latest_link_is_refused_for_a_pdf_with_activity_no_longer_shared() -> None:
    fib = FakeFib(
        _profile(latest_export={"storage_path": OLD_PATH, "created_at": NOW, "signals": ["coach"]})
    )

    with pytest.raises(NoExportError):
        await latest_report_link(
            "u1", cast(FibRepository, fib), cast(ExportStore, FakeStore()), NOW, EXPIRES, NOT_SHARED
        )


async def test_the_latest_link_is_given_while_the_activity_is_still_shared() -> None:
    fib = FakeFib(
        _profile(latest_export={"storage_path": OLD_PATH, "created_at": NOW, "signals": ["coach"]})
    )

    link = await latest_report_link(
        "u1",
        cast(FibRepository, fib),
        cast(ExportStore, FakeStore()),
        NOW,
        EXPIRES,
        Sharing(coach=True, scam=False),
    )

    assert link.download_url.endswith(OLD_PATH)


async def test_a_pdf_made_without_signals_is_always_linkable() -> None:
    fib = FakeFib(_profile(latest_export={"storage_path": OLD_PATH, "created_at": NOW}))

    link = await latest_report_link(
        "u1", cast(FibRepository, fib), cast(ExportStore, FakeStore()), NOW, EXPIRES, NOT_SHARED
    )

    assert link.download_url.endswith(OLD_PATH)
