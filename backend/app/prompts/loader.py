from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

_PROMPTS_DIR = Path(__file__).resolve().parent


class PromptTemplate(BaseModel):
    """One versioned prompt file: `app/prompts/<pillar>/<step>.v<N>.yaml`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    description: str
    system: str
    user: str


@lru_cache
def load_prompt(pillar: str, step: str, version: int) -> PromptTemplate:
    """Load and validate a prompt file.

    Args:
        pillar: Folder under `app/prompts/`, e.g. "contract".
        step: Pipeline step, e.g. "extract".
        version: Prompt version; a new wording gets a new file instead of an edit.

    Raises:
        FileNotFoundError: No such prompt file.
        pydantic.ValidationError: The file is missing `description`, `system` or `user`,
            or has unknown keys.
    """
    path = _PROMPTS_DIR / pillar / f"{step}.v{version}.yaml"
    with path.open(encoding="utf-8") as prompt_file:
        raw = yaml.safe_load(prompt_file)
    return PromptTemplate.model_validate({"id": f"{pillar}/{step}.v{version}", **raw})
