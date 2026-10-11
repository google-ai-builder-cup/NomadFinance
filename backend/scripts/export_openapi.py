"""Write the API's OpenAPI document to `docs/api/openapi.json` (NF-HR-013).

A deployed API does not serve `/openapi.json` (NF-P4-004), so this file is the one place the
machine-readable contract is kept. Run it after any change to a route or to a request or
response model, and commit the result:

    python scripts/export_openapi.py            # write docs/api/openapi.json
    python scripts/export_openapi.py --check    # exit 1 when the file is out of date

The document is built from the code with the title and the version pinned to the setting
defaults and `.env.local` shadowed, so two machines write the same file. The routes hidden from
it on purpose (`/api/v1/internal/*`, called by Cloud Scheduler only) are not in it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
OUTPUT = BACKEND.parent / "docs" / "api" / "openapi.json"


@contextmanager
def _pinned_settings() -> Iterator[None]:
    """Settings that do not depend on the machine, put back as they were afterwards.

    An environment variable wins over `.env.local`, so a developer's copy of the example file
    (which sets `APP_VERSION`) cannot change the title or the version of the document.
    """
    from app.config import Settings, get_settings

    pinned = {
        "APP_ENV": "local",
        "APP_NAME": str(Settings.model_fields["app_name"].default),
        "APP_VERSION": str(Settings.model_fields["app_version"].default),
        # Required at startup; the document is built without calling Gemini or Firestore.
        "GEMINI_API_KEY": "placeholder-not-a-key",
        "RADAR_REPORTER_HASH_SECRET": "placeholder-not-a-secret",
    }
    saved = {name: os.environ.get(name) for name in pinned}
    os.environ.update(pinned)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        get_settings.cache_clear()


def build_spec() -> dict[str, Any]:
    """The OpenAPI document of the app as `create_app()` builds it."""
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    with _pinned_settings():
        from app.main import create_app

        spec: dict[str, Any] = create_app().openapi()
    return spec


def render(spec: dict[str, Any]) -> str:
    # ensure_ascii off keeps the non-English descriptions readable in a diff.
    return json.dumps(spec, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="do not write; exit 1 if out of date")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="file to write or compare")
    args = parser.parse_args(argv)

    spec = build_spec()
    if args.check:
        # Parsed, not byte for byte: a Windows checkout may hold the file with CRLF line ends.
        current = (
            json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else None
        )
        if current == spec:
            print(f"{args.output} is up to date")
            return 0
        print(f"{args.output} is out of date. Run: python scripts/export_openapi.py")
        return 1

    # newline="" so the file is written with LF whatever the platform.
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        handle.write(render(spec))
    paths = len(spec["paths"])
    print(f"wrote {args.output} (version {spec['info']['version']}, {paths} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
