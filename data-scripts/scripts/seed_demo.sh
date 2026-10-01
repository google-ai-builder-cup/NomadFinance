#!/usr/bin/env bash
# Load demo data into Firestore. Run from data-scripts/.
set -euo pipefail

python -m src.loaders.radar_seed
# Writes under uid_priya_demo, which no one can sign in as. For a real demo account:
#   python -m src.loaders.seed --only priya_sg_domestic --uid <that account's uid>
python -m src.loaders.seed
