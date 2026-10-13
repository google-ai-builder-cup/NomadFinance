#!/usr/bin/env python3
"""What the service did in a window, from its own logs (NF-HR-017). Read-only.

The 48-hour watch after the flags go on needs the same few numbers at every check: how many
requests, how many failed, how slow, what Gemini refused and how the caches did. This prints them
for any window from one `gcloud logging read`, so a check takes a minute and two people reading
the same window see the same figures.

    python infra/monitoring/watch_report.py --project nomadfinance-prod --window 6h
    gcloud logging read '...' --format=json | python infra/monitoring/watch_report.py --stdin

Counts and timings only: the path of a request has its ids replaced, and no uid, answer or message
is read (the log lines carry none). Exit code 0: nothing crossed a threshold; 1: something did
(each is named); 2: no matching line in the window (a silent service is not a healthy one).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

SERVICE = "nomadfinance-api"
LINES = (
    "request_completed",
    "gemini_call_failed",
    "gemini_budget_blocked",
    "cache_lookup",
)
_NAMES = " OR ".join(f'jsonPayload.message=~"^{name} "' for name in LINES)
FILTER = (
    'resource.type="cloud_run_revision" '
    f'AND resource.labels.service_name="{SERVICE}" AND ({_NAMES})'
)

# Routes that wait for Gemini by design, so their normal time is seconds, not milliseconds
# (NF-HR-007: a new scam analysis 14 s, a Coach turn 4.5 s, a plan 20 to 40 s).
AI_ROUTES = (
    "POST /api/v2/scam/analyze",
    "POST /api/v2/scam/checks/{id}/report",
    "POST /api/v2/coach/sessions/{id}/messages",
    "POST /api/v2/coach/sessions/{id}/plan",
    "GET /api/v2/coach/plans/{id}",
    "GET /api/v2/coach/plans/{id}.pdf",
)
_ID = re.compile(r"^(?=.*\d)[A-Za-z0-9_-]{12,}$|^\d+$")


@dataclass
class Thresholds:
    max_5xx_share: float = 0.01
    max_p95_ms: float = 2000.0
    max_ai_p95_ms: float = 45000.0
    min_requests: int = 20  # below this a share is noise, not a finding


@dataclass
class Route:
    latencies: list[float] = field(default_factory=list)
    classes: Counter[str] = field(default_factory=Counter)


def route_of(method: str, path: str) -> str:
    """`POST /api/v2/coach/sessions/{id}/plan`: the shape of a path, never the ids in it."""
    parts = []
    for part in path.split("?")[0].split("/"):
        stem, dot, suffix = part.partition(".")
        parts.append("{id}" + dot + suffix if _ID.match(stem) else part)
    return f"{method} {'/'.join(parts)}"


def percentile(values: list[float], q: float) -> float:
    """Nearest rank: the value that `q` of the sample is at or below."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _name(entry: dict[str, Any]) -> str:
    return str((entry.get("jsonPayload") or {}).get("message", "")).split(" ", 1)[0]


