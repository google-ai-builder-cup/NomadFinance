#!/usr/bin/env bash
# Load bootstrap reference data into Firestore. Run from data-scripts/.
set -euo pipefail

python -m src.loaders.corridors

# TODO(Pranjal): call the labor-law loader here once NF-P1-018 lands
# (src/loaders/ilo_natlex.py is still an empty stub).
