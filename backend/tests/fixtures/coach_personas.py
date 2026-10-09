"""The twelve Financial Coach test personas (NF-FC-007): the file and its shape.

`coach_personas.json` is read by the unit tests now, by the scoring engine's tests (NF-FC-011),
by the multi-turn regression runner (NF-FC-024) and by the demo seed (NF-HR-003). The models
here refuse a file that has drifted from the shape those readers rely on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.coach_profile import CoachProfile
from app.schemas.coach_questions import FollowUpTrigger

DATA_FILE = Path(__file__).with_name("coach_personas.json")
Band = Literal["needs_work", "getting_ready", "well_prepared"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Turn(_Strict):
    """One message the worker types. `fills` are the slots a correct reading takes from it."""

    say: str = Field(min_length=2)
    language: str
    fills: list[str]
    # The follow-up the coach must ask next because of this message; `None` when it moves on.
    coach_follow_up: FollowUpTrigger | None


class ExpectedFactor(_Strict):
    id: str
    value: float
    points: int = Field(ge=0, le=100)
    weight: float


class ExpectedScore(_Strict):
    rate_pair: str
    rate: float = Field(gt=0)
    amounts_in_host_currency: dict[str, float]
    factors: list[ExpectedFactor] = Field(min_length=5, max_length=5)
    total: int = Field(ge=0, le=100)
    band: Band


class Persona(_Strict):
    id: str
    name: str
    demo: bool
    corridor: str
    host_country: str
    home_country: str
    language: str
    summary: str
    script: list[Turn] = Field(min_length=8)
    # Asked? "skipped": the bank does not ask (no debt, so no interest). "declined": asked, and
    # the worker did not say (a leaving date not known yet), so the slot stays empty.
    skipped_slots: list[str]
    declined_slots: list[str]
    expected_turn_count: int
    expected_slots: CoachProfile
    expected_score: ExpectedScore


class PersonaFile(_Strict):
    version: int
    rubric_version: int
    description: str
    rates_note: str
    rates: dict[str, float]
    personas: list[Persona]


def load_personas() -> PersonaFile:
    """Read and check the file.

    Raises:
        OSError: The file cannot be read.
        pydantic.ValidationError: The file breaks a rule of `PersonaFile`.
    """
    return PersonaFile.model_validate_json(DATA_FILE.read_text(encoding="utf-8"))
