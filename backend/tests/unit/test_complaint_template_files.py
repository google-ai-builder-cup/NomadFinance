"""The curated complaint templates (data-scripts) must fit what the backend reads and fills.

data-scripts has its own validator and cannot import the backend, so the shared vocabulary
(letter languages, placeholder names) is compared here, on the files that get loaded.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, get_args

import pytest

from app.prompts.loader import load_prompt
from app.schemas.contract_complaint import ComplaintTemplate, LetterLanguage
from app.services.contract.complaint import LETTER_LANGUAGE_NAMES

DATA_SCRIPTS = Path(__file__).resolve().parents[3] / "data-scripts"
VALIDATOR = DATA_SCRIPTS / "src" / "validators" / "complaint_template.py"
FILES = sorted((DATA_SCRIPTS / "data" / "source" / "complaint-templates").glob("*.json"))


def _validator_constant(name: str) -> tuple[str, ...]:
    for node in ast.parse(VALIDATOR.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, tuple)
            return value
    raise AssertionError(f"{name} not found in {VALIDATOR}")


def test_the_six_country_files_exist() -> None:
    assert [path.stem for path in FILES] == ["AU", "HK", "JP", "KR", "MY", "SG"]


def test_letter_languages_match_the_data_scripts_validator() -> None:
    assert set(get_args(LetterLanguage)) == set(_validator_constant("LETTER_LANGUAGES"))
    assert set(LETTER_LANGUAGE_NAMES) == set(get_args(LetterLanguage))


def test_every_placeholder_the_files_may_use_is_explained_in_the_prompt() -> None:
    system = load_prompt("contract", "complaint", 2).system

    for name in _validator_constant("PLACEHOLDERS"):
        assert re.search(rf"^\s*- {name}:", system, re.MULTILINE), f"{name} is not in the prompt"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_each_stored_general_template_parses_as_the_backend_reads_it(path: Path) -> None:
    file: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    # What the loader writes to Firestore: the type's fields plus country, type and version.
    stored = file["types"]["general"] | {"country": file["country"], "type": "general"}

    template = ComplaintTemplate.model_validate(stored)

    assert template.country == path.stem
    assert template.channels
