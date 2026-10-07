"""Scam Analyzer step 2 (NF-SA-008): from a screenshot to the message text and its sender.

The image lives in memory for this request only. It is shrunk, sent to Gemini Vision once and
dropped; nothing in this module writes it anywhere or logs what it shows.
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass

from fastapi.concurrency import run_in_threadpool
from google.genai import types
from PIL import Image, ImageOps, UnidentifiedImageError

from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.scam import ScamIndicator
from app.schemas.scam_screenshot import ScreenshotReading

logger = logging.getLogger(__name__)

# Loaded at import so a missing or malformed prompt file stops the app at startup.
READ_PROMPT = load_prompt("scam", "read_screenshot", 1)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
# What `sniff_document_mime_type` can say about a screenshot we accept. HEIC is left out: Pillow
# cannot read it without another dependency (v2-scam.md, open point 2).
IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

# A phone screenshot is about 1200 x 2600; text stays readable well below this, and Gemini
# downsizes larger images itself, so more pixels only cost upload time.
_MAX_SIDE = 2048
# A 5 MB file can hold a far larger picture (a blank PNG compresses to almost nothing), and
# decoding it would take hundreds of MB of memory.
_MAX_PIXELS = 40_000_000
_JPEG_QUALITY = 85
_MAX_SENDER_CHARS = 254


class ImageUnreadableError(Exception):
    """No message text could be read: a broken file, not a message, or nothing legible."""


@dataclass(frozen=True)
class ScreenshotMessage:
    """What a screenshot said: the message as written, and who it came from if shown."""

    text: str
    sender: ScamIndicator | None


def prepare_image(data: bytes) -> bytes:
    """Fix orientation, flatten transparency, shrink, and re-encode as JPEG.

    Re-encoding also drops the metadata (location, device) a photo carries.

    Raises:
        ImageUnreadableError: Not an image Pillow can decode, or a picture too large to decode.
    """
    try:
        with Image.open(io.BytesIO(data)) as opened:
            # The header gives the size without decoding the pixels.
            if opened.width * opened.height > _MAX_PIXELS:
                raise ImageUnreadableError("The image has too many pixels")
            upright = ImageOps.exif_transpose(opened)
            rgba = upright.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        flat.thumbnail((_MAX_SIDE, _MAX_SIDE), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        flat.save(out, format="JPEG", quality=_JPEG_QUALITY)
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        EOFError,
        SyntaxError,
        ValueError,
    ) as exc:
        # Pillow signals a corrupt file with any of these, depending on the format. A cut-off
        # one may decode as far as it goes: weasyprint enables that process-wide.
        raise ImageUnreadableError("The file could not be decoded as an image") from exc
    return out.getvalue()


def _sender_indicator(raw: str | None) -> ScamIndicator | None:
    value = (raw or "").strip()[:_MAX_SENDER_CHARS].strip()
    if not value:
        return None
    # The data model's key of an indicator: SHA-256 of `kind:value` in normal form (a sender is
    # lowercased and trimmed); the id is its first 8 hex characters.
    key = hashlib.sha256(f"sender:{value.lower()}".encode()).hexdigest()
    return ScamIndicator(id=key[:8], kind="sender", value=value, flags=[], imitates=None, seen=None)


async def read_screenshot_message(data: bytes, gemini: GeminiClient) -> ScreenshotMessage:
    """Read the message and sender out of a screenshot.

    Args:
        data: The uploaded file, already known to be a JPEG, PNG or WebP of at most 5 MB.
        gemini: Client for the extraction-tier Vision call.

    Raises:
        ImageUnreadableError: The file is not a decodable image, or shows no message text.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    jpeg = await run_in_threadpool(prepare_image, data)
    # Annotated: with Pillow installed mypy would infer list[object].
    contents: list[types.PartUnion] = [
        types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"),
        READ_PROMPT.render_user(),
    ]
    reading = await gemini.generate_structured(
        operation=READ_PROMPT.key,
        tier=ModelTier.EXTRACTION,
        contents=contents,
        response_model=ScreenshotReading,
        system_instruction=READ_PROMPT.system,
        # Transcription: the same screenshot should always give the same text.
        temperature=0.0,
    )
    text = (reading.message_text or "").strip()
    if not reading.is_message or not text:
        raise ImageUnreadableError("No message text was read from the image")
    sender = _sender_indicator(reading.sender)
    logger.info(
        "scam_screenshot_read image_bytes=%d sent_bytes=%d text_chars=%d has_sender=%s",
        len(data),
        len(jpeg),
        len(text),
        sender is not None,
    )
    return ScreenshotMessage(text=text, sender=sender)
