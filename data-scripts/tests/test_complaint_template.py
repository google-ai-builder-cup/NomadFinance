from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.config import COMPLAINT_TEMPLATES_DIR
from src.validators.complaint_template import (
    LETTER_LANGUAGES,
    PLACEHOLDERS,
    TYPE_IDS,
    ComplaintTemplateFile,
    load,
    main,
)
from src.validators.labor_law import CATEGORY_IDS, COUNTRIES

_TEXT = (
    "To: {{authority_name}}\n\nDear Sir or Madam,\n\nI am {{worker_name}}. My contract has "
    "terms that appear to break the law:\n\n{{violation_summary}}\n\nThank you.\n{{worker_name}}"
)


def _type(**over: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "authority_name": "Example Labour Office",
        "authority_url": "https://example.org/",
        "channels": [{"kind": "web", "value": "https://example.org/report"}],
        "letter_language": "en",
        "template_text": _TEXT,
        "placeholders": ["authority_name", "worker_name", "violation_summary"],
        "reviewed_on": "2026-09-28",
    }
    data.update(over)
    return data


def _file(**over: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "country": "SG",
        "curated_by": ["Someone"],
        "last_verified_on": "2026-09-28",
        "sources": ["https://example.org/source"],
        "types": {"general": _type()},
    }
    data.update(over)
    return data


def _errors(data: dict[str, Any]) -> str:
    with pytest.raises(ValidationError) as exc:
        ComplaintTemplateFile.model_validate(data)
    return str(exc.value)


def test_valid_file_passes() -> None:
    parsed = ComplaintTemplateFile.model_validate(_file())

    assert parsed.country == "SG"
    assert set(parsed.types) == {"general"}


def test_constants_match_the_labor_law_vocabulary() -> None:
    assert TYPE_IDS == ("general", *CATEGORY_IDS)
    assert set(LETTER_LANGUAGES) == {"en", "ko", "ms", "ja"}
    assert "violation_summary" in PLACEHOLDERS


def test_general_template_is_required() -> None:
    other = CATEGORY_IDS[0]

    assert "'general' template is required" in _errors(_file(types={other: _type()}))


def test_a_category_template_is_allowed_next_to_general() -> None:
    other = CATEGORY_IDS[0]

    parsed = ComplaintTemplateFile.model_validate(_file(types={"general": _type(), other: _type()}))

    assert set(parsed.types) == {"general", other}


def test_unknown_template_type_is_rejected() -> None:
    assert "unknown template type" in _errors(_file(types={"general": _type(), "bogus": _type()}))


def test_unknown_placeholder_is_rejected() -> None:
    text = _TEXT + "\n{{worker_passport}}"
    message = _errors(
        _file(
            types={
                "general": _type(
                    template_text=text,
                    placeholders=["authority_name", "worker_name", "violation_summary"]
                    + ["worker_passport"],
                )
            }
        )
    )

    assert "unknown placeholder" in message and "worker_passport" in message


@pytest.mark.parametrize("missing", ["authority_name", "violation_summary"])
def test_required_placeholders_must_appear_in_the_text(missing: str) -> None:
    text = _TEXT.replace("{{" + missing + "}}", "")
    listed = [p for p in ("authority_name", "worker_name", "violation_summary") if p != missing]

    assert missing in _errors(
        _file(types={"general": _type(template_text=text, placeholders=listed)})
    )


def test_placeholder_list_must_match_the_markers_used() -> None:
    message = _errors(
        _file(types={"general": _type(placeholders=["authority_name", "worker_name"])})
    )

    assert "exactly once" in message


def test_duplicate_placeholder_entries_are_rejected() -> None:
    listed = ["authority_name", "worker_name", "violation_summary", "worker_name"]

    assert "exactly once" in _errors(_file(types={"general": _type(placeholders=listed)}))


def test_markers_with_spaces_are_rejected() -> None:
    text = _TEXT.replace("{{worker_name}}", "{{ worker_name }}", 1)

    assert "no spaces" in _errors(_file(types={"general": _type(template_text=text)}))


def test_todo_text_is_rejected() -> None:
    text = "TODO write the letter " + _TEXT

    assert "TODO" in _errors(_file(types={"general": _type(template_text=text)}))


def test_todo_authority_name_is_rejected() -> None:
    assert "TODO" in _errors(_file(types={"general": _type(authority_name="TODO name")}))


def test_short_template_text_is_rejected() -> None:
    assert "at least 100" in _errors(
        _file(types={"general": _type(template_text="{{authority_name}}")})
    )


