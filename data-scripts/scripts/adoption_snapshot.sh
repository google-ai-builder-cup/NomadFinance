#!/usr/bin/env bash
# The adoption numbers for the pitch (NF-HR-015). Read-only; counts only.
#   ./scripts/adoption_snapshot.sh                       all that is stored, demo workers left out
#   ./scripts/adoption_snapshot.sh --since 2026-10-01 --json /tmp/snapshot.json
# Against the emulator set FIRESTORE_EMULATOR_HOST first; against production, run
# `gcloud auth application-default login` with read access to nomadfinance-prod.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m src.metrics.adoption_snapshot "$@"
