#!/usr/bin/env bash
# Load demo data into Firestore. Run from data-scripts/.
set -euo pipefail

python -m src.loaders.radar_seed
# Auth accounts first (fixed uids, Firebase test phone numbers), so the history below belongs
# to accounts that can sign in. If a number already signs in under another uid, the first
# command reports it; load that user with: seed --only <name> --uid <that uid>
python -m src.loaders.demo_accounts
python -m src.loaders.seed
# Sample contracts for the Contract Shield demo -> gs://<bucket>/demo-samples/contracts/
python -m src.loaders.sample_contracts