@pytest.mark.parametrize(
    ("channel", "fragment"),
    [
        ({"kind": "web", "value": "http://example.org"}, "not a valid web"),
        ({"kind": "email", "value": "not-an-email"}, "not a valid email"),
        ({"kind": "phone", "value": "call us"}, "not a valid phone"),
        ({"kind": "phone", "value": "TODO"}, "TODO"),
        ({"kind": "fax", "value": "123456"}, "kind"),
    ],
)
def test_bad_channels_are_rejected(channel: dict[str, str], fragment: str) -> None:
    assert fragment in _errors(_file(types={"general": _type(channels=[channel])}))


def test_good_phone_email_and_post_channels_pass() -> None:
    channels = [
        {"kind": "phone", "value": "+65 6339 5505"},
        {"kind": "phone", "value": "1800 339 5505"},
        {"kind": "email", "value": "help@example.org"},
        {"kind": "post", "value": "1 Example Road, Singapore 000000"},
    ]

    parsed = ComplaintTemplateFile.model_validate(
        _file(types={"general": _type(channels=channels)})
    )

    assert len(parsed.types["general"].channels) == 4


def test_at_least_one_channel_is_required() -> None:
    assert "at least 1" in _errors(_file(types={"general": _type(channels=[])}))


def test_authority_url_must_be_https() -> None:
    assert "https" in _errors(_file(types={"general": _type(authority_url="http://example.org")}))


def test_authority_url_is_optional() -> None:
    parsed = ComplaintTemplateFile.model_validate(
        _file(types={"general": _type(authority_url=None)})
    )

    assert parsed.types["general"].authority_url is None


def test_letter_language_must_be_supported() -> None:
    assert "letter_language" in _errors(_file(types={"general": _type(letter_language="fr")}))


def test_reviewed_on_cannot_be_in_the_future() -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    assert "future" in _errors(_file(types={"general": _type(reviewed_on=tomorrow)}))


def test_sources_are_required_and_must_be_https() -> None:
    assert "at least 1" in _errors(_file(sources=[]))
    assert "https" in _errors(_file(sources=["http://example.org"]))


def test_unknown_fields_are_rejected() -> None:
    assert "Extra inputs" in _errors(_file(surprise=1))
    assert "Extra inputs" in _errors(_file(types={"general": _type(surprise=1)}))


def test_country_must_be_one_of_the_six() -> None:
    assert "country" in _errors(_file(country="AE"))


def test_shipped_files_cover_all_six_countries_and_pass() -> None:
    for country in COUNTRIES:
        parsed = load(COMPLAINT_TEMPLATES_DIR / f"{country}.json")
        assert parsed.country == country
        assert "general" in parsed.types


def test_shipped_letter_language_is_the_authority_language() -> None:
    expected = {"SG": "en", "HK": "en", "AU": "en", "KR": "ko", "MY": "ms", "JP": "ja"}

    for country, language in expected.items():
        parsed = load(COMPLAINT_TEMPLATES_DIR / f"{country}.json")
        assert {t.letter_language for t in parsed.types.values()} == {language}


def test_shipped_files_have_no_todo_markers_and_a_real_channel() -> None:
    for country in COUNTRIES:
        text = (COMPLAINT_TEMPLATES_DIR / f"{country}.json").read_text(encoding="utf-8")
        assert "TODO" not in text
        parsed = load(COMPLAINT_TEMPLATES_DIR / f"{country}.json")
        assert parsed.types["general"].channels


def test_load_rejects_a_file_named_for_another_country(tmp_path: Path) -> None:
    path = tmp_path / "KR.json"
    path.write_text(json.dumps(_file(country="SG")), encoding="utf-8")

    with pytest.raises(ValueError, match="contains country SG"):
        load(path)


def test_load_accepts_a_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "SG.json"
    path.write_text(json.dumps(_file()), encoding="utf-8-sig")

    assert load(path).country == "SG"


def test_main_ok_on_shipped_files(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--require-all"]) == 0

    out = capsys.readouterr().out
    assert out.count("OK   ") == 6 and "FAIL" not in out


def test_main_reports_a_broken_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broken = copy.deepcopy(_file())
    broken["types"]["general"]["placeholders"] = ["authority_name"]
    path = tmp_path / "SG.json"
    path.write_text(json.dumps(broken), encoding="utf-8")

    assert main([str(path)]) == 1

    assert "FAIL SG.json" in capsys.readouterr().out
