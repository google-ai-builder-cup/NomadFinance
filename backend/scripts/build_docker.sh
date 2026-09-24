#!/usr/bin/env bash
# Builds the production image locally. Override the tag with IMAGE=<name:tag>.
set -euo pipefail

cd "$(dirname "$0")/.."
exec docker build -t "${IMAGE:-nomadfinance-backend:local}" .
