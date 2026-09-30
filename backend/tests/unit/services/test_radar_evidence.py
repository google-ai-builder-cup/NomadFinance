from __future__ import annotations

from typing import Any, cast

import pytest

from app.repositories.radar_repo import RadarRepository
from app.services.radar.evidence import (
    MAX_EVIDENCE_FILES,
    NotTheReporterError,
    ReportNotFoundError,
    TooMuchEvidenceError,
    add_evidence,
)
from app.utils.hashing import hash_reporter

pytestmark = pytest.mark.anyio

SECRET = "test-secret"
UID = "worker-uid"
REPORTER_HASH = hash_reporter(UID, SECRET)


class FakeStore:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, bytes, str]] = []

    def upload(self, report_id: str, filename: str, data: bytes, content_type: str) -> str:
        self.uploads.append((report_id, filename, data, content_type))
        return f"radar-evidence/{report_id}/{filename}"


class FakeRadar:
    def __init__(self, report: dict[str, Any] | None) -> None:
        self.report = report
        self.added: list[tuple[str, str]] = []

    def get(self, report_id: str) -> dict[str, Any] | None:
        return self.report

    def add_evidence_path(self, report_id: str, path: str) -> None:
        self.added.append((report_id, path))


def _report(**over: Any) -> dict[str, Any]:
    values: dict[str, Any] = {"reporter_hash": REPORTER_HASH, "evidence_paths": []}
    return values | over


async def test_a_valid_upload_is_stored_and_recorded_on_the_report() -> None:
    radar = FakeRadar(_report())
    store = FakeStore()

    result = await add_evidence(
        UID, "r_01", "image/jpeg", b"bytes", cast(RadarRepository, radar), store, SECRET
    )

    assert result.report_id == "r_01"
    report_id, filename, data, content_type = store.uploads[0]
    assert (report_id, data, content_type) == ("r_01", b"bytes", "image/jpeg")
    assert filename.endswith(".jpg")
    assert radar.added == [("r_01", result.evidence_paths[0])]
    assert result.evidence_paths[0].startswith("radar-evidence/r_01/")


async def test_a_missing_report_is_rejected() -> None:
    radar = FakeRadar(None)

    with pytest.raises(ReportNotFoundError):
        await add_evidence(
            UID, "r_01", "image/jpeg", b"x", cast(RadarRepository, radar), FakeStore(), SECRET
        )


async def test_a_report_with_no_reporter_hash_is_rejected() -> None:
    # contract_signal / seed reports: nobody to check ownership against.
    radar = FakeRadar(_report(reporter_hash=None))

    with pytest.raises(ReportNotFoundError):
        await add_evidence(
            UID, "r_01", "image/jpeg", b"x", cast(RadarRepository, radar), FakeStore(), SECRET
        )


async def test_a_different_workers_uid_is_rejected() -> None:
    radar = FakeRadar(_report())  # reporter_hash belongs to UID

    with pytest.raises(NotTheReporterError):
        await add_evidence(
            "someone-else",
            "r_01",
            "image/jpeg",
            b"x",
            cast(RadarRepository, radar),
            FakeStore(),
            SECRET,
        )


async def test_the_original_reporter_can_add_more_than_one_file() -> None:
    radar = FakeRadar(_report(evidence_paths=["radar-evidence/r_01/a.jpg"]))
    store = FakeStore()

    result = await add_evidence(
        UID, "r_01", "image/png", b"x", cast(RadarRepository, radar), store, SECRET
    )

    assert result.evidence_paths == ["radar-evidence/r_01/a.jpg", radar.added[0][1]]


async def test_the_cap_is_enforced_before_uploading() -> None:
    radar = FakeRadar(_report(evidence_paths=[f"p{n}" for n in range(MAX_EVIDENCE_FILES)]))
    store = FakeStore()

    with pytest.raises(TooMuchEvidenceError):
        await add_evidence(
            UID, "r_01", "image/jpeg", b"x", cast(RadarRepository, radar), store, SECRET
        )

    assert store.uploads == []  # never uploaded past the cap
    assert radar.added == []


@pytest.mark.parametrize(
    ("content_type", "extension"),
    [
        ("application/pdf", "pdf"),
        ("image/png", "png"),
        ("image/jpeg", "jpg"),
        ("image/webp", "webp"),
        ("image/heic", "heic"),
        ("image/heif", "heif"),
    ],
)
async def test_every_accepted_content_type_maps_to_an_extension(
    content_type: str, extension: str
) -> None:
    radar = FakeRadar(_report())
    store = FakeStore()

    await add_evidence(UID, "r_01", content_type, b"x", cast(RadarRepository, radar), store, SECRET)

    assert store.uploads[0][1].endswith(f".{extension}")
