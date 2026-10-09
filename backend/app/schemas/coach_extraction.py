"""What the slot-extraction model returns for one worker message (NF-FC-010).

Gemini's response schema cannot say "no other keys" (`additionalProperties`), so these models
leave extra keys to be ignored; what matters is that `slot` is one of the eleven names.

This is the model's raw reading, sent to Gemini as the response schema. Nothing in it is stored
or shown as it is: `app/services/coach/extraction_checks.py` checks every candidate against the
message before it becomes an answer. A value the model could not find is `None`, never a guess,
which is why every part of an amount is optional.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.coach_profile import AccountKind, InterestPeriod, MoneyPeriod, SlotName
from app.schemas.contract import HostCountryCode, JobTypeId

# What the whole message was: an answer to what was asked, a refusal or "I do not know" for it,
# a question back to the coach, or something else (a greeting, small talk, another subject).
MessageKind = Literal["answer", "decline", "question", "other"]


class ExtractedMoney(BaseModel):
    """An amount as the worker said it. Any part the worker did not say is `None`."""

    amount: float | None = Field(
        default=None,
        description="The number as a plain number, without separators. 0 when the worker says "
        "there is nothing. None when no amount was said.",
    )
    currency: str | None = Field(
        default=None,
        description="ISO code of the money the worker named in this message or an earlier worker "
        "message: SGD, KRW, MYR, JPY, HKD, AUD, PHP, INR, IDR, NPR or BDT. None when no money "
        "was named. Never guessed from the country or the language.",
    )
    period: MoneyPeriod | None = Field(
        default=None,
        description="month, week or year, as the worker said it; once for a one-off total. "
        "None when it was not said.",
    )


class ExtractedInterest(BaseModel):
    rate_percent: float | None = Field(
        default=None, description="The percent as a plain number; 0 for free. None if not said."
    )
    period: InterestPeriod | None = Field(
        default=None, description="month or year, as the worker said it. None if not said."
    )


class SlotCandidate(BaseModel):
    """One answer the message seems to give. Fill only the field of the slot."""

    slot: SlotName
    evidence: str = Field(
        description="The exact words of the worker's message that give this answer, copied "
        "character for character. Never a paraphrase."
    )
    confidence: float = Field(description="0 to 1: how sure the answer is what the worker meant.")
    confirms_pending: bool = Field(
        default=False,
        description="True when the worker only agrees (yes, correct) to a value listed in "
        "<unconfirmed>, adding no new value.",
    )
    country: HostCountryCode | None = None
    job_type: JobTypeId | None = None
    date: str | None = Field(default=None, description="YYYY-MM-DD, with a year.")
    count: int | None = None
    money: ExtractedMoney | None = None
    interest: ExtractedInterest | None = None
    account: AccountKind | None = None


class SlotExtraction(BaseModel):
    message_kind: MessageKind
    candidates: list[SlotCandidate] = Field(default_factory=list)
