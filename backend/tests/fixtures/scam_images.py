"""Synthetic screenshots for the Scam Analyzer's tests (NF-SA-008).

Drawn with Pillow from invented messages: no real worker's screen, no real chat. The drawing
uses Pillow's built-in font, which covers Latin text only, so the language cases are English,
Tagalog and Indonesian.
"""

from __future__ import annotations

import io
from typing import Any, Literal

from PIL import Image, ImageDraw

ImageFormat = Literal["PNG", "JPEG", "WEBP"]

MESSAGES = {
    "en": "Congratulations! Pay 800 SGD processing fee today or the visa slot is cancelled.",
    "tl": "Aprubado na ang loan mo na 5,000 PHP. Magbayad sa loob ng 3 araw.",
    "id": "Selamat! Nomor Anda terpilih dalam undian hadiah bulan ini. Balas pesan ini.",
}


def encode(image: Image.Image, fmt: ImageFormat = "PNG", **options: Any) -> bytes:
    out = io.BytesIO()
    image.save(out, format=fmt, **options)
    return out.getvalue()


def chat_screenshot(
    text: str = MESSAGES["en"],
    *,
    sender: str = "+65 9000 0001",
    fmt: ImageFormat = "PNG",
    size: tuple[int, int] = (540, 960),
) -> bytes:
    """A phone-shaped image with a header and one message bubble."""
    image = Image.new("RGB", size, (236, 229, 221))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, size[0], 70), fill=(7, 94, 84))
    draw.text((20, 28), sender, fill="white")
    draw.rectangle((20, 120, size[0] - 60, 260), fill="white")
    draw.text((30, 130), text, fill="black")
    return encode(image, fmt)
