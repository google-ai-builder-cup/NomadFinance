#!/usr/bin/env bash
# Load bootstrap reference data into Firestore. Run from data-scripts/.
set -euo pipefail

python -m src.loaders.corridors

python -m src.loaders.ilo_natlex
