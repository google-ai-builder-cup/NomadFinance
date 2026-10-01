"""Turn the sample contract texts into PDFs (NF-P3-020).

Run from data-scripts/:  python -m src.loaders.sample_contract_pdf
Reads data/seed/contracts/source/*.txt and writes the .pdf next to the manifest. The PDFs are
committed, so this only needs running when a text changes. `--check` fails if a committed PDF
is out of date with its text. Output is deterministic (no dates, no random ids).

Text format: `# ` starts the title, `## ` a heading, a blank line a gap, and a line that starts
with "12. " is a numbered clause whose wrapped lines are indented. Only characters in Windows-1252
are allowed: the PDFs use the built-in Helvetica fonts, which carry no CJK or Indic glyphs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from src.config import SEED_CONTRACTS_DIR

FOOTER = "Sample contract for demonstration. Parties and details are fictional."
PAGE_W, PAGE_H = 612, 792
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 72, 72, 72
TEXT_W = PAGE_W - 2 * MARGIN_X
BODY_SIZE, BODY_LEAD = 10.5, 14.5
CLAUSE_INDENT = 16.0
_CLAUSE = re.compile(r"^\d+\. ")


def _char_width(ch: str) -> float:
    """Rough Helvetica advance in em; only used to decide where to wrap."""
    if ch == " ":
        return 0.278
    if ch in "iljtfI.,;:'|!()":
        return 0.28
    if ch in "mwMW@":
        return 0.85
    if ch.isupper():
        return 0.68
    return 0.556 if ch.isdigit() else 0.52


def _wrap(text: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if sum(_char_width(c) for c in candidate) * size <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _escape(text: str) -> bytes:
    raw = text.encode("cp1252")  # raises UnicodeEncodeError for glyphs Helvetica cannot show
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class _Line:
    def __init__(self, text: str, bold: bool, size: float, x: float, lead: float) -> None:
        self.text, self.bold, self.size, self.x, self.lead = text, bold, size, x, lead


def _layout(text: str) -> list[_Line]:
    lines: list[_Line] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            lines.append(_Line("", False, BODY_SIZE, MARGIN_X, BODY_LEAD * 0.6))
        elif stripped.startswith("## "):
            lines.append(_Line("", False, BODY_SIZE, MARGIN_X, BODY_LEAD * 0.3))
            lines.append(_Line(stripped[3:], True, 11.5, MARGIN_X, 17))
        elif stripped.startswith("# "):
            for part in _wrap(stripped[2:], 14, TEXT_W):
                lines.append(_Line(part, True, 14, MARGIN_X, 19))
        elif _CLAUSE.match(stripped):
            first, *rest = _wrap_clause(stripped)
            lines.append(_Line(first, False, BODY_SIZE, MARGIN_X, BODY_LEAD))
            lines.extend(
                _Line(p, False, BODY_SIZE, MARGIN_X + CLAUSE_INDENT, BODY_LEAD) for p in rest
            )
        else:
            for part in _wrap(stripped, BODY_SIZE, TEXT_W):
                lines.append(_Line(part, False, BODY_SIZE, MARGIN_X, BODY_LEAD))
    return lines


def _wrap_clause(text: str) -> list[str]:
    """Wrap a numbered clause: the first line is full width, the rest are indented."""
    first = _wrap(text, BODY_SIZE, TEXT_W)[0]
    return [first, *_wrap(text[len(first) :], BODY_SIZE, TEXT_W - CLAUSE_INDENT)]


def _paginate(lines: list[_Line]) -> list[list[tuple[float, _Line]]]:
    pages: list[list[tuple[float, _Line]]] = [[]]
    y = float(PAGE_H - MARGIN_TOP)
    for line in lines:
        if y - line.lead < MARGIN_BOTTOM:
            pages.append([])
            y = float(PAGE_H - MARGIN_TOP)
        if line.text or pages[-1]:  # no blank lines at the top of a page
            pages[-1].append((y, line))
            y -= line.lead
    return pages


def _content(page: list[tuple[float, _Line]], number: int, total: int) -> bytes:
    ops: list[bytes] = []
    for y, line in page:
        if line.text:
            font = b"/F2" if line.bold else b"/F1"
            ops.append(
                b"BT %s %s Tf 1 0 0 1 %s %s Tm (%s) Tj ET"
                % (
                    font,
                    f"{line.size:g}".encode(),
                    f"{line.x:g}".encode(),
                    f"{y:.1f}".encode(),
                    _escape(line.text),
                )
            )
    footer = _escape(f"{FOOTER}  Page {number} of {total}")
    ops.append(b"BT /F1 8 Tf 1 0 0 1 72 40 Tm (%s) Tj ET" % footer)
    return b"\n".join(ops)


def render_pdf(text: str, title: str) -> bytes:
    """Build a deterministic multi-page PDF from the sample text format."""
    pages = _paginate(_layout(text))
    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    kids = []
    for i, page in enumerate(pages):
        page_id = 5 + 2 * i
        kids.append(f"{page_id} 0 R".encode())
        stream = _content(page, i + 1, len(pages))
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents %d 0 R "
            b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>" % (PAGE_W, PAGE_H, page_id + 1)
        )
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(kids), len(pages))
    fonts = [
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    info = b"<< /Title (%s) >>" % _escape(title)
    # Object order: 1 catalog, 2 pages, 3-4 fonts, then page/content pairs, then info.
    ordered = [objects[0], objects[1], *fonts, *objects[2:], info]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(ordered, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(ordered) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(ordered) + 1,
        len(ordered),
        xref,
    )
    return bytes(out)


def title_of(text: str) -> str:
    first = text.splitlines()[0]
    if not first.startswith("# "):
        raise ValueError("the first line must be the title, starting with '# '")
    return first[2:].strip()


def read_pdf(path: Path) -> bytes:
    """The PDF's bytes as built. On Windows, git's autocrlf can turn the line feeds of these
    all-ASCII files into CRLF at checkout, which shifts the xref offsets; undo that."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def build(source_dir: Path, out_dir: Path, *, check: bool = False) -> list[str]:
    """Write (or with check=True, only compare) every PDF; returns the stems that differ."""
    stale: list[str] = []
    for source in sorted(source_dir.glob("*.txt")):
        text = source.read_text(encoding="utf-8")
        data = render_pdf(text, title_of(text))
        target = out_dir / f"{source.stem}.pdf"
        if target.exists() and read_pdf(target) == data:
            continue
        stale.append(source.stem)
        if not check:
            target.write_bytes(data)
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the sample contract PDFs.")
    parser.add_argument("--source-dir", type=Path, default=SEED_CONTRACTS_DIR / "source")
    parser.add_argument("--output-dir", type=Path, default=SEED_CONTRACTS_DIR)
    parser.add_argument("--check", action="store_true", help="fail if a PDF is out of date")
    args = parser.parse_args(argv)
    changed = build(args.source_dir, args.output_dir, check=args.check)
    if args.check:
        if changed:
            print(f"out of date: {', '.join(changed)}", file=sys.stderr)
            return 1
        print("all PDFs match their text")
        return 0
    print(f"wrote {len(changed)} PDF(s){': ' + ', '.join(changed) if changed else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
