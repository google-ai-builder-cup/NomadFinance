from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

from app.core.features import FEATURES, PLATFORM, feature_for_path
from app.main import create_app


@pytest.mark.parametrize(
    ("path", "feature"),
    [
        ("/api/v1/contracts/extract", "contract"),
        ("/api/v1/contracts/C0123/analyze", "contract"),
        ("/api/v1/remittance/compare", "remittance"),
        ("/api/v1/radar/report", "radar"),
        ("/api/v1/fib/income", "fib"),
        ("/api/v2/coach/sessions", "coach"),
        ("/api/v2/scam/analyze", "scam"),
        ("/api/v1/internal/refresh-rates", "remittance"),
        ("/api/v1/internal/aggregate-radar", "radar"),
        ("/api/v1/internal/recompute-fib-profiles", "fib"),
        ("/api/v1/internal/something-new", PLATFORM),
        ("/api/v1/internal", PLATFORM),
        ("/api/v2/flags", PLATFORM),
        ("/api/v1/users/me", PLATFORM),
        ("/health", PLATFORM),
        ("/", PLATFORM),
        ("", PLATFORM),
        ("/api/v1", PLATFORM),
        ("/elsewhere/contracts/extract", PLATFORM),
    ],
)
def test_a_path_belongs_to_the_feature_its_first_segment_names(path: str, feature: str) -> None:
    assert feature_for_path(path) == feature


def _paths(routes: list[BaseRoute]) -> Iterator[str]:
    """Every endpoint's full path. Included routers expose one context per endpoint."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route.path
        elif hasattr(route, "effective_route_contexts"):
            contexts: Any = route.effective_route_contexts()
            yield from (context.path for context in contexts)


def test_every_feature_name_is_a_known_one() -> None:
    assert set(FEATURES) == {"contract", "remittance", "radar", "fib", "coach", "scam", "platform"}


def test_a_new_route_is_not_silently_filed_under_platform() -> None:
    # The only routes that are `platform` on purpose. A new pillar route that is missing from
    # `_BY_SEGMENT` shows up here, so its requests are not lost from the per-feature charts.
    intended = {
        "/health",
        "/api/v2/flags",
        "/api/v1/users/me",
    }
    app = create_app()
    platform = {path for path in _paths(app.routes) if feature_for_path(path) == PLATFORM}

    assert platform == intended
