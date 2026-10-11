#!/usr/bin/env bash
# Regenerate docs/api/openapi.json from the code (NF-HR-013); pass --check to only compare.
# The work is in export_openapi.py, which also runs on Windows without bash. This wrapper uses
# the backend's own virtualenv when there is one, else whatever `python` is on the PATH.
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin=python
for candidate in .venv/Scripts/python.exe .venv/bin/python; do
  if [ -x "$candidate" ]; then
    python_bin="$candidate"
    break
  fi
done
exec "$python_bin" scripts/export_openapi.py "$@"
