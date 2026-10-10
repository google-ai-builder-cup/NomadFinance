"""The report of a regression run (NF-FC-024): results, turn counts, timing and token usage.

Token usage is not in any API answer (the contract hides model details), so it is read from the
server's `gemini_call` log lines, which carry the request id of the turn that caused them. Export
them from Cloud Logging and pass the file to the runner; without it the report says how to.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from tests.regression.coach_replay import PersonaResult


@dataclass(frozen=True)
class RunInfo:
    when: datetime
    base_url: str
    rpm: int
    plan_language: str
    personas_version: int
    rubric_version: int
    uid_hash: str | None


@dataclass
class Usage:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


def uid_hash_of(token: str) -> str | None:
    """The hashed uid the server tags its log lines with, read from the token's own claims.

    Nothing is verified here: the claims only name the account to look for in the logs.
    """
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        uid = claims.get("user_id") or claims["sub"]
    except (IndexError, KeyError, ValueError):
        return None
    return hashlib.sha256(str(uid).encode()).hexdigest()[:16]


def parse_usage_log(text: str) -> dict[str, Usage]:
    """Sum the `gemini_call` lines of an export by request id.

    Accepts what `gcloud logging read --format=json` writes (an array) or one entry per line;
    an entry may carry its fields under `jsonPayload` or at the top.
    """
    try:
        loaded = json.loads(text)
        entries = loaded if isinstance(loaded, list) else [loaded]
    except ValueError:
        entries = [json.loads(line) for line in text.splitlines() if line.strip()]
    usage: dict[str, Usage] = defaultdict(Usage)
    for entry in entries:
        payload = entry.get("jsonPayload", entry)
        fields = payload.get("gemini_usage")
        request_id = payload.get("request_id")
        if not isinstance(fields, dict) or not request_id:
            continue
        total = usage[str(request_id)]
        total.calls += 1
        total.tokens_in += int(fields.get("tokens_in") or 0)
        total.tokens_out += int(fields.get("tokens_out") or 0)
    return dict(usage)


def _usage_of(result: PersonaResult, log: dict[str, Usage]) -> Usage:
    total = Usage()
    for request_id in set(result.request_ids):
        found = log.get(request_id)
        if found:
            total.calls += found.calls
            total.tokens_in += found.tokens_in
            total.tokens_out += found.tokens_out
    return total


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(share * len(ordered)) - 1)]


def render_report(
    results: list[PersonaResult], info: RunInfo, usage: dict[str, Usage] | None
) -> str:
    """The markdown report, verdict first."""
    passed = sum(1 for r in results if r.passed)
    lines = [
        f"# Coach regression run, {info.when:%Y-%m-%d}",
        "",
        f"**{passed} / {len(results)} personas passed.**"
        + ("" if passed == len(results) else " The target is 12 / 12."),
        "",
        "## The run",
        "",
        f"- Started: {info.when:%Y-%m-%d %H:%M} UTC",
        f"- Server: {info.base_url}",
        f"- Personas file version {info.personas_version}, rubric version {info.rubric_version}",
        f"- Pace: at most {info.rpm or 'unlimited'} Gemini-spending calls a minute; "
        f"plan in `{info.plan_language}`",
        "- Leaving dates moved to the day of the run (D-203); scores use the live rates, so the "
        "band is checked and the total is shown for comparison",
        "",
        "## Results",
        "",
        "| Persona | Corridor | Turns (got / expected) | Band (got / expected) "
        "| Score (got / expected) | Plan | Retries | Time |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        p = r.persona
        lines.append(
            f"| `{p.id}` {'✔' if r.passed else '✘'} | {p.corridor} "
            f"| {r.turn_count} / {p.expected_turn_count} "
            f"| {r.band} / {p.expected_score.band} | {r.total} / {p.expected_score.total} "
            f"| {'ok' if r.plan_ok else 'no'} | {r.retries} | {r.seconds:.0f} s |"
        )
    failed = [r for r in results if not r.passed]
    lines += ["", "## Failures", ""]
    if not failed:
        lines.append("None.")
    for r in failed:
        lines.append(f"**`{r.persona.id}`**")
        lines += [f"- {problem}" for problem in r.problems]
        lines.append("")
    times = [t for r in results for t in r.first_token_s]
    lines += ["", "## Time to the first word of a reply", ""]
    if times:
        lines.append(
            f"{len(times)} turns: median {_percentile(times, 0.5):.1f} s, "
            f"p95 {_percentile(times, 0.95):.1f} s, slowest {max(times):.1f} s. "
            "The goal of NF-FC-009 is under 2 s at p95."
        )
    else:
        lines.append("No reply carried a word.")
    lines += ["", "## Token usage", ""]
    lines += _usage_section(results, info, usage)
    lines += ["", "## Request ids", "", "Every request of a persona, in the order sent.", ""]
    for r in results:
        lines += [
            f"`{r.persona.id}` (plan: `{r.plan_request_id}`)",
            "",
            "```",
            *r.request_ids,
            "```",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def _usage_section(
    results: list[PersonaResult], info: RunInfo, log: dict[str, Usage] | None
) -> list[str]:
    if log is None:
        who = f' AND jsonPayload.uid_hash="{info.uid_hash}"' if info.uid_hash else ""
        return [
            "Not read for this run: the answers carry no token counts. Export the server's "
            "`gemini_call` lines for the window of the run and run the report again with "
            "`--usage-log`:",
            "",
            "```",
            "gcloud logging read '"
            'jsonPayload.message=~"^gemini_call "'
            + who
            + f' AND timestamp>="{info.when:%Y-%m-%dT%H:%M:%SZ}"'
            "' --project nomadfinance-prod --format=json > coach-usage.json",
            "```",
        ]
    lines = ["| Persona | Gemini calls | Tokens in | Tokens out |", "|---|---|---|---|"]
    grand = Usage()
    for r in results:
        u = _usage_of(r, log)
        lines.append(f"| `{r.persona.id}` | {u.calls} | {u.tokens_in} | {u.tokens_out} |")
        grand.calls += u.calls
        grand.tokens_in += u.tokens_in
        grand.tokens_out += u.tokens_out
    lines.append(f"| **All** | {grand.calls} | {grand.tokens_in} | {grand.tokens_out} |")
    return lines
