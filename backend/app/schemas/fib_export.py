from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

MAX_HOLDER_NAME_CHARS = 100


class ExportReportRequest(BaseModel):
    """Optional body of `POST /api/v1/fib/report/export`."""

    holder_name: str | None = Field(
        default=None,
        max_length=MAX_HOLDER_NAME_CHARS,
        description="Name printed on the report. Used for this PDF only, never stored.",
    )

    @field_validator("holder_name")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class ExportReportResponse(BaseModel):
    """A link to the exported Financial Identity PDF."""

    download_url: str = Field(description="Signed link; anyone who has it can download the PDF.")
    expires_at: datetime
    created_at: datetime = Field(description="When this PDF was made.")
    language: str = Field(description="Language of the report: the profile narrative's.")
    filename: str
