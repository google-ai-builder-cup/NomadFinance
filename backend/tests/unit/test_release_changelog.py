"""`infra/release/generate_changelog.py`: the changelog is built from the commit messages alone.

Git is replaced by canned output in the exact format the script asks for, so nothing here reads
or writes a repository. The script was also run against the real history (NF-HR-011 runbook).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

RELEASE = Path(__file__).resolve().parents[3] / "infra" / "release"
SHA = "a" * 40
REPO = "https://github.com/org/repo"


@pytest.fixture(scope="module")
def cl() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_changelog", RELEASE / "generate_changelog.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # a dataclass looks its module up by name
    spec.loader.exec_module(module)
    return module


def entry(cl: ModuleType, subject: str, body: str = "", pr: tuple[int, str] | None = None) -> Any:
    return cl.parse(SHA, subject, body, pr)


def block(cl: ModuleType, entries: list[Any], **over: Any) -> str:
    args: dict[str, Any] = {
        "version": "2.0.0",
        "day": "2026-10-17",
        "commits": len(entries),
        "base": "1111111",
        "head": "2222222",
        "repo": REPO,
    }
    return cl.render(entries, **{**args, **over})


def test_a_conventional_subject_gives_type_scope_and_text(cl: ModuleType) -> None:
    e = entry(cl, "feat(coach): add the score screen")

    assert (e.kind, e.scope, e.text, e.breaking) == ("feat", "coach", "add the score screen", False)


def test_refs_on_the_subject_line_are_read_and_cut_off(cl: ModuleType) -> None:
    e = entry(cl, "test(security): review v2 routes Refs: NF-HR-008")

    assert e.text == "review v2 routes"
    assert e.tasks == ["NF-HR-008"]


def test_refs_in_the_body_may_name_several_tasks(cl: ModuleType) -> None:
    e = entry(cl, "docs(runbooks): add two runbooks", "Why.\n\nRefs: NF-F0-001, NF-FC-006")

    assert e.tasks == ["NF-F0-001", "NF-FC-006"]


def test_a_commit_without_refs_takes_the_task_id_from_its_pull_request_branch(
    cl: ModuleType,
) -> None:
    e = entry(cl, "fix(scam): allow 90 s", pr=(138, "feature/NF-SA-017-scam-explainer-ui"))

    assert (e.tasks, e.pr) == (["NF-SA-017"], 138)


def test_refs_on_the_commit_win_over_the_branch_name(cl: ModuleType) -> None:
    e = entry(cl, "fix(frontend): one at a time Refs: NF-F0-010", pr=(174, "test/NF-HR-007-x"))

    assert e.tasks == ["NF-F0-010"]


@pytest.mark.parametrize(
    ("subject", "body"),
    [("feat(api)!: drop the old field", ""), ("fix(api): drop it", "BREAKING CHANGE: gone")],
)
def test_a_breaking_change_is_found_in_the_subject_or_the_body(
    cl: ModuleType, subject: str, body: str
) -> None:
    assert entry(cl, subject, body).breaking is True


@pytest.mark.parametrize(
    "subject", ["Update readme", "wip(x): not a type we use", "feat: ", "Feat(x): y"]
)
def test_anything_that_is_not_a_conventional_commit_goes_under_other(
    cl: ModuleType, subject: str
) -> None:
    assert entry(cl, subject).kind == "other"


def test_the_same_message_committed_twice_is_listed_once_with_its_pull_request(
    cl: ModuleType,
) -> None:
    first = entry(cl, "test(security): review Refs: NF-HR-008")
    second = entry(cl, "test(security): review Refs: NF-HR-008", pr=(176, "x/NF-HR-008"))

    merged = cl.merge_duplicates([first, second])

    assert len(merged) == 1
    assert merged[0].pr == 176


def test_log_output_is_split_into_sha_subject_and_body(cl: ModuleType) -> None:
    raw = "abc\x1ffeat(a): one\x1fRefs: NF-A1-001\n\x1e\ndef\x1ffix(b): two\x1f\x1e\n"

    assert cl.split_log(raw) == [
        ("abc", "feat(a): one", "Refs: NF-A1-001"),
        ("def", "fix(b): two", ""),
    ]


def test_merge_output_is_split_into_sha_parents_and_subject(cl: ModuleType) -> None:
    raw = (
        "m1 p1 p2\x1fMerge pull request #7 from o/feature/NF-A1-001-x\nm2 q1\x1fMerge branch 'x'\n"
    )

    assert cl.split_merges(raw) == [
        ("m1", ["p1", "p2"], "Merge pull request #7 from o/feature/NF-A1-001-x"),
        ("m2", ["q1"], "Merge branch 'x'"),
    ]


def test_sections_come_in_a_fixed_order_and_empty_ones_are_left_out(cl: ModuleType) -> None:
    out = block(
        cl,
        [entry(cl, "docs(a): d"), entry(cl, "fix(a): f"), entry(cl, "feat(a): x")],
    )

    assert out.index("### Features") < out.index("### Bug fixes") < out.index("### Documentation")
    assert "### Tests" not in out


def test_entries_are_grouped_by_scope_and_keep_their_order_inside_one(cl: ModuleType) -> None:
    out = block(
        cl,
        [entry(cl, "feat(scam): s1"), entry(cl, "feat(coach): c1"), entry(cl, "feat(scam): s2")],
    )

    assert out.index("c1") < out.index("s1") < out.index("s2")


def test_a_line_links_its_pull_request_and_names_its_tasks(cl: ModuleType) -> None:
    out = block(cl, [entry(cl, "feat(coach): add it", "Refs: NF-FC-001", pr=(145, "x"))])

    assert f"- **coach:** add it ([#145]({REPO}/pull/145), NF-FC-001)" in out


def test_a_commit_that_came_in_without_a_pull_request_shows_its_short_sha(cl: ModuleType) -> None:
    assert "(`aaaaaaa`)" in block(cl, [entry(cl, "fix(scam): direct")])


def test_without_a_remote_the_pull_request_is_plain_text(cl: ModuleType) -> None:
    out = block(cl, [entry(cl, "feat(a): x", pr=(5, "b"))], repo=None)

    assert "(#5)" in out


def test_a_breaking_change_is_listed_first_and_in_its_own_section(cl: ModuleType) -> None:
    out = block(cl, [entry(cl, "feat(a): fine"), entry(cl, "feat(api)!: drops a field")])

    assert out.index("### Breaking changes") < out.index("### Features")
    assert out.count("drops a field") == 2


def test_the_heading_summary_and_highlights(cl: ModuleType) -> None:
    out = block(
        cl,
        [entry(cl, "feat(a): x", pr=(108, "b")), entry(cl, "feat(a): y", pr=(178, "c"))],
        highlights="  Two new modules.  \n",
    )

    assert out.startswith("## [2.0.0] - 2026-10-17\n\nTwo new modules.\n\n")
    assert "2 commits in 2 pull requests (#108 to #178) since `1111111`, up to `2222222`." in out


def test_the_summary_leaves_out_pull_requests_when_there_are_none(cl: ModuleType) -> None:
    assert "1 commits since `1111111`" in block(cl, [entry(cl, "feat(a): x")])


def test_a_new_file_gets_the_intro_and_a_marked_section(cl: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "CHANGELOG.md"

    cl.write(path, "2.0.0", "## [2.0.0]\n\nbody\n")

    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Changelog\n")
    assert text.count("<!-- changelog:2.0.0:start -->") == 1
    assert text.rstrip().endswith("<!-- changelog:2.0.0:end -->")


def test_running_again_replaces_the_marked_section_and_nothing_else(
    cl: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / "CHANGELOG.md"
    cl.write(path, "2.0.0", "## [2.0.0]\n\nold\n")
    path.write_text(
        path.read_text(encoding="utf-8") + "\nA note added by hand.\n", encoding="utf-8"
    )

    cl.write(path, "2.0.0", "## [2.0.0]\n\nnew\n")
    once = path.read_text(encoding="utf-8")
    cl.write(path, "2.0.0", "## [2.0.0]\n\nnew\n")

    assert "new" in once and "old" not in once
    assert once.endswith("A note added by hand.\n")
    assert path.read_text(encoding="utf-8") == once


def test_a_newer_version_is_added_above_the_older_one(cl: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "CHANGELOG.md"
    cl.write(path, "2.0.0", "## [2.0.0]\n")

    cl.write(path, "2.1.0", "## [2.1.0]\n")

    text = path.read_text(encoding="utf-8")
    assert text.index("## [2.1.0]") < text.index("## [2.0.0]")


@pytest.mark.parametrize(
    ("remote", "expected"),
    [
        ("https://github.com/org/repo.git\n", REPO),
        ("git@github.com:org/repo.git\n", REPO),
        ("ssh://elsewhere/org/repo\n", None),
    ],
)
def test_the_remote_becomes_a_web_address_or_nothing(
    cl: ModuleType, monkeypatch: pytest.MonkeyPatch, remote: str, expected: str | None
) -> None:
    monkeypatch.setattr(cl, "git", lambda *a: remote)

    assert cl.repo_url() == expected


def test_commits_are_matched_to_the_pull_request_that_merged_them(
    cl: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    merges = (
        "m1 p1 p2\x1fMerge pull request #7 from o/feature/NF-A1-001-x\n"
        "m2 q1 q2 q3\x1fMerge pull request #8 from o/octopus\n"
        "m3 r1 r2\x1fMerge branch 'main' into feature/y\n"
    )
    log = (
        "c1\x1ffeat(a): one\x1f\x1e\n"
        "c2\x1ffix(a): two\x1f\x1e\n"
        "c3\x1fdocs(b): three\x1f\x1e\n"
    )
    answers = {
        "log --first-parent --merges": merges,
        "rev-list p1..p2": "c1\nc2\n",
        "log --no-merges": log,
    }

    def fake(*args: str) -> str:
        key = " ".join(args)
        return next(v for k, v in answers.items() if key.startswith(k))

    monkeypatch.setattr(cl, "git", fake)

    entries, commits = cl.collect("base", "head")

    assert commits == 3
    assert [(e.sha, e.pr, e.tasks) for e in entries] == [
        ("c1", 7, ["NF-A1-001"]),
        ("c2", 7, ["NF-A1-001"]),
        ("c3", None, []),
    ]


def test_without_a_tag_or_a_base_the_script_stops_and_says_what_to_pass(
    cl: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*args: str) -> str:
        raise subprocess.CalledProcessError(128, ["git", *args], stderr="fatal: No names found")

    monkeypatch.setattr(cl, "git", fail)

    assert cl.main(["--version", "2.0.0"]) == 2
    assert "pass --base" in capsys.readouterr().err


def test_write_updates_the_file_the_flag_names(
    cl: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake(*args: str) -> str:
        if args[0] == "log" and "--merges" in args:
            return ""
        if args[0] == "log":
            return "c1\x1ffeat(a): one\x1f\x1e\n"
        if args[0] == "rev-parse":
            return args[-1][:7] + "\n"
        return "https://github.com/org/repo.git\n"

    monkeypatch.setattr(cl, "git", fake)
    monkeypatch.setattr(cl, "CHANGELOG", tmp_path / "CHANGELOG.md")

    assert cl.main(["--version", "2.0.0", "--base", "v1", "--date", "2026-10-17", "--write"]) == 0

    text = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [2.0.0] - 2026-10-17" in text
    assert "- **a:** one (`c1`)" in text
