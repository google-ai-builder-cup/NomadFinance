#!/usr/bin/env bash
# Load demo data into Firestore. Run from data-scripts/.
set -euo pipefail

python -m src.loaders.radar_seed
