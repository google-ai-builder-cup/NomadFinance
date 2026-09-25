from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import LABOR_LAWS_DIR
from src.validators.labor_law import (
    CATEGORY_IDS,
    COUNTRIES,
    JOB_TYPES,
    LaborLawFile,
    load,
    main,
    template,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _rule(**over: object) -> dict[str, object]:
    rule: dict[str, object] = {
        "coverage": "regulated",
        "title": "Working hours",
        "summary": "Workers may not be made to work more than eight hours a day.",
        "variants": [
            {
                "applies_to": ["all"],
                "requirements": ["No more than 8 hours per day (Example Act, Art. 1)."],
                "limits": {"daily": {"value": 8, "unit": "hours", "period": "day"}},
            }
        ],
        "references": [
            {"law": "Example Act", "section": "Art. 1", "url": "https://example.org/act"}
        ],
        "confidence": "high",
        "last_verified_on": "2026-09-25",
    }
    rule.update(over)
    return rule


def _file(**over: object) -> dict[str, object]:
    data: dict[str, object] = {
        "country": "JP",
        "name": "Japan",
        "curated_by": ["Someone"],
        "last_verified_on": "2026-09-25",
        "rules": {category: _rule() for category in CATEGORY_IDS},
    }
    data.update(over)
    return data


def test_valid_file_passes() -> None:
    parsed = LaborLawFile.model_validate(_file())

    assert parsed.country == "JP"
    assert len(parsed.rules) == 15


def test_missing_and_extra_categories_are_named() -> None:
    rules = {c: _rule() for c in CATEGORY_IDS if c != "sick_leave"}
    rules["made_up"] = _rule()

    with pytest.raises(ValidationError, match="missing .*sick_leave.*extra .*made_up"):
        LaborLawFile.model_validate(_file(rules=rules))


@pytest.mark.parametrize(
    ("applies_to", "message"),
    [
        (["astronaut"], "unknown worker group"),
        (["all", "care_worker"], "cannot be combined"),
        (["care_worker", "care_worker"], "duplicate worker group"),
    ],
)
def test_bad_worker_groups_are_rejected(applies_to: list[str], message: str) -> None:
    variant = {"applies_to": applies_to, "requirements": ["A requirement that is long enough."]}

    with pytest.raises(ValidationError, match=message):
        LaborLawFile.model_validate(_file(rules=_all_rules(variants=[variant])))


def _all_rules(**over: object) -> dict[str, object]:
    return {category: _rule(**over) for category in CATEGORY_IDS}


def test_a_job_type_variant_can_sit_next_to_all_but_not_repeat() -> None:
    good = [
        {"applies_to": ["all"], "requirements": ["General requirement that is long enough."]},
        {"applies_to": ["domestic_worker"], "requirements": ["Domestic requirement long enough."]},
    ]
    bad = good + [
        {"applies_to": ["domestic_worker"], "requirements": ["Another requirement here."]}
    ]

    LaborLawFile.model_validate(_file(rules=_all_rules(variants=good)))
    with pytest.raises(ValidationError, match="more than one variant"):
        LaborLawFile.model_validate(_file(rules=_all_rules(variants=bad)))


def test_unclear_coverage_needs_low_confidence() -> None:
    with pytest.raises(ValidationError, match="needs confidence 'low'"):
        LaborLawFile.model_validate(_file(rules=_all_rules(coverage="unclear", confidence="high")))

    LaborLawFile.model_validate(_file(rules=_all_rules(coverage="unclear", confidence="low")))


@pytest.mark.parametrize(
    "override",
    [
        {"summary": "TODO write the summary of this rule"},
        {"references": [{"law": "Example Act", "section": "Art. 1", "url": "not-a-url"}]},
        {"references": []},
        {"variants": [{"applies_to": ["all"], "requirements": []}]},
        {"confidence": "certain"},
        {"last_verified_on": "yesterday"},
    ],
)
def test_incomplete_rules_are_rejected(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        LaborLawFile.model_validate(_file(rules=_all_rules(**override)))


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        LaborLawFile.model_validate(_file(surprise=True))


def test_template_has_every_category_and_is_not_valid_until_filled() -> None:
    skeleton = template("HK")

    assert list(skeleton["rules"]) == list(CATEGORY_IDS)  # type: ignore[call-overload]
    with pytest.raises(ValidationError):
        LaborLawFile.model_validate(skeleton)


def test_file_name_must_match_country(tmp_path: Path) -> None:
    path = tmp_path / "SG.json"
    path.write_text(json.dumps(_file()), encoding="utf-8")

    with pytest.raises(ValueError, match="contains country JP"):
        load(path)


def test_cli_skips_uncurated_stubs_unless_all_are_required(tmp_path: Path) -> None:
    stub = tmp_path / "AU.json"
    stub.write_text("{}\n", encoding="utf-8")

    assert main([str(stub)]) == 0
    assert main(["--require-all", str(stub)]) == 1


def test_cli_reports_a_broken_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broken = copy.deepcopy(_file())
    del broken["rules"]["minimum_wage"]  # type: ignore[attr-defined]
    path = tmp_path / "JP.json"
    path.write_text(json.dumps(broken), encoding="utf-8")

    assert main([str(path)]) == 1
    assert "minimum_wage" in capsys.readouterr().out


def test_category_ids_match_the_data_model_doc() -> None:
    doc = (REPO_ROOT / "docs/data-model/collections/labor_laws.md").read_text(encoding="utf-8")

    assert tuple(re.findall(r"^\| \d+ \| `([a-z_]+)` \|", doc, re.M)) == CATEGORY_IDS


def test_job_types_match_the_onboarding_enum() -> None:
    enums = (REPO_ROOT / "frontend/src/types/enums.ts").read_text(encoding="utf-8")
    block = re.search(r"JOB_TYPES = \[(.*?)\]", enums, re.S)
    if block is None:
        pytest.skip("frontend onboarding enums not on this branch yet")

    assert tuple(re.findall(r'"([a-z_]+)"', block.group(1))) == JOB_TYPES


@pytest.mark.parametrize("path", sorted(LABOR_LAWS_DIR.glob("*.json")), ids=lambda p: p.name)
def test_committed_country_files_are_valid_or_still_stubs(path: Path) -> None:
    if json.loads(path.read_text(encoding="utf-8")) == {}:
        pytest.skip(f"{path.name} not curated yet")

    parsed = load(path)
    assert parsed.country in COUNTRIES
    assert parsed.last_verified_on.isoformat() >= "2026-09-01"


def test_template_output_refuses_to_overwrite_curated_work(tmp_path: Path) -> None:
    target = tmp_path / "HK.json"
    target.write_text("{}\n", encoding="utf-8")

    assert main(["--template", "HK", "--output", str(target)]) == 0
    assert list(json.loads(target.read_text(encoding="utf-8"))["rules"]) == list(CATEGORY_IDS)

    target.write_text(json.dumps(_file(country="HK")), encoding="utf-8")
    assert main(["--template", "HK", "--output", str(target)]) == 1
    assert json.loads(target.read_text(encoding="utf-8"))["name"] == "Japan"
    assert main(["--template", "HK", "--output", str(target), "--force"]) == 0


def test_a_file_saved_with_a_byte_order_mark_still_loads(tmp_path: Path) -> None:
    path = tmp_path / "JP.json"
    path.write_text(json.dumps(_file()), encoding="utf-8-sig")

    assert load(path).country == "JP"
