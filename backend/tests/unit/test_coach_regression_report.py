"""The regression runner's report and command (NF-FC-024)."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.fixtures.coach_regression_server import FakeCoach
from tests.regression import run_coach_regression
from tests.regression.coach_client import SetupError
from tests.regression.coach_report import RunInfo, parse_usage_log, render_report, uid_hash_of
from tests.unit.test_coach_regression import PERSONAS, TODAY, play

pytestmark = pytest.mark.anyio


def _info() -> RunInfo:
    return RunInfo(
        datetime(2026, 11, 8, 2, 0, tzinfo=UTC), "https://coach.test", 9, "en", 1, 1, "abc"
    )


async def test_the_report_has_the_verdict_the_turn_counts_and_the_request_ids() -> None:
    results = await play(FakeCoach(PERSONAS, TODAY))

    report = render_report(results, _info(), None)

    assert "**12 / 12 personas passed.**" in report
    assert "| `p09_jp_ph_mark` ✔ | JP-PH | 14 / 14 |" in report
    assert "req-0001" in report and "--usage-log" in report


async def test_a_failing_run_says_so_on_top_and_lists_the_problems() -> None:
    server = FakeCoach(PERSONAS, TODAY)
    server.extra_turn_for = "p09_jp_ph_mark"

    report = render_report(await play(server), _info(), None)

    assert "**11 / 12 personas passed.** The target is 12 / 12." in report
    assert "- turn count is 15, expected 14" in report


async def test_token_usage_is_summed_per_persona_from_a_log_export() -> None:
    results = await play(FakeCoach(PERSONAS[:2], TODAY))
    ids = results[0].request_ids
    lines = [
        {
            "jsonPayload": {
                "request_id": ids[0],
                "gemini_usage": {"tokens_in": 100, "tokens_out": 20},
            }
        },
        {"jsonPayload": {"request_id": ids[0], "gemini_usage": {"tokens_in": 50, "tokens_out": 5}}},
        {"jsonPayload": {"request_id": ids[1], "gemini_usage": {"tokens_in": 10, "tokens_out": 1}}},
        {"jsonPayload": {"request_id": ids[1], "message": "not a usage line"}},
    ]

    log = parse_usage_log(json.dumps(lines))
    report = render_report(results, _info(), log)

    assert f"| `{results[0].persona.id}` | 3 | 160 | 26 |" in report
    assert parse_usage_log("\n".join(json.dumps(x) for x in lines)) == log


def test_the_uid_hash_comes_from_the_token_claims() -> None:
    claims = (
        base64.urlsafe_b64encode(json.dumps({"user_id": "uid-1"}).encode()).decode().rstrip("=")
    )

    assert uid_hash_of(f"h.{claims}.s") == hashlib.sha256(b"uid-1").hexdigest()[:16]
    assert uid_hash_of("not-a-token") is None


def test_a_token_is_never_sent_over_plain_http_to_another_machine() -> None:
    run_coach_regression.check_address("http://127.0.0.1:8080")
    run_coach_regression.check_address("https://api.example.com")
    with pytest.raises(SetupError, match="clear"):
        run_coach_regression.check_address("http://api.example.com")


def test_the_command_needs_a_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("COACH_EVAL_ID_TOKEN", raising=False)

    assert run_coach_regression.main(["--base-url", "https://coach.test"]) == 2
    assert "COACH_EVAL_ID_TOKEN" in capsys.readouterr().out


def test_the_command_runs_the_personas_and_writes_the_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("COACH_EVAL_ID_TOKEN", "token")
    server = FakeCoach(PERSONAS, datetime.now(UTC).date())
    report = tmp_path / "report.md"

    code = run_coach_regression.main(
        ["--base-url", "https://coach.test", "--rpm", "0", "--report", str(report)],
        transport=server.transport(),
    )

    assert code == 0
    assert "**12 / 12 personas passed.**" in report.read_text(encoding="utf-8")


def test_a_partial_run_writes_no_report_unless_asked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("COACH_EVAL_ID_TOKEN", "token")
    monkeypatch.setattr(run_coach_regression, "REPORT_DIR", tmp_path)
    server = FakeCoach(PERSONAS[:1], datetime.now(UTC).date())

    code = run_coach_regression.main(
        ["--base-url", "https://coach.test", "--rpm", "0", "--only", PERSONAS[0].id],
        transport=server.transport(),
    )

    assert code == 0 and list(tmp_path.iterdir()) == []


def test_a_failing_persona_makes_the_command_exit_with_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("COACH_EVAL_ID_TOKEN", "token")
    server = FakeCoach(PERSONAS[:1], datetime.now(UTC).date())
    server.extra_turn_for = PERSONAS[0].id

    code = run_coach_regression.main(
        [
            "--base-url",
            "https://coach.test",
            "--rpm",
            "0",
            "--only",
            PERSONAS[0].id,
            "--report",
            str(tmp_path / "r.md"),
        ],
        transport=server.transport(),
    )

    assert code == 1
