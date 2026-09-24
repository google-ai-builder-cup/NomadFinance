"""Live check of the Gemini client: one structured-output call per model tier.

Needs GEMINI_API_KEY in backend/.env.local. Run from backend/:

    python -m scripts.gemini_smoke_test

Exits 0 when every tier returns a validated object, 1 otherwise.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from google.genai import types
from pydantic import BaseModel

from app.integrations.gemini import GeminiError, ModelTier, get_gemini_client


class ClauseVerdict(BaseModel):
    risky: bool
    reason: str


class SalaryTerms(BaseModel):
    employer: str
    monthly_salary: float
    currency: str


class DetectedLanguage(BaseModel):
    iso_639_1: str


def _one_page_pdf(lines: list[str]) -> bytes:
    """Build a minimal text PDF so the extraction tier is tested on a real document type."""
    text = " T* ".join(f"({line}) Tj" for line in lines)
    stream = f"BT /F1 14 Tf 16 TL 72 720 Td {text} ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref_at = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_at,
    )
    return bytes(pdf)


CONTRACT_PDF = _one_page_pdf(
    [
        "EMPLOYMENT CONTRACT",
        "Employer: Lim Household Services Pte Ltd",
        "Position: Domestic worker",
        "Monthly salary: SGD 750",
        "Rest days: one per month",
    ]
)

CHECKS: list[tuple[ModelTier, types.ContentListUnion, type[BaseModel]]] = [
    (
        ModelTier.REASONING,
        "Contract clause: 'The employer will keep the worker's passport for the whole "
        "contract period.' Is this clause risky for a migrant worker in Singapore?",
        ClauseVerdict,
    ),
    (
        ModelTier.EXTRACTION,
        [
            types.Part.from_bytes(data=CONTRACT_PDF, mime_type="application/pdf"),
            "Extract the employer name, monthly salary and currency from this contract.",
        ],
        SalaryTerms,
    ),
    (
        ModelTier.CLASSIFICATION,
        "Detect the language of this text: 'Magkano ang padala sa Pilipinas ngayong buwan?'",
        DetectedLanguage,
    ),
]


async def main() -> int:
    client = get_gemini_client()
    failures = 0
    for tier, contents, response_model in CHECKS:
        try:
            result = await client.generate_structured(
                operation=f"smoke.{tier.value}",
                tier=tier,
                contents=contents,
                response_model=response_model,
            )
        except GeminiError as exc:
            failures += 1
            print(f"FAIL {tier.value}: {type(exc).__name__}: {exc}")
        else:
            print(f"OK   {tier.value}: {result.model_dump_json()}")
    return 1 if failures else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    sys.exit(asyncio.run(main()))
