from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.prompts import loader
from app.prompts.loader import load_prompt


def test_loads_contract_extract_prompt() -> None:
    prompt = load_prompt("contract", "extract", 1)

    assert prompt.id == "contract/extract.v1"
    assert "original language" in prompt.system
    assert prompt.user.strip()


def test_missing_prompt_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("contract", "does-not-exist", 1)


def test_prompt_file_with_unknown_key_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "step.v1.yaml").write_text(
        "description: d\nsystem: s\nuser: u\ntemprature: 0.2\n", encoding="utf-8"
    )
    monkeypatch.setattr(loader, "_PROMPTS_DIR", tmp_path)
    load_prompt.cache_clear()

    with pytest.raises(ValidationError):
        load_prompt("demo", "step", 1)

    load_prompt.cache_clear()
