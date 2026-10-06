"""Fail a build when backend coverage is too low (NF-F0-010).

Reads the JSON report from `coverage json` and applies two rules:

* every backend package a pull request changed (`app/<package>/`) must reach `--package-min`
  percent of its statements covered;
* the whole of `app/` must reach `--total-min` percent.

The total is a floor, not a comparison with `main`: it catches coverage sliding away over many
pull requests, while the package rule catches a pull request that adds code without tests.

    python scripts/check_coverage.py coverage.json --changed-list changed.txt

`changed.txt` holds one path per line, as `git diff --name-only` prints them. Without it only the
total is checked (a push to `main`, a local run).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

ROOT_PACKAGE = "app (root files)"


@dataclass
class Row:
    package: str
    covered: int
    statements: int

    @property
    def percent(self) -> float:
        return 100.0 if self.statements == 0 else 100.0 * self.covered / self.statements


@dataclass
class Result:
    rows: list[Row]
    total: Row
    failures: list[str] = field(default_factory=list)


def package_of(path: str) -> str | None:
    """The package a file belongs to: `backend/app/services/x.py` is `app/services`.

    Files directly in `app/` are the root package. Anything outside `app/` (tests, scripts,
    docs, other folders) is not a backend package and is `None`.
    """
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if "app" not in parts:
        return None
    rest = parts[parts.index("app") + 1 :]
    if not rest or not rest[-1].endswith(".py"):
        return None
    return ROOT_PACKAGE if len(rest) == 1 else f"app/{rest[0]}"


def package_rows(report: dict[str, Any]) -> dict[str, Row]:
    rows: dict[str, Row] = {}
    for path, data in report["files"].items():
        package = package_of(path)
        if package is None:
            continue
        summary = data["summary"]
        row = rows.setdefault(package, Row(package, 0, 0))
        row.covered += summary["covered_lines"]
        row.statements += summary["num_statements"]
    return rows


def evaluate(
    report: dict[str, Any], changed: list[str], *, package_min: float, total_min: float
) -> Result:
    rows = package_rows(report)
    changed_packages = sorted({p for path in changed if (p := package_of(path)) is not None})
    total = Row(
        "app (total)",
        sum(r.covered for r in rows.values()),
        sum(r.statements for r in rows.values()),
    )
    result = Result(rows=[rows[p] for p in changed_packages if p in rows], total=total)

    for package in changed_packages:
        row = rows.get(package)
        if row is not None and row.percent < package_min:
            result.failures.append(
                f"{package} is at {row.percent:.1f}% ({row.covered}/{row.statements} statements), "
                f"under the {package_min:g}% a changed package needs"
            )
    if total.percent < total_min:
        result.failures.append(
            f"app is at {total.percent:.1f}% in total, under the {total_min:g}% floor"
        )
    return result


def _row(row: Row, needs: float) -> str:
    cells = [row.package, row.covered, row.statements, f"{row.percent:.1f}%", f"{needs:g}%"]
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def render(result: Result, *, package_min: float, total_min: float) -> str:
    lines = ["| Package | Covered | Statements | Coverage | Needs |", "|---|---:|---:|---:|---:|"]
    for row in result.rows:
        lines.append(_row(row, package_min))
    lines.append(_row(result.total, total_min))
    if not result.rows:
        lines.append("")
        lines.append("No backend package changed, so only the total is checked.")
    for failure in result.failures:
        lines.append(f"\n**FAIL:** {failure}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path, help="JSON from `coverage json`")
    parser.add_argument("--changed-list", type=Path, help="file listing the changed paths")
    parser.add_argument("--package-min", type=float, default=70.0)
    parser.add_argument("--total-min", type=float, default=93.0)
    args = parser.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    changed = (
        [line.strip() for line in args.changed_list.read_text(encoding="utf-8").splitlines()]
        if args.changed_list
        else []
    )
    result = evaluate(report, changed, package_min=args.package_min, total_min=args.total_min)
    text = render(result, package_min=args.package_min, total_min=args.total_min)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("### Backend coverage\n\n" + text + "\n")
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main())
