#!/usr/bin/env bash
# Dev server with auto-reload. Production uses gunicorn with uvicorn workers (see Dockerfile).
set -euo pipefail

cd "$(dirname "$0")/.."
exec uvicorn app.main:app --reload --host 127.0.0.1 --port "${PORT:-8080}"
