from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import evals.run_scam_eval as cli
from src.loaders.scam_patterns_calibrate import golden_rows
from src.scam_eval import backend
from src.scam_eval.metrics import Prediction
from src.scam_eval.runner import Classifier, ClassifyError
from src.validators.scam_golden import GoldenRow
from src.validators.scam_taxonomy import load_taxonomy


@pytest.fixture(scope="module")
def rows() -> list[GoldenRow]:
    return golden_rows()


def classifier(
    answer: Callable[[GoldenRow], Prediction] | None = None, *, seen: list[GoldenRow] | None = None
) -> Classifier:
    """A fake classifier: right about every message unless `answer` says otherwise."""

    async def classify(row: GoldenRow) -> Prediction:
        if seen is not None:
            seen.append(row)
        return answer(row) if answer else Prediction(row.is_scam, row.scam_type, 0.9)

    return Classifier(classify, model="fake-model", prompt="scam.classify v2")


def options(tmp_path: Path, **changes: object) -> argparse.Namespace:
    values = {"report": tmp_path / "out" / "report.md", "limit": None, "concurrency": 4, "rpm": 0}
    return argparse.Namespace(**(values | changes))


def test_a_run_that_meets_the_bar_writes_the_report_and_exits_0(
    rows: list[GoldenRow], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = options(tmp_path)

    code = cli.run(args, rows, load_taxonomy(), classifier())

    assert code == 0
    report = args.report.read_text(encoding="utf-8")
    assert "**Bar met.**" in report and "fake-model" in report
    out = capsys.readouterr().out
    assert "[120/120]" in out and f"Report: {args.report}" in out
    assert "NOT MET" not in out


def test_a_run_below_the_bar_still_writes_the_report_and_exits_1(
    rows: list[GoldenRow], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calm = classifier(lambda row: Prediction(False, None, 0.9))
    args = options(tmp_path)

    code = cli.run(args, rows, load_taxonomy(), calm)

    assert code == 1
    assert "**Bar not met:**" in args.report.read_text(encoding="utf-8")
    assert "NOT MET" in capsys.readouterr().out


def test_one_language_under_its_bar_fails_the_run_even_when_the_total_passes(
    rows: list[GoldenRow], tmp_path: Path
) -> None:
    # Hindi scams all called benign: 14 of 84 scams missed keeps the total near 0.92, but the
    # Hindi F1 falls to 0 and the run must still fail.
    def answer(row: GoldenRow) -> Prediction:
        if row.language == "hi" and row.is_scam:
            return Prediction(False, None, 0.9)
        return Prediction(row.is_scam, row.scam_type, 0.9)

    args = options(tmp_path)

    code = cli.run(args, rows, load_taxonomy(), classifier(answer))

    report = args.report.read_text(encoding="utf-8")
    assert code == 1
    assert "| Overall | 120 | 0.909 | 0.85 | met |" in report
    assert "**Bar not met:** hi F1 0.000 is under 0.75." in report


def test_a_message_with_no_answer_means_nothing_is_scored_and_no_report(
    rows: list[GoldenRow], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def answer(row: GoldenRow) -> Prediction:
        if row.id == "gold-hi-004":
            raise ClassifyError("GeminiRateLimitError: quota\nretry later")
        return Prediction(row.is_scam, row.scam_type, 0.9)

    args = options(tmp_path)

    code = cli.run(args, rows, load_taxonomy(), classifier(answer))

    assert code == 2
    assert not args.report.exists()
    out = capsys.readouterr().out
    assert "1 message(s) got no answer, so nothing was scored" in out
    assert "gold-hi-004  GeminiRateLimitError: quota retry later" in out


def test_a_limit_runs_a_spread_of_messages_and_scores_nothing(
    rows: list[GoldenRow], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[GoldenRow] = []
    args = options(tmp_path, limit=6)

    code = cli.run(args, rows, load_taxonomy(), classifier(seen=seen))

    assert code == 0
    assert len(seen) == 6 and {r.language for r in seen} == {"bn", "en", "hi", "id", "ne", "tl"}
    assert not args.report.exists()
    assert "Partial run: no report written and no bar applied." in capsys.readouterr().out


def test_a_limit_at_or_over_the_number_of_messages_is_a_full_run(
    rows: list[GoldenRow], tmp_path: Path
) -> None:
    args = options(tmp_path, limit=500)

    assert cli.run(args, rows, load_taxonomy(), classifier()) == 0
    assert args.report.exists()


def test_the_report_goes_to_docs_evals_under_the_date_unless_told_otherwise(
    rows: list[GoldenRow], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "EVAL_REPORT_DIR", tmp_path)

    cli.run(options(tmp_path, report=None), rows, load_taxonomy(), classifier())

    [written] = tmp_path.glob("scam-eval-*.md")
    assert written.name == f"scam-eval-{datetime.now(UTC):%Y-%m-%d}.md"


def test_the_default_report_folder_is_docs_evals_at_the_repo_root() -> None:
    from src.config import EVAL_REPORT_DIR

    assert EVAL_REPORT_DIR.parts[-2:] == ("docs", "evals")
    assert EVAL_REPORT_DIR.is_dir()


def test_main_runs_end_to_end_with_the_classifier_it_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "load_backend_classifier", lambda taxonomy: classifier())
    report = tmp_path / "r.md"

    assert cli.main(["--report", str(report), "--concurrency", "8"]) == 0
    assert report.is_file()


def test_main_stops_with_exit_2_and_a_reason_when_the_setup_is_incomplete(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(taxonomy: object) -> Classifier:
        raise backend.SetupError("GEMINI_API_KEY is empty: set it in this shell")

    monkeypatch.setattr(cli, "load_backend_classifier", refuse)

    assert cli.main([]) == 2
    assert "FAIL GEMINI_API_KEY is empty" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv", [["--limit", "0"], ["--concurrency", "0"], ["--rpm", "-1"], ["--limit", "many"]]
)
def test_main_refuses_nonsense_options_before_doing_anything(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        cli.main(argv)

    assert stop.value.code == 2


def test_a_backend_that_is_not_there_is_a_setup_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(backend, "BACKEND_DIR", tmp_path)

    with pytest.raises(backend.SetupError, match="the backend is not at"):
        backend.load_backend_classifier(load_taxonomy())


def test_a_backend_package_that_is_not_installed_says_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(name: str) -> object:
        raise ModuleNotFoundError("No module named 'tenacity'", name="tenacity")

    monkeypatch.setattr(backend, "importlib", SimpleNamespace(import_module=missing))

    with pytest.raises(backend.SetupError) as error:
        backend.load_backend_classifier(load_taxonomy())

    assert re.search(r"'tenacity'.*pip install -r backend/requirements.txt", str(error.value))


# --- scoring one file of messages (NF-SA-023) --------------------------------------------------


STRESS = Path(__file__).resolve().parents[1] / "evals" / "scam_stress_en_hi.jsonl"


def test_scoring_one_file_gates_only_the_languages_it_has(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stress = [r for r in cli.load_rows(STRESS)[0]]
    args = options(tmp_path, rows=STRESS)

    code = cli.run(args, stress, load_taxonomy(), classifier())

    assert code == 0
    out = capsys.readouterr().out
    assert "[ 30/30]" in out and "en" in out and "ne " not in out
    report = args.report.read_text(encoding="utf-8")
    assert "`data-scripts/evals/scam_stress_en_hi.jsonl`" in report
    assert "| ne |" not in report.split("## Scam against benign")[0]


def test_the_default_report_of_one_file_is_named_after_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "EVAL_REPORT_DIR", tmp_path)
    stress = cli.load_rows(STRESS)[0]

    cli.run(options(tmp_path, report=None, rows=STRESS), stress, load_taxonomy(), classifier())

    [written] = list(tmp_path.glob("*.md"))
    assert written.name.startswith("scam-eval-scam_stress_en_hi-")


def test_a_file_that_does_not_parse_is_not_scored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.jsonl"
    broken.write_text('{"id": "x"}\n', encoding="utf-8")

    code = cli.main(["--rows", str(broken)])

    assert code == cli.NOT_SCORED
    assert "FAIL broken.jsonl" in capsys.readouterr().out
