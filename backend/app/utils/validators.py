from __future__ import annotations

# ISO base media "ftyp" brands used by phone cameras (iPhone photos are HEIC).
_HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"hevx"}
_HEIF_BRANDS = {b"mif1", b"msf1"}


def sniff_document_mime_type(data: bytes) -> str | None:
    """Return the document MIME type implied by a file's leading bytes.

    The filename and Content-Type header come from the client and can't be trusted,
    so uploads are classified by their signature instead.

    Returns:
        One of application/pdf, image/png, image/jpeg, image/webp, image/heic,
        image/heif; or None for anything else.
    """
    # The PDF spec lets the header start anywhere in the first 1024 bytes.
    if b"%PDF-" in data[:1024]:
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in _HEIC_BRANDS:
            return "image/heic"
        if brand in _HEIF_BRANDS:
            return "image/heif"
    return None
