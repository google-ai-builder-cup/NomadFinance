from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_coverage.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # A dataclass looks its own module up by name while it is being built.
    import sys

    sys.modules["check_coverage"] = module
    spec.loader.exec_module(module)
    return module


cc = _load()


def report(files: dict[str, tuple[int, int]]) -> dict[str, Any]:
    """A coverage report; each file is (covered lines, statements)."""
    return {
        "files": {
            path: {"summary": {"covered_lines": c, "num_statements": n}}
            for path, (c, n) in files.items()
        }
    }


GOOD = report(
    {
        "app/services/a.py": (98, 100),
        "app/services/b.py": (98, 100),
        "app/repositories/r.py": (60, 100),
        "app/main.py": (10, 10),
    }
)


@pytest.mark.parametrize(
    ("path", "package"),
    [
        ("backend/app/services/fib/exporter.py", "app/services"),
        ("app/services/x.py", "app/services"),
        ("app\\core\\errors.py", "app/core"),
        ("backend/app/main.py", cc.ROOT_PACKAGE),
        ("backend/app/api/v2/flags.py", "app/api"),
        ("backend/tests/unit/test_x.py", None),
        ("backend/scripts/check_coverage.py", None),
        ("docs/api/endpoints.md", None),
        ("backend/app/prompts/coach/reply.v1.yaml", None),
        ("frontend/src/app/page.tsx", None),
        ("", None),
    ],
)
def test_a_file_belongs_to_the_package_under_app(path: str, package: str | None) -> None:
    assert cc.package_of(path) == package


def test_a_covered_package_and_total_pass() -> None:
    result = cc.evaluate(GOOD, ["backend/app/services/a.py"], package_min=70, total_min=70)

    assert result.failures == []
    assert [row.package for row in result.rows] == ["app/services"]
    assert result.rows[0].percent == 98.0


def test_a_changed_package_under_the_minimum_fails_and_names_it() -> None:
    result = cc.evaluate(GOOD, ["backend/app/repositories/r.py"], package_min=70, total_min=50)

    (failure,) = result.failures
    assert "app/repositories" in failure and "60.0%" in failure and "70%" in failure


def test_a_package_the_pull_request_did_not_touch_is_not_judged() -> None:
    result = cc.evaluate(GOOD, ["backend/app/services/a.py"], package_min=70, total_min=50)

    assert result.failures == []
    assert "app/repositories" not in [row.package for row in result.rows]


def test_the_total_floor_fails_even_when_nothing_changed() -> None:
    result = cc.evaluate(GOOD, [], package_min=70, total_min=99)

    (failure,) = result.failures
    assert "in total" in failure and "99%" in failure


def test_changes_outside_the_backend_app_only_check_the_total() -> None:
    result = cc.evaluate(
        GOOD,
        ["docs/x.md", "backend/tests/unit/test_y.py", "frontend/src/a.ts"],
        package_min=70,
        total_min=50,
    )

    assert result.failures == [] and result.rows == []


def test_a_new_package_with_no_tests_counts_as_zero_and_fails() -> None:
    data = report({"app/newpkg/x.py": (0, 40), "app/services/a.py": (100, 100)})

    result = cc.evaluate(data, ["backend/app/newpkg/x.py"], package_min=70, total_min=10)

    assert any("app/newpkg" in failure and "0.0%" in failure for failure in result.failures)


def test_a_package_with_no_statements_is_not_a_failure() -> None:
    data = report({"app/empty/__init__.py": (0, 0), "app/services/a.py": (100, 100)})

    result = cc.evaluate(data, ["backend/app/empty/__init__.py"], package_min=70, total_min=10)

    assert result.failures == []


def test_a_deleted_package_that_has_no_coverage_data_is_ignored() -> None:
    result = cc.evaluate(GOOD, ["backend/app/gone/old.py"], package_min=70, total_min=50)

    assert result.failures == []


def test_exactly_the_minimum_passes() -> None:
    data = report({"app/core/a.py": (70, 100)})

    assert cc.evaluate(data, ["app/core/a.py"], package_min=70, total_min=70).failures == []


def test_main_returns_the_exit_code_and_writes_the_step_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    coverage = tmp_path / "coverage.json"
    coverage.write_text(json.dumps(GOOD), encoding="utf-8")
    changed = tmp_path / "changed.txt"
    changed.write_text("backend/app/repositories/r.py\nREADME.md\n", encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    code = cc.main([str(coverage), "--changed-list", str(changed), "--total-min", "50"])

    assert code == 1
    assert "FAIL" in capsys.readouterr().out
    assert "### Backend coverage" in summary.read_text(encoding="utf-8")


def test_main_passes_without_a_changed_list(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.json"
    coverage.write_text(json.dumps(GOOD), encoding="utf-8")

    assert cc.main([str(coverage), "--total-min", "50"]) == 0
