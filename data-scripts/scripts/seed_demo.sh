#!/usr/bin/env bash
# Load demo data into Firestore. Run from data-scripts/.
set -euo pipefail

# Reference data the demo journey reads and `load_bootstrap.sh` does not load. Both are offline
# and idempotent. The scam patterns need an embedding key (python -m src.loaders.scam_patterns).
python -m src.loaders.cost_baselines
python -m src.loaders.scam_taxonomy

python -m src.loaders.radar_seed
# Auth accounts first (fixed uids, Firebase test phone numbers), so the history below belongs
# to accounts that can sign in. If a number already signs in under another uid, the first
# command reports it; load that user with: seed --only <name> --uid <that uid>
python -m src.loaders.demo_accounts
python -m src.loaders.seed
# Sample contracts for the Contract Shield demo -> gs://<bucket>/demo-samples/contracts/
python -m src.loaders.sample_contracts

# The Coach plan and the five scam checks of each worker (after `seed`: they need the user
# document). Plans and checks are dated from today, so run this again shortly before a demo.
python -m src.loaders.demo_coach
python -m src.loaders.demo_scam

# Last: what a cold account needs that the seed does not write (cost baselines, taxonomy,
# patterns, flags, fresh rates). Exits non-zero, and says which command fixes each gap.
python -m src.loaders.demo_preflight
