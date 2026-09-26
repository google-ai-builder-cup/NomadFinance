from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

_PROMPTS_DIR = Path(__file__).resolve().parent


class PromptTemplate(BaseModel):
    """One versioned prompt file: `app/prompts/<pillar>/<step>.v<N>.yaml`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    description: str
    system: str
    user: str
    # Names of the `${...}` placeholders in `user`, declared so a typo fails at startup.
    variables: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _placeholders_match_variables(self) -> PromptTemplate:
        template = Template(self.user)
        if not template.is_valid():
            raise ValueError(f"{self.id}: `user` has a malformed placeholder")
        used = set(template.get_identifiers())
        declared = set(self.variables)
        if used != declared:
            raise ValueError(
                f"{self.id}: placeholders {sorted(used)} do not match variables {sorted(declared)}"
            )
        if Template(self.system).get_identifiers():
            raise ValueError(f"{self.id}: `system` must not contain placeholders")
        return self

    @property
    def key(self) -> str:
        """`<pillar>.<step>`, the key used in stored `prompt_versions` maps."""
        return self.id.rsplit(".v", 1)[0].replace("/", ".")

    @property
    def version(self) -> int:
        return int(self.id.rsplit(".v", 1)[1])

    def render_user(self, **values: str) -> str:
        """Fill the user template.

        Values are inserted once and never re-scanned, so `${...}` inside worker-supplied text
        stays literal.

        Raises:
            ValueError: A declared variable is missing, or an undeclared one was given.
        """
        missing = set(self.variables) - values.keys()
        unexpected = values.keys() - set(self.variables)
        if missing or unexpected:
            raise ValueError(
                f"{self.id}: missing {sorted(missing)}, unexpected {sorted(unexpected)}"
            )
        return Template(self.user).substitute(values)


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
            has unknown keys, or its placeholders don't match `variables`.
    """
    path = _PROMPTS_DIR / pillar / f"{step}.v{version}.yaml"
    with path.open(encoding="utf-8") as prompt_file:
        raw = yaml.safe_load(prompt_file)
    return PromptTemplate.model_validate({"id": f"{pillar}/{step}.v{version}", **raw})
