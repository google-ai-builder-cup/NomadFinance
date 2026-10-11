"""Build one version's section of CHANGELOG.md from Conventional Commits (NF-HR-011).

    python infra/release/generate_changelog.py --base 6117b4f9 --version 2.0.0          # print it
    python infra/release/generate_changelog.py --base 6117b4f9 --version 2.0.0 --write  # update

Git is only read (log, rev-list, rev-parse, describe, remote). With --write, the text between the
two markers of that version in CHANGELOG.md is replaced and nothing outside them is touched, so the
command can be run again after a last-minute fix lands and just before the tag is made. Each entry
carries the pull request that brought the commit in (found from the merge commits) and its
`Refs: NF-...` task ids, or the task id in the branch name when the commit has none.

The release commit itself is not listed: the section covers everything up to the commit that
was checked out when this ran.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = ROOT / "CHANGELOG.md"

INTRO = """# Changelog

Every release of NomadFinance. Versions follow [Semantic Versioning](https://semver.org).
Each section is built from Conventional Commits by `infra/release/generate_changelog.py`:
run it again when new commits land, and never edit between the markers by hand.
"""

# (key, heading), in the order they are printed.
SECTIONS = (
    ("breaking", "Breaking changes"),
    ("feat", "Features"),
    ("fix", "Bug fixes"),
    ("perf", "Performance"),
    ("revert", "Reverts"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("refactor", "Refactoring"),
    ("build", "Build"),
    ("ci", "CI"),
    ("chore", "Chores"),
    ("style", "Style"),
    ("other", "Other changes"),
)
TYPES = {key for key, _ in SECTIONS} - {"breaking", "other"}

HEADER = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?: (?P<text>.+)$")
TASK = re.compile(r"NF-[A-Z0-9]{2}-\d{3}")
REFS = re.compile(rf"[ \t]*Refs:[ \t]*({TASK.pattern}(?:,[ \t]*{TASK.pattern})*)")
PR_MERGE = re.compile(r"^Merge pull request #(?P<number>\d+) from \S+?/(?P<branch>\S+)")


@dataclass
class Entry:
    kind: str
    scope: str
    text: str
    breaking: bool
    sha: str
    tasks: list[str]
    pr: int | None


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def split_log(raw: str) -> list[tuple[str, str, str]]:
    """Output of `git log --format=%H%x1f%s%x1f%b%x1e` as (sha, subject, body) triples."""
    records = []
    for chunk in raw.split("\x1e"):
        if chunk.strip():
            sha, subject, body = chunk.strip("\n").split("\x1f", 2)
            records.append((sha, subject, body.strip()))
    return records


def split_merges(raw: str) -> list[tuple[str, list[str], str]]:
    """Output of `git log --merges --format=%H %P%x1f%s` as (sha, parent shas, subject)."""
    merges = []
    for line in raw.splitlines():
        if "\x1f" in line:
            hashes, subject = line.split("\x1f", 1)
            sha, *parents = hashes.split()
            merges.append((sha, parents, subject))
    return merges


def parse(sha: str, subject: str, body: str, pr: tuple[int, str] | None) -> Entry:
    mentioned = [t for m in REFS.finditer(f"{subject}\n{body}") for t in TASK.findall(m.group(1))]
    number = pr[0] if pr else None
    # Older commits carry Refs on the subject line, so it is cut off before the subject is read.
    plain = REFS.sub("", subject).strip()
    match = HEADER.match(plain)
    if match is None or match["type"] not in TYPES:
        return Entry("other", "", plain, False, sha, mentioned, number)
    tasks = mentioned or (TASK.findall(pr[1]) if pr else [])
    breaking = bool(match["bang"]) or "BREAKING CHANGE:" in body
    return Entry(
        match["type"],
        match["scope"] or "",
        match["text"],
        breaking,
        sha,
        list(dict.fromkeys(tasks)),
        number,
    )


def merge_duplicates(entries: list[Entry]) -> list[Entry]:
    """One line for a message that was committed twice (a branch that was re-pushed)."""
    kept: dict[tuple[str, str, str], Entry] = {}
    for entry in entries:
        first = kept.setdefault((entry.kind, entry.scope, entry.text), entry)
        if first is not entry:
            first.tasks = list(dict.fromkeys(first.tasks + entry.tasks))
            first.pr = first.pr or entry.pr
            first.breaking = first.breaking or entry.breaking
    return list(kept.values())


def line(entry: Entry, repo: str | None) -> str:
    if entry.pr is None:
        where = [f"`{entry.sha[:7]}`"]
    else:
        where = [f"[#{entry.pr}]({repo}/pull/{entry.pr})" if repo else f"#{entry.pr}"]
    scope = f"**{entry.scope}:** " if entry.scope else ""
    return f"- {scope}{entry.text} ({', '.join(where + entry.tasks)})"


def render(
    entries: list[Entry],
    *,
    version: str,
    day: str,
    commits: int,
    base: str,
    head: str,
    repo: str | None,
    highlights: str = "",
) -> str:
    prs = sorted({e.pr for e in entries if e.pr is not None})
    inside = f"{commits} commits"
    if prs:
        inside += f" in {len(prs)} pull requests (#{prs[0]} to #{prs[-1]})"
    out = [f"## [{version}] - {day}", ""]
    if highlights.strip():
        out += [highlights.strip(), ""]
    out += [f"{inside} since `{base}`, up to `{head}`.", ""]
    for key, heading in SECTIONS:
        picked = [e for e in entries if (e.breaking if key == "breaking" else e.kind == key)]
        if not picked:
            continue
        picked.sort(key=lambda e: e.scope)  # stable: oldest first inside a scope
        out += [f"### {heading}", "", *(line(e, repo) for e in picked), ""]
    return "\n".join(out)


def write(path: Path, version: str, block: str) -> None:
    start, end = (
        f"<!-- changelog:{version}:start -->",
        f"<!-- changelog:{version}:end -->",
    )
    wrapped = f"{start}\n{block}{end}"
    text = path.read_text(encoding="utf-8") if path.exists() else INTRO
    if start in text and end in text:
        before, rest = text.split(start, 1)
        text = before + wrapped + rest.split(end, 1)[1]
    elif "<!-- changelog:" in text:  # newest version first
        at = text.index("<!-- changelog:")
        text = text[:at] + wrapped + "\n\n" + text[at:]
    else:
        text = text.rstrip("\n") + "\n\n" + wrapped + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def repo_url() -> str | None:
    try:
        remote = git("remote", "get-url", "origin").strip()
    except subprocess.CalledProcessError:
        return None
    remote = re.sub(r"^git@github\.com:", "https://github.com/", remote)
    return re.sub(r"\.git$", "", remote) if remote.startswith("https://") else None


def collect(base: str, head: str) -> tuple[list[Entry], int]:
    span = f"{base}..{head}"
    pulls: dict[str, tuple[int, str]] = {}
    for _, parents, subject in split_merges(
        git("log", "--first-parent", "--merges", "--format=%H %P%x1f%s", span)
    ):
        found = PR_MERGE.match(subject)
        if found is not None and len(parents) == 2:
            for sha in git("rev-list", f"{parents[0]}..{parents[1]}").split():
                pulls.setdefault(sha, (int(found["number"]), found["branch"]))
    raw = split_log(git("log", "--no-merges", "--reverse", "--format=%H%x1f%s%x1f%b%x1e", span))
    entries = [parse(sha, subject, body, pulls.get(sha)) for sha, subject, body in raw]
    return entries, len(entries)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version", required=True, help="for example 2.0.0")
    ap.add_argument(
        "--base", help="commit or tag the section starts after (default: latest v* tag)"
    )
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--highlights", type=Path, help="markdown file printed under the heading")
    ap.add_argument("--write", action="store_true", help=f"update {CHANGELOG.name} in place")
    args = ap.parse_args(argv)
    try:
        base = args.base or git("describe", "--tags", "--abbrev=0", "--match", "v*").strip()
        entries, commits = collect(base, args.head)
        block = render(
            merge_duplicates(entries),
            version=args.version,
            day=args.date,
            commits=commits,
            base=git("rev-parse", "--short", base).strip(),
            head=git("rev-parse", "--short", args.head).strip(),
            repo=repo_url(),
            highlights=(args.highlights.read_text(encoding="utf-8") if args.highlights else ""),
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"git failed: {exc.stderr.strip() or exc}\n(no tag yet? pass --base)",
            file=sys.stderr,
        )
        return 2
    for entry in entries:
        if entry.kind == "other":
            print(
                f"not a Conventional Commit, listed under Other: {entry.sha[:7]}",
                file=sys.stderr,
            )
    if args.write:
        write(CHANGELOG, args.version, block)
        print(f"{CHANGELOG} updated for {args.version}: {commits} commits")
    else:
        sys.stdout.write(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
