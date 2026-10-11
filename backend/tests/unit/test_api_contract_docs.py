"""The API docs against the code (NF-HR-013): the exported OpenAPI file and the route lists.

A deployed API does not serve its OpenAPI document, so `docs/api/openapi.json` is the contract in
machine form. These tests fail when a route or a model changes and the export or the docs do not.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

from fastapi.routing import APIRoute

from app.api.v1 import internal

REPO = Path(__file__).resolve().parents[3]
API_DOCS = REPO / "docs" / "api"
EXPORT_SCRIPT = REPO / "backend" / "scripts" / "export_openapi.py"

# The pages that name routes. `v2-conventions.md` only has made-up example paths.
ROUTE_PAGES = ("endpoints.md", "v2-flags.md", "v2-scam.md", "v2-coach.md")

_METHODS = "GET|POST|PUT|PATCH|DELETE"
# A route is "named" in a heading or in a table row: `POST /api/v2/x` or | `POST` | `/api/v2/x` |.
_INLINE = re.compile(rf"`({_METHODS}) (/[^`\s?]+)")
_TABLE = re.compile(rf"\|\s*`?({_METHODS})`?\s*\|\s*`(/[^`\s?]+)`")


def _shape(path: str) -> str:
    """`/a/{contract_id}` and `/a/{id}` are the same route."""
    return re.sub(r"\{[^}]*\}", "{}", path)


def _export() -> ModuleType:
    spec = importlib.util.spec_from_file_location("export_openapi", EXPORT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_openapi"] = module
    spec.loader.exec_module(module)
    return module


def _code_routes() -> set[tuple[str, str]]:
    """Every route the app serves: the OpenAPI paths plus the Cloud Scheduler jobs.

    Only the `internal` router is hidden from the document (`include_in_schema=False`), so its
    routes are read from the router, under the `/api/v1` prefix `app.main` gives it.
    """
    found: set[tuple[str, str]] = set()
    for path, operations in _export().build_spec()["paths"].items():
        found.update((method.upper(), _shape(path)) for method in operations)
    for route in internal.router.routes:
        if isinstance(route, APIRoute):
            found.update((method, _shape(f"/api/v1{route.path}")) for method in route.methods or ())
    return found


def _documented_routes() -> dict[tuple[str, str], list[str]]:
    found: dict[tuple[str, str], list[str]] = {}
    for page in ROUTE_PAGES:
        for line in (API_DOCS / page).read_text(encoding="utf-8").splitlines():
            if not line.startswith(("|", "#")):
                continue
            for method, path in [*_INLINE.findall(line), *_TABLE.findall(line)]:
                if path.startswith(("/api/v", "/health")):
                    found.setdefault((method, _shape(path)), []).append(page)
    return found


def test_openapi_file_is_what_the_code_builds() -> None:
    committed = json.loads((API_DOCS / "openapi.json").read_text(encoding="utf-8"))
    assert committed == _export().build_spec(), (
        "docs/api/openapi.json is out of date. Regenerate it with "
        "`python scripts/export_openapi.py` from backend/ and commit the result."
    )


def test_every_route_is_in_the_docs_and_every_documented_route_exists() -> None:
    code = _code_routes()
    documented = set(_documented_routes())
    assert code - documented == set(), "routes with no heading or table row in docs/api"
    assert documented - code == set(), "routes in docs/api that the app does not serve"
