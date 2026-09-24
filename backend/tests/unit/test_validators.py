from __future__ import annotations

import pytest

from app.utils.validators import sniff_document_mime_type


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"%PDF-1.7\n...", "application/pdf"),
        (b"\xef\xbb\xbf\n%PDF-1.4\n", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n\x00\x00", "image/png"),
        (b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg"),
        (b"RIFF\x24\x00\x00\x00WEBPVP8 ", "image/webp"),
        (b"\x00\x00\x00\x18ftypheic\x00\x00", "image/heic"),
        (b"\x00\x00\x00\x18ftypmif1\x00\x00", "image/heif"),
    ],
)
def test_detects_supported_types_from_bytes(data: bytes, expected: str) -> None:
    assert sniff_document_mime_type(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        b"plain text pretending to be a contract",
        b"PK\x03\x04 docx is a zip",
        b"GIF89a",
        b"\x00\x00\x00\x18ftypmp42",  # MP4 video shares the ftyp box with HEIC
        b"",
    ],
)
def test_rejects_everything_else(data: bytes) -> None:
    assert sniff_document_mime_type(data) is None


def test_pdf_header_after_1024_bytes_is_rejected() -> None:
    assert sniff_document_mime_type(b"x" * 1024 + b"%PDF-1.4") is None
