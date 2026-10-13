"""`infra/monitoring/watch_report.py`: the figures of a watch window, from log lines (NF-HR-017)."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "infra" / "monitoring" / "watch_report.py"


@pytest.fixture(scope="module")
def wr() -> ModuleType:
    spec = importlib.util.spec_from_file_location("watch_report", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # a dataclass looks its module up by name
    spec.loader.exec_module(module)
    return module


def request(
    feature: str = "scam",
    status: int = 200,
    latency: float = 20.0,
    method: str = "GET",
    path: str = "/api/v2/scam/checks",
    at: str = "2026-10-20T10:00:00Z",
) -> dict[str, Any]:
    return {
        "timestamp": at,
        "jsonPayload": {
            "message": f"request_completed method={method} path={path} status={status}",
            "feature": feature,
            "status": status,
            "status_class": f"{status // 100}xx",
            "latency_ms": latency,
            "method": method,
            "path": path,
        },
    }


def failure(feature: str = "scam", model: str = "gemini-3.5-flash", error: str = "ai_busy") -> Any:
    return {
        "timestamp": "2026-10-20T10:01:00Z",
        "jsonPayload": {
            "message": "gemini_call_failed operation=scam.explain",
            "gemini_usage": {
                "feature": feature,
                "model": model,
                "error": error,
                "outcome": "failed",
            },
        },
    }


def block() -> dict[str, Any]:
    return {
        "timestamp": "2026-10-20T10:02:00Z",
        "jsonPayload": {
            "message": "gemini_budget_blocked feature=coach tier=reasoning source=db",
            "gemini_budget": {"feature": "coach", "tier": "reasoning", "source": "db"},
        },
    }


def lookup(result: str, feature: str = "scam", name: str = "scam_check") -> dict[str, Any]:
    return {
        "timestamp": "2026-10-20T10:03:00Z",
        "jsonPayload": {
            "message": f"cache_lookup feature={feature} name={name} result={result}",
            "cache_lookup": {"feature": feature, "name": name, "result": result},
        },
    }


def clean_window(count: int = 40) -> list[dict[str, Any]]:
    return [request(latency=10.0 + n) for n in range(count)]


def test_a_path_keeps_its_shape_and_loses_its_ids(wr: ModuleType) -> None:
    assert wr.route_of("GET", "/api/v2/coach/plans/5a202702c922fc9b4fcf.pdf") == (
        "GET /api/v2/coach/plans/{id}.pdf"
    )
    assert wr.route_of("PUT", "/api/v2/coach/plans/abc123def4567890/checkins/d30") == (
        "PUT /api/v2/coach/plans/{id}/checkins/d30"
    )
    assert wr.route_of("GET", "/api/v2/scam/checks/k_01") == "GET /api/v2/scam/checks/k_01"
    assert wr.route_of("GET", "/api/v1/contracts/e2eseeded0000001") == (
        "GET /api/v1/contracts/{id}"
    )


def test_the_percentiles_are_nearest_rank(wr: ModuleType) -> None:
    values = [float(n) for n in range(1, 101)]

    assert wr.percentile(values, 0.5) == 50.0
    assert wr.percentile(values, 0.95) == 95.0
    assert wr.percentile([7.0], 0.95) == 7.0


def test_requests_are_counted_by_feature_and_class(wr: ModuleType) -> None:
    entries = [
        request("scam"),
        request("scam", 429),
        request("coach", 500),
        request("coach"),
    ]

    report = wr.build(entries)

    assert report["features"]["scam"] == {"2xx": 1, "4xx": 1}
    assert report["features"]["coach"] == {"2xx": 1, "5xx": 1}
    assert report["from"] == report["to"] == "2026-10-20T10:00:00Z"


def test_gemini_failures_blocks_and_cache_lookups_are_counted(wr: ModuleType) -> None:
    entries = [
        failure(),
        failure(error="ai_timeout"),
        failure(),
        block(),
        lookup("hit"),
        lookup("miss"),
        lookup("hit"),
    ]

    report = wr.build(entries)

    assert report["gemini_failures"][("scam", "gemini-3.5-flash", "ai_busy")] == 2
    assert report["gemini_failures"][("scam", "gemini-3.5-flash", "ai_timeout")] == 1
    assert report["budget_blocks"][("coach", "reasoning", "db")] == 1
    assert report["cache"][("scam", "scam_check")] == {"hit": 2, "miss": 1}


def test_a_clean_window_has_no_findings_and_exits_zero(wr: ModuleType) -> None:
    report = wr.build(clean_window())

    assert wr.findings(report, wr.Thresholds()) == []


def test_a_share_of_server_errors_over_the_limit_is_named(wr: ModuleType) -> None:
    entries = clean_window(38) + [request(status=500), request(status=502)]

    found = wr.findings(wr.build(entries), wr.Thresholds())

    assert any(line.startswith("scam: 5.0% of 40 requests were server errors") for line in found)


def test_too_few_requests_do_not_make_a_share(wr: ModuleType) -> None:
    entries = [request(status=500), request(status=200)]

    assert wr.findings(wr.build(entries), wr.Thresholds()) == []


def test_a_slow_route_is_named_but_a_route_that_waits_for_gemini_has_its_own_limit(
    wr: ModuleType,
) -> None:
    slow = [request(latency=2500.0, path="/api/v2/scam/checks") for _ in range(25)]
    analyze = [
        request(latency=14000.0, method="POST", path="/api/v2/scam/analyze") for _ in range(25)
    ]

    found = wr.findings(wr.build(slow + analyze), wr.Thresholds())

    assert found == ["GET /api/v2/scam/checks: p95 2500 ms is over 2000 ms"]


def test_a_gemini_route_over_its_own_limit_is_named(wr: ModuleType) -> None:
    plan = [
        request(
            latency=50000.0,
            method="POST",
            path="/api/v2/coach/sessions/s1abcdef12345/plan",
        )
        for _ in range(25)
    ]

    found = wr.findings(wr.build(plan), wr.Thresholds())

    assert found == ["POST /api/v2/coach/sessions/{id}/plan: p95 50000 ms is over 45000 ms"]


def test_a_budget_block_is_always_a_finding(wr: ModuleType) -> None:
    found = wr.findings(wr.build(clean_window() + [block()]), wr.Thresholds())

    assert any("daily Gemini budget refused 1 request" in line for line in found)


def test_the_report_carries_no_id_of_a_record(wr: ModuleType) -> None:
    entries = [
        request(path="/api/v2/coach/plans/5a202702c922fc9b4fcf", latency=30.0),
        request(path="/api/v2/scam/checks/9f3a1c5e7b2d4a60c8e1aa", latency=30.0),
    ]

    text = wr.render(wr.build(entries), wr.Thresholds())

    assert "5a202702c922fc9b4fcf" not in text and "9f3a1c5e7b2d4a60c8e1aa" not in text
    assert "GET /api/v2/coach/plans/{id}" in text


def test_the_filter_asks_for_exactly_the_four_lines_of_the_service(
    wr: ModuleType,
) -> None:
    assert 'resource.labels.service_name="nomadfinance-api"' in wr.FILTER
    for name in (
        "request_completed",
        "gemini_call_failed",
        "gemini_budget_blocked",
        "cache_lookup",
    ):
        assert f'jsonPayload.message=~"^{name} "' in wr.FILTER


def test_stdin_mode_exits_by_what_it_found(
    wr: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def run(entries: list[dict[str, Any]]) -> int:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(entries)))
        return int(wr.main(["--stdin"]))

    assert run(clean_window()) == 0
    assert run(clean_window(38) + [request(status=500)] * 2) == 1
    assert run([]) == 2
    assert "Crossed a threshold" in capsys.readouterr().out


def test_it_reads_what_the_service_really_writes(
    wr: ModuleType, client: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """A real request through the real middleware and the real JSON formatter, then the report."""
    import logging

    from app.core.logging import JsonFormatter

    caplog.set_level(logging.INFO)
    client.get("/api/v2/flags")  # no token: a 401, which is still a completed request
    formatter = JsonFormatter("test-project")
    entries = [
        {"timestamp": "2026-10-20T10:00:00Z", "jsonPayload": json.loads(formatter.format(record))}
        for record in caplog.records
        if record.getMessage().startswith("request_completed ")
    ]
    assert entries, "the middleware wrote no request_completed line"

    report = wr.build(entries)

    assert report["features"]["platform"]["4xx"] == 1
    route = report["routes"]["GET /api/v2/flags"]
    assert len(route.latencies) == 1 and route.latencies[0] >= 0
