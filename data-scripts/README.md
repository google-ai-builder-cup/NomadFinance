# NomadFinance — Data Scripts

One-off Python scripts for loading external data into Firestore.

## Sources
•⁠  ⁠*World Bank RPW* — quarterly Excel; provider fees per corridor
•⁠  ⁠*ILO NATLEX* — manually curated per host country; loaded as JSON
•⁠  ⁠*ILOSTAT REST API* — statistical verification of labor law values
•⁠  ⁠*Frankfurter API* — historical FX rate backfill for trend charts

## Host Countries (6, JAPAC)
Singapore (SG), South Korea (KR), Malaysia (MY), Japan (JP), Hong Kong (HK), Australia (AU)

## Structure
•⁠  ⁠⁠ src/loaders/ ⁠ — Parse + write to Firestore
•⁠  ⁠⁠ src/validators/ ⁠ — Schema checks before write
•⁠  ⁠⁠ data/source/ ⁠ — Bootstrap data (large files gitignored)
•⁠  ⁠⁠ data/seed/ ⁠ — Real demo assets loaded ONCE for demo purposes

## Usage
⁠ bash
./scripts/load_bootstrap.sh    # Load WB + ILO to Firestore
./scripts/seed_demo.sh          # Seed demo users, contracts, radar reports
./scripts/refresh_data.sh       # Manual refresh (usually run by Cloud Scheduler)
 ⁠
