"""Pack pre-rendered PNGs into a multi-resolution .ico, without Pillow/ImageMagick.

The Vista+ ICO format allows each directory entry to embed a plain PNG file's bytes as-is
(no BMP re-encoding needed), so this only has to write the ICONDIR/ICONDIRENTRY structs
and concatenate the PNG data. Uses only the standard library.

Usage: python3 pack_ico.py in1.png in2.png ... --output favicon.ico
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path


def _png_dimensions(data: bytes) -> tuple[int, int]:
    # PNG: 8-byte signature, then the IHDR chunk (4-byte length, "IHDR", width, height, ...).
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("not a PNG file")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def pack_ico(png_paths: list[Path], output: Path) -> None:
    images = [path.read_bytes() for path in png_paths]
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)  # reserved, type=icon, image count

    directory = b""
    data = b""
    offset = 6 + 16 * count  # ICONDIR + one ICONDIRENTRY per image
    for image in images:
        width, height = _png_dimensions(image)
        # A dimension of 256 or more is encoded as 0 in the single-byte width/height fields.
        entry_w = 0 if width >= 256 else width
        entry_h = 0 if height >= 256 else height
        directory += struct.pack(
            "<BBBBHHII", entry_w, entry_h, 0, 0, 1, 32, len(image), offset
        )
        data += image
        offset += len(image)

    output.write_bytes(header + directory + data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="PNG files, smallest to largest")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    pack_ico(args.inputs, args.output)
    print(f"Wrote {args.output} ({len(args.inputs)} images)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