def build(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Every figure of the report, from the log entries as `gcloud logging read` returns them."""
    routes: dict[str, Route] = defaultdict(Route)
    features: dict[str, Counter[str]] = defaultdict(Counter)
    failures: Counter[tuple[str, str, str]] = Counter()
    blocks: Counter[tuple[str, str, str]] = Counter()
    cache: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    stamps: list[str] = []
    for entry in entries:
        payload = entry.get("jsonPayload") or {}
        name = _name(entry)
        if entry.get("timestamp"):
            stamps.append(str(entry["timestamp"]))
        if name == "request_completed":
            feature = str(payload.get("feature", "platform"))
            klass = str(payload.get("status_class", "?"))
            features[feature][klass] += 1
            route = routes[
                route_of(str(payload.get("method", "?")), str(payload.get("path", "?")))
            ]
            route.classes[klass] += 1
            latency = _num(payload.get("latency_ms"))
            if latency is not None:
                route.latencies.append(latency)
        elif name == "gemini_call_failed":
            usage = payload.get("gemini_usage") or {}
            failures[
                (
                    str(usage.get("feature", "?")),
                    str(usage.get("model", "?")),
                    str(usage.get("error", "?")),
                )
            ] += 1
        elif name == "gemini_budget_blocked":
            budget = payload.get("gemini_budget") or {}
            blocks[
                (
                    str(budget.get("feature", "?")),
                    str(budget.get("tier", "?")),
                    str(budget.get("source", "?")),
                )
            ] += 1
        elif name == "cache_lookup":
            lookup = payload.get("cache_lookup") or {}
            cache[(str(lookup.get("feature", "?")), str(lookup.get("name", "?")))][
                str(lookup.get("result", "?"))
            ] += 1
    return {
        "entries": len(entries),
        "from": min(stamps) if stamps else None,
        "to": max(stamps) if stamps else None,
        "features": features,
        "routes": routes,
        "gemini_failures": failures,
        "budget_blocks": blocks,
        "cache": cache,
    }


def findings(report: dict[str, Any], limits: Thresholds) -> list[str]:
    """What crossed a threshold, in words. An empty list is a clean window."""
    found: list[str] = []
    for feature, classes in sorted(report["features"].items()):
        total = sum(classes.values())
        if (
            total >= limits.min_requests
            and classes.get("5xx", 0) / total > limits.max_5xx_share
        ):
            share = classes["5xx"] / total
            found.append(
                f"{feature}: {share:.1%} of {total} requests were server errors"
            )
    for name, route in sorted(report["routes"].items()):
        if len(route.latencies) < limits.min_requests:
            continue
        p95 = percentile(route.latencies, 0.95)
        ai = (
            name.replace("/api/v2/coach/plans/{id}.pdf", "/api/v2/coach/plans/{id}.pdf")
            in AI_ROUTES
        )
        limit = limits.max_ai_p95_ms if ai else limits.max_p95_ms
        if p95 > limit:
            found.append(f"{name}: p95 {p95:.0f} ms is over {limit:.0f} ms")
    for (feature, tier, source), n in sorted(report["budget_blocks"].items()):
        found.append(
            f"{feature}: the daily Gemini budget refused {n} request(s) ({tier}, {source})"
        )
    return found


def _table(header: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def render(report: dict[str, Any], limits: Thresholds) -> str:
    out = [
        f"## Window {report['from']} to {report['to']} ({report['entries']} log lines)",
        "",
    ]
    rows = []
    for feature, classes in sorted(report["features"].items()):
        total = sum(classes.values())
        rows.append(
            [
                feature,
                total,
                classes.get("2xx", 0),
                classes.get("4xx", 0),
                classes.get("5xx", 0),
                f"{classes.get('5xx', 0) / total:.2%}" if total else "n/a",
            ]
        )
    out += [
        "### Requests by feature",
        _table(["feature", "requests", "2xx", "4xx", "5xx", "5xx share"], rows),
        "",
    ]
    rows = []
    for name, route in sorted(
        report["routes"].items(),
        key=lambda item: -percentile(item[1].latencies or [0.0], 0.95),
    )[:15]:
        lat = route.latencies or [0.0]
        rows.append(
            [
                name,
                sum(route.classes.values()),
                f"{percentile(lat, 0.5):.0f}",
                f"{percentile(lat, 0.95):.0f}",
                f"{max(lat):.0f}",
                route.classes.get("5xx", 0),
            ]
        )
    out += [
        "### Slowest routes (ms)",
        _table(["route", "requests", "p50", "p95", "max", "5xx"], rows),
        "",
    ]
    rows = [[f, m, e, n] for (f, m, e), n in sorted(report["gemini_failures"].items())]
    out += [
        "### Gemini calls that gave up",
        _table(["feature", "model", "error", "count"], rows) if rows else "None.",
        "",
    ]
    rows = [[f, t, s, n] for (f, t, s), n in sorted(report["budget_blocks"].items())]
    out += [
        "### Refused by the daily budget",
        _table(["feature", "tier", "source", "count"], rows) if rows else "None.",
        "",
    ]
    rows = []
    for (feature, cache_name), results in sorted(report["cache"].items()):
        total = sum(results.values())
        rows.append(
            [feature, cache_name, total, f"{results.get('hit', 0) / total:.0%}"]
        )
    out += [
        "### Cache lookups",
        _table(["feature", "cache", "lookups", "hit rate"], rows) if rows else "None.",
        "",
    ]
    flagged = findings(report, limits)
    out.append("### Crossed a threshold")
    out += [f"- {line}" for line in flagged] if flagged else ["Nothing."]
    return "\n".join(out)


def read_logs(project: str, window: str, limit: int) -> list[dict[str, Any]]:
    command = [
        "gcloud",
        "logging",
        "read",
        FILTER,
        "--project",
        project,
        "--freshness",
        window,
        "--limit",
        str(limit),
        "--format=json",
    ]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise SystemExit(f"gcloud failed: {done.stderr.strip()[:300]}")
    data = json.loads(done.stdout or "[]")
    if len(data) >= limit:
        print(
            f"Warning: {limit} lines is the limit; the window is cut. Use a shorter one.",
            file=sys.stderr,
        )
    return list(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The service's numbers for a window (read-only)."
    )
    parser.add_argument("--project", default="nomadfinance-prod")
    parser.add_argument(
        "--window", default="6h", help="how far back, as gcloud's --freshness"
    )
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument(
        "--stdin", action="store_true", help="read `--format=json` output from stdin"
    )
    parser.add_argument("--max-5xx-share", type=float, default=Thresholds.max_5xx_share)
    parser.add_argument("--max-p95-ms", type=float, default=Thresholds.max_p95_ms)
    parser.add_argument("--max-ai-p95-ms", type=float, default=Thresholds.max_ai_p95_ms)
    args = parser.parse_args(argv)

    entries = (
        json.load(sys.stdin)
        if args.stdin
        else read_logs(args.project, args.window, args.limit)
    )
    limits = Thresholds(args.max_5xx_share, args.max_p95_ms, args.max_ai_p95_ms)
    report = build(entries)
    print(render(report, limits))
    if not any(name == "request_completed" for name in map(_name, entries)):
        return 2
    return 1 if findings(report, limits) else 0


if __name__ == "__main__":
    raise SystemExit(main())
