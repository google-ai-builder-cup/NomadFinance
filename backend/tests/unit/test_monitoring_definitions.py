"""The metric, dashboard and alert definitions in infra/monitoring/ against the real log lines.

Nothing here talks to Google. A tiny evaluator applies each metric's filter and label extractors to
the JSON the backend really writes (`JsonFormatter` on records from the real middleware and the
real Gemini client), so a renamed log field or a changed filter fails a test, not a dashboard.
What it cannot show is that Google accepts the definitions: that needs the setup script run once.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from app.config import get_settings
from app.core.cache import log_cache_lookup
from app.core.logging import JsonFormatter
from app.integrations.gemini import GeminiBudget, GeminiBudgetExhaustedError, GeminiError, ModelTier
from app.integrations.gemini.embeddings import EMBEDDING_DIMENSION
from app.integrations.gemini.usage import log_failure
from app.main import create_app
from tests.unit.integrations.test_gemini_client import OK, api_error, generate, make_client
from tests.unit.integrations.test_gemini_embeddings import _client as embed_client
from tests.unit.integrations.test_gemini_embeddings import _error as embed_error
from tests.unit.integrations.test_gemini_embeddings import _response as embed_response

pytestmark = pytest.mark.anyio

MONITORING = Path(__file__).resolve().parents[3] / "infra" / "monitoring"
RESOURCE = {
    "resource.type": "cloud_run_revision",
    "resource.labels.service_name": "nomadfinance-api",
}


def _load(relative: str) -> Any:
    return json.loads((MONITORING / relative).read_text(encoding="utf-8"))


METRICS: dict[str, dict[str, Any]] = {
    path.stem: json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((MONITORING / "metrics").glob("*.json"))
}


def _renderer() -> Any:
    spec = importlib.util.spec_from_file_location(
        "render_policies", MONITORING / "render_policies.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- a small evaluator for the filters and extractors used in the metric files ---------------


def _lookup(payload: dict[str, Any], path: str) -> Any:
    if path in RESOURCE:
        return RESOURCE[path]
    assert path.startswith("jsonPayload."), f"unsupported field {path}"
    value: Any = payload
    for part in path.removeprefix("jsonPayload.").split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _clause(payload: dict[str, Any], clause: str) -> bool:
    match = re.fullmatch(r'([\w.]+)\s*(=~|>=|=)\s*(?:"(.*)"|(-?\d+))', clause.strip())
    assert match, f"unsupported filter clause: {clause}"
    field, operator, text, number = match.groups()
    value = _lookup(payload, field)
    if value is None:
        return False
    if operator == "=~":
        return re.search(text, str(value)) is not None
    if operator == "=":
        return str(value) == text
    return isinstance(value, int | float) and value >= int(number)


def matches(metric: dict[str, Any], payload: dict[str, Any]) -> bool:
    return all(_clause(payload, clause) for clause in metric["filter"].split(" AND "))


def extract(expression: str, payload: dict[str, Any]) -> Any:
    match = re.fullmatch(r"EXTRACT\((jsonPayload[\w.]+)\)", expression)
    assert match, f"unsupported extractor: {expression}"
    return _lookup(payload, match.group(1))


# --- the real log lines ------------------------------------------------------------------------


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.lines: list[dict[str, Any]] = []
        self._formatter = JsonFormatter("proj-x")

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(json.loads(self._formatter.format(record)))


def _by_start(lines: list[dict[str, Any]], start: str) -> list[dict[str, Any]]:
    return [line for line in lines if line["message"].startswith(start)]


@pytest.fixture
def collected() -> Any:
    handler = _Collect()
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    yield handler
    root.removeHandler(handler)
    root.setLevel(previous)


async def _every_kind_of_line(collected: _Collect) -> dict[str, dict[str, Any]]:
    unavailable = api_error(genai_errors.ServerError, 503, "UNAVAILABLE")

    app: FastAPI = create_app()

    @app.get("/api/v1/radar/_boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as http:
        http.get("/api/v1/remittance/trends")  # 401, a client error
        http.get("/api/v1/radar/_boom")  # 500, a server error

    client, _ = make_client([unavailable, OK])
    await generate(client)  # one retry, then an answer
    failing, _ = make_client([unavailable, unavailable, unavailable])
    with pytest.raises(GeminiError):
        await generate(failing)  # three attempts, gives up
    embedder, _ = embed_client(
        [
            embed_error(genai_errors.ServerError, 503, "UNAVAILABLE"),
            embed_response([1.0] * EMBEDDING_DIMENSION),
        ]
    )
    await embedder.embed_text("x", operation="radar.embed")
    # The two endings that are not failures: the worker went away, and a caller stopped a stream.
    # Both are still requests the model counted.
    for outcome, error in (("cancelled", asyncio.CancelledError()), ("closed", None)):
        log_failure(
            error,
            operation="test.stream",
            tier=ModelTier.REASONING,
            model=get_settings().gemini_model_reasoning,
            latency_ms=1,
            attempts=1,
            outcome=outcome,
        )

    # A refusal before any request (NF-HR-010), and the two answers a cache can give.
    budget = GeminiBudget(None, {"reasoning": 4})
    await budget.admit("scam", "reasoning")
    with pytest.raises(GeminiBudgetExhaustedError):
        await budget.admit("scam", "reasoning")
    log_cache_lookup("scam", "check", hit=True)
    log_cache_lookup("scam", "check", hit=False)

    lines = collected.lines
    requests = _by_start(lines, "request_completed")
    lookups = _by_start(lines, "cache_lookup")
    return {
        "blocked": _by_start(lines, "gemini_budget_blocked")[0],
        "cache_hit": next(line for line in lookups if line["cache_lookup"]["result"] == "hit"),
        "cache_miss": next(line for line in lookups if line["cache_lookup"]["result"] == "miss"),
        "client_error": next(line for line in requests if line["status"] == 401),
        "server_error": next(line for line in requests if line["status"] == 500),
        "call": _by_start(lines, "gemini_call ")[0],
        "retry": _by_start(lines, "gemini_retry")[0],
        "failed": next(
            line
            for line in _by_start(lines, "gemini_call_failed")
            if line["gemini_usage"]["outcome"] == "failed"
        ),
        "cancelled": next(
            line
            for line in _by_start(lines, "gemini_call_failed")
            if line["gemini_usage"]["outcome"] == "cancelled"
        ),
        "closed": next(
            line
            for line in _by_start(lines, "gemini_call_failed")
            if line["gemini_usage"]["outcome"] == "closed"
        ),
        "embedding": _by_start(lines, "gemini_call ")[-1],
    }


# --- the metrics -------------------------------------------------------------------------------


def test_the_seven_metrics_exist() -> None:
    assert set(METRICS) == {
        "nf_gemini_budget_blocks",
        "nf_cache_lookups",
        "nf_http_requests",
        "nf_gemini_requests",
        "nf_gemini_failures",
        "nf_gemini_tokens_in",
        "nf_gemini_tokens_out",
    }


@pytest.mark.parametrize("name", sorted(METRICS))
def test_a_metric_is_well_formed(name: str) -> None:
    metric = METRICS[name]
    labels = {label["key"] for label in metric["metricDescriptor"]["labels"]}

    assert labels == set(metric["labelExtractors"])
    assert metric["metricDescriptor"]["metricKind"] == "DELTA"
    if metric["metricDescriptor"]["valueType"] == "DISTRIBUTION":
        assert "valueExtractor" in metric and "bucketOptions" in metric
    else:
        assert "valueExtractor" not in metric and "bucketOptions" not in metric


async def test_each_metric_matches_exactly_the_lines_it_is_for(collected: _Collect) -> None:
    lines = await _every_kind_of_line(collected)

    def matched(name: str) -> set[str]:
        return {kind for kind, payload in lines.items() if matches(METRICS[name], payload)}

    assert matched("nf_http_requests") == {"client_error", "server_error"}
    # Every attempt is one line: an answer, a give-up, a retry, and the embedding model's too.
    assert matched("nf_gemini_requests") == {
        "call",
        "retry",
        "failed",
        "cancelled",
        "closed",
        "embedding",
    }
    # Only a call that gave up is a failure: a cancelled or a closed one is not.
    assert matched("nf_gemini_failures") == {"failed"}
    # Tokens come only from answered chat calls: an embedding has no token counts.
    assert matched("nf_gemini_tokens_in") == {"call"}
    assert matched("nf_gemini_tokens_out") == {"call"}
    # A refusal made here is not a request to Google, so no request metric counts it (above), and
    # only its own metric does. Caches: every lookup, hit or miss.
    assert matched("nf_gemini_budget_blocks") == {"blocked"}
    assert matched("nf_cache_lookups") == {"cache_hit", "cache_miss"}


async def test_every_label_a_metric_extracts_has_a_value(collected: _Collect) -> None:
    lines = await _every_kind_of_line(collected)

    for name, metric in METRICS.items():
        for payload in (p for p in lines.values() if matches(metric, p)):
            for label, expression in metric["labelExtractors"].items():
                assert extract(expression, payload), f"{name}: label {label} is empty"


async def test_the_labels_carry_the_values_a_dashboard_expects(collected: _Collect) -> None:
    lines = await _every_kind_of_line(collected)
    settings = get_settings()

    def label(name: str, kind: str, key: str) -> Any:
        return extract(METRICS[name]["labelExtractors"][key], lines[kind])

    assert label("nf_http_requests", "client_error", "feature") == "remittance"
    assert label("nf_http_requests", "client_error", "status_class") == "4xx"
    assert label("nf_http_requests", "server_error", "feature") == "radar"
    assert label("nf_http_requests", "server_error", "status_class") == "5xx"
    assert label("nf_gemini_requests", "call", "model") == settings.gemini_model_reasoning
    assert label("nf_gemini_requests", "call", "feature") == "test"
    assert label("nf_gemini_requests", "embedding", "model") == settings.gemini_model_embedding
    assert label("nf_gemini_failures", "failed", "error") == "GeminiUnavailableError"
    assert label("nf_gemini_budget_blocks", "blocked", "feature") == "scam"
    assert label("nf_gemini_budget_blocks", "blocked", "tier") == "reasoning"
    assert label("nf_gemini_budget_blocks", "blocked", "source") == "budget"
    assert label("nf_cache_lookups", "cache_hit", "feature") == "scam"
    assert label("nf_cache_lookups", "cache_hit", "result") == "hit"
    assert label("nf_cache_lookups", "cache_miss", "result") == "miss"


async def test_the_token_distributions_read_a_number(collected: _Collect) -> None:
    lines = await _every_kind_of_line(collected)

    assert extract(METRICS["nf_gemini_tokens_in"]["valueExtractor"], lines["call"]) == 12
    assert extract(METRICS["nf_gemini_tokens_out"]["valueExtractor"], lines["call"]) == 7


async def test_the_requests_metric_counts_what_the_model_saw(collected: _Collect) -> None:
    """Retried attempts count, and so do calls that ended without an error."""
    await _every_kind_of_line(collected)
    chat = [
        line
        for line in collected.lines
        if matches(METRICS["nf_gemini_requests"], line)
        and line["gemini_usage"]["model"] == get_settings().gemini_model_reasoning
    ]

    # 2 for retry-then-answer, 3 for three failed attempts, and the cancelled and closed ones.
    assert len(chat) == 2 + 3 + 2


# --- the dashboard -----------------------------------------------------------------------------


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for value in node.values() for s in _strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in _strings(value)]
    return []


def test_the_dashboard_only_uses_metrics_and_labels_that_exist() -> None:
    dashboard = _load("dashboard.json")
    used = _strings(dashboard)

    for text in used:
        for name in re.findall(r"logging\.googleapis\.com/user/(\w+)", text):
            assert name in METRICS, f"dashboard uses a metric that is not defined: {name}"
        for name in re.findall(r"logging_googleapis_com:user_(\w+?)_sum", text):
            assert METRICS[name]["metricDescriptor"]["valueType"] == "DISTRIBUTION", name
    for widget in dashboard["gridLayout"]["widgets"]:
        for data_set in widget.get("xyChart", {}).get("dataSets", []):
            query = data_set["timeSeriesQuery"].get("timeSeriesFilter")
            if query is None:
                continue
            name = re.search(r"user/(\w+)", query["filter"]).group(1)  # type: ignore[union-attr]
            allowed = {f"metric.label.{k}" for k in METRICS[name]["labelExtractors"]}
            used_labels = set(re.findall(r"metric\.label\.\w+", query["filter"]))
            used_labels |= set(query["aggregation"]["groupByFields"])
            assert used_labels <= allowed, f"{widget['title']}: {used_labels - allowed}"


def test_the_dashboard_has_the_charts_the_tracker_asks_for() -> None:
    titles = " | ".join(w["title"] for w in _load("dashboard.json")["gridLayout"]["widgets"])

    assert "Requests per feature" in titles
    assert "Server errors (5xx) per feature" in titles
    assert "Gemini failures per feature" in titles
    assert "Prompt tokens per feature" in titles
    assert "Answer + thinking tokens per feature" in titles
    # NF-HR-010: the refusals and the cache hit rate, so the guard can be watched.
    assert "refused by the daily budget" in titles
    assert "Cache lookups per feature" in titles


# --- the quota alerts --------------------------------------------------------------------------


def test_the_limits_file_covers_every_model_the_app_is_configured_to_use() -> None:
    settings = get_settings()
    configured = {
        settings.gemini_model_reasoning,
        settings.gemini_model_extraction,
        settings.gemini_model_classification,
        settings.gemini_model_embedding,
    }

    assert set(_load("quota-limits.json")["models"]) == configured


def test_an_alert_fires_at_80_percent_of_the_models_daily_limit() -> None:
    template = _load("alert-policy.template.json")
    limits = _load("quota-limits.json")
    limits["models"]["gemini-3.5-flash"]["rpd"] = 1000

    policies, skipped = _renderer().render_policies(
        limits, template, ["projects/p/notificationChannels/1"]
    )

    policy = policies["gemini-3.5-flash"]
    condition = policy["conditions"][0]["conditionThreshold"]
    assert condition["thresholdValue"] == 800
    assert 'metric.label.model="gemini-3.5-flash"' in condition["filter"]
    assert policy["notificationChannels"] == ["projects/p/notificationChannels/1"]
    assert "__" not in json.dumps(policy), "a placeholder was left in the policy"
    assert "gemini-3.5-flash-lite" in skipped  # no limit given, so no alert


def test_the_threshold_is_rounded_down_so_it_never_waits_past_80_percent() -> None:
    limits = _load("quota-limits.json")
    limits["models"]["gemini-3.1-flash-lite"]["rpd"] = 333

    policies, _ = _renderer().render_policies(limits, _load("alert-policy.template.json"), [])

    condition = policies["gemini-3.1-flash-lite"]["conditions"][0]["conditionThreshold"]
    assert condition["thresholdValue"] == 266
    assert "notificationChannels" not in policies["gemini-3.1-flash-lite"]


def test_a_model_with_no_limit_is_skipped_and_named_not_given_a_made_up_number() -> None:
    policies, skipped = _renderer().render_policies(
        _load("quota-limits.json"), _load("alert-policy.template.json"), []
    )

    assert policies == {}
    assert set(skipped) == set(_load("quota-limits.json")["models"])


@pytest.mark.parametrize("bad", [0, -5, 12.5, "1500", True])
def test_a_nonsense_limit_is_refused(bad: object) -> None:
    limits = _load("quota-limits.json")
    limits["models"]["gemini-3.5-flash"]["rpd"] = bad

    with pytest.raises(ValueError, match="rpd for gemini-3.5-flash"):
        _renderer().render_policies(limits, _load("alert-policy.template.json"), [])


@pytest.mark.parametrize("fraction", [0, -0.1, 1.5])
def test_a_nonsense_fraction_is_refused(fraction: float) -> None:
    limits = _load("quota-limits.json")
    limits["alert_at_fraction"] = fraction

    with pytest.raises(ValueError, match="alert_at_fraction"):
        _renderer().render_policies(limits, _load("alert-policy.template.json"), [])


def test_the_alert_watches_the_metric_the_dashboard_shows() -> None:
    template = _load("alert-policy.template.json")
    condition = template["conditions"][0]["conditionThreshold"]
    name = re.search(r"user/(\w+)", condition["filter"]).group(1)  # type: ignore[union-attr]

    assert name == "nf_gemini_requests"
    assert name in METRICS
    assert "model" in METRICS[name]["labelExtractors"]
    # The same window the "rolling 23.5 h" chart on the dashboard plots.
    assert condition["aggregations"][0]["alignmentPeriod"] == "84600s"


# --- the alerts of the rollout watch (NF-HR-017) ---------------------------------------------


def _service_alert(name: str) -> dict[str, Any]:
    return _load(f"service-alerts/{name}.json")


def test_the_server_error_alert_is_a_share_of_the_requests_metric_with_a_volume_floor() -> None:
    policy = _service_alert("server-errors")
    share, volume = (c["conditionThreshold"] for c in policy["conditions"])

    assert policy["combiner"] == "AND", "a share alone fires on one failure of three requests"
    assert 'metric.label.status_class="5xx"' in share["filter"]
    assert (
        share["denominatorFilter"] == 'metric.type="logging.googleapis.com/user/nf_http_requests"'
    )
    assert share["comparison"] == "COMPARISON_GT" and share["thresholdValue"] == 0.05
    assert volume["thresholdValue"] == 20
    # The same window for the numerator, the denominator and the floor.
    windows = {
        share["aggregations"][0]["alignmentPeriod"],
        share["denominatorAggregations"][0]["alignmentPeriod"],
        volume["aggregations"][0]["alignmentPeriod"],
    }
    assert windows == {"900s"}


def test_the_server_error_alert_uses_a_metric_and_a_label_that_exist() -> None:
    share = _service_alert("server-errors")["conditions"][0]["conditionThreshold"]

    name = re.search(r"user/(\w+)", share["filter"]).group(1)  # type: ignore[union-attr]

    assert name in METRICS
    assert "status_class" in METRICS[name]["labelExtractors"]


def test_the_latency_alert_is_the_95th_percentile_of_cloud_runs_own_metric() -> None:
    condition = _service_alert("slow-requests")["conditions"][0]["conditionThreshold"]

    assert 'metric.type="run.googleapis.com/request_latencies"' in condition["filter"]
    assert 'resource.labels.service_name="nomadfinance-api"' in condition["filter"]
    assert condition["aggregations"][0]["perSeriesAligner"] == "ALIGN_PERCENTILE_95"
    # Above a route that waits for Gemini by design (a plan takes 20 to 40 s at its slowest).
    assert condition["thresholdValue"] == 30000


def test_each_service_alert_says_what_to_do_and_where_the_runbook_is() -> None:
    names = set()
    for file in sorted((MONITORING / "service-alerts").glob("*.json")):
        policy = json.loads(file.read_text(encoding="utf-8"))
        names.add(policy["displayName"])

        assert "NF-HR-017-rollout-watch.md" in policy["documentation"]["content"]
        assert "__" not in json.dumps(policy), "a placeholder was left in the policy"
        assert policy["alertStrategy"]["autoClose"] == "86400s"
    assert len(names) == 2


def test_the_service_alerts_are_made_even_when_no_model_has_a_limit(tmp_path: Path) -> None:
    code = _renderer().main(
        ["render_policies.py", str(tmp_path), "projects/p/notificationChannels/1"]
    )

    made = sorted(file.name for file in tmp_path.glob("*.json"))
    assert code == _renderer().SKIPPED_EXIT_CODE  # the models are still skipped, and said so
    assert "service-server-errors.json" in made and "service-slow-requests.json" in made
    policy = json.loads((tmp_path / "service-server-errors.json").read_text(encoding="utf-8"))
    assert policy["notificationChannels"] == ["projects/p/notificationChannels/1"]
