from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.config import SCAM_TAXONOMY_DIR
from src.validators.scam_taxonomy import (
    REQUIRED_TACTICS,
    REQUIRED_TYPES,
    Taxonomy,
    TaxonomyFile,
    load_taxonomy,
    main,
)


def _copy(tmp_path: Path) -> Path:
    target = tmp_path / "scam-taxonomy"
    shutil.copytree(SCAM_TAXONOMY_DIR, target)
    return target


def _edit(directory: Path, name: str, change: Any) -> None:
    path = directory / name
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_committed_files_pass_and_meet_the_tracker_minimums() -> None:
    taxonomy = load_taxonomy()

    assert len(taxonomy.types) >= 8 and len(taxonomy.tactics) >= 6
    assert set(REQUIRED_TYPES) <= set(taxonomy.types)
    assert set(REQUIRED_TACTICS) <= set(taxonomy.tactics)


def test_every_entry_has_definition_signs_safe_response_and_a_source() -> None:
    taxonomy = load_taxonomy()

    for entry in [*taxonomy.types.values(), *taxonomy.tactics.values()]:
        assert entry.definition and entry.safe_response
        assert 3 <= len(entry.signs) <= 6
        assert entry.sources and all(s.url.startswith("https://") for s in entry.sources)


def test_types_carry_risk_and_related_tactics_and_tactics_carry_how_it_works() -> None:
    taxonomy = load_taxonomy()

    assert all(t.default_risk and t.related_tactics for t in taxonomy.types.values())
    assert all(t.how_it_works for t in taxonomy.tactics.values())
    assert taxonomy.types["other_scam"].order == max(t.order for t in taxonomy.types.values())


def test_a_missing_required_type_is_rejected(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    _edit(data, "types.json", lambda d: d["entries"].pop("lottery"))

    with pytest.raises(ValidationError, match="missing required type"):
        load_taxonomy(data)


def test_an_id_used_for_a_type_and_a_tactic_is_rejected() -> None:
    taxonomy = load_taxonomy()
    types = dict(taxonomy.types)
    types["urgency"] = types["lottery"]
    with pytest.raises(ValidationError, match="unique across"):
        Taxonomy(types=types, tactics=taxonomy.tactics)


def test_related_tactics_must_exist(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    _edit(
        data,
        "types.json",
        lambda d: d["entries"]["lottery"].update(related_tactics=["greed"]),
    )

    with pytest.raises(ValidationError, match="are not tactics"):
        load_taxonomy(data)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("signs", ["only one", "only two"], "at least 3"),
        ("signs", ["a sign", "a sign", "another one"], "must not repeat"),
        ("definition", "TODO write this", "TODO"),
    ],
)
def test_bad_entry_fields_are_rejected(
    tmp_path: Path, field: str, value: Any, message: str
) -> None:
    data = _copy(tmp_path)
    _edit(data, "types.json", lambda d: d["entries"]["lottery"].update({field: value}))

    with pytest.raises(ValidationError, match=message):
        load_taxonomy(data)


def test_curator_must_be_initials(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    _edit(data, "types.json", lambda d: d["entries"]["lottery"].update(curator="Aditya"))

    with pytest.raises(ValidationError, match="initials"):
        load_taxonomy(data)


def test_a_source_must_be_https_and_not_from_the_future(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    _edit(
        data,
        "types.json",
        lambda d: d["entries"]["lottery"]["sources"][0].update(url="http://example.org/x"),
    )
    with pytest.raises(ValidationError, match="https"):
        load_taxonomy(data)

    data = _copy(tmp_path / "again")
    _edit(
        data,
        "types.json",
        lambda d: d["entries"]["lottery"]["sources"][0].update(retrieved_on="2999-01-01"),
    )
    with pytest.raises(ValidationError, match="in the future"):
        load_taxonomy(data)


def test_fields_of_the_other_kind_are_rejected() -> None:
    entry = {
        "label": "Urgency",
        "definition": "The scammer sets a short deadline so you hurry.",
        "signs": ["Today only", "Last chance", "Act now"],
        "safe_response": "Stop and take your time before you act.",
        "default_risk": "high",
        "order": 1,
        "sources": [
            {"url": "https://example.org/a", "publisher": "Example", "retrieved_on": "2026-01-01"}
        ],
        "curator": "AB",
    }

    with pytest.raises(ValidationError, match="how_it_works"):
        TaxonomyFile.model_validate({"kind": "tactic", "entries": {"urgency": entry}})
    with pytest.raises(ValidationError, match="belongs to tactics only"):
        TaxonomyFile.model_validate(
            {"kind": "type", "entries": {"urgency": entry | {"how_it_works": "x" * 30}}}
        )
    with pytest.raises(ValidationError, match="are for types"):
        TaxonomyFile.model_validate(
            {"kind": "tactic", "entries": {"urgency": entry | {"how_it_works": "x" * 30}}}
        )


def test_order_must_differ_inside_a_file(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    _edit(data, "tactics.json", lambda d: d["entries"]["fear"].update(order=1))

    with pytest.raises(ValidationError, match="order"):
        load_taxonomy(data)


def test_a_file_holding_the_wrong_kind_is_rejected(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    (data / "types.json").write_text(
        (data / "tactics.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="expected 'type'"):
        load_taxonomy(data)


def test_cli_reports_ok_and_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "8 type(s), 6 tactic(s)" in capsys.readouterr().out

    (tmp_path / "types.json").write_text("not json", encoding="utf-8")
    assert main(["--input-dir", str(tmp_path)]) == 1
    assert "FAIL" in capsys.readouterr().out
