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

## Setup
Requires Python 3.11.9. Run everything from `data-scripts/`.

- PowerShell: `py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1`
- bash: `python3.11 -m venv .venv && source .venv/bin/activate`
- then: `pip install -r requirements-dev.txt`

Checks before every push: `pytest`, `ruff check .`, `black --check .`, `mypy src tests`.

## World Bank RPW parser (NF-P1-015)
Download the Excel first (see [`data/source/README.md`](data/source/README.md)), then:

```bash
python -m src.loaders.world_bank
```

It reads `data/source/rpw_dataset_2011_2025_q1.xlsx` (about 30 s), spot-checks 15 random records against the raw rows and writes `data/processed/rpw_corridors.json`. The JSON is committed so the Firestore loader (NF-P1-016) does not need the Excel. Options: `--period 2025_1Q`, `--sample 15`, `--source`, `--output`.

Result: 6 corridors (SG→PH, SG→IN, AU→IN, MY→ID, JP→PH, AU→PH) with 221 provider records for 2025 Q1. KR→NP is not in RPW, so AU→IN replaces it.

Full steps, output schema and troubleshooting: [`docs/runbooks/NF-P1-015-worldbank-rpw-parse.md`](../docs/runbooks/NF-P1-015-worldbank-rpw-parse.md).

## Corridor loader (NF-P1-016)
Loads the committed `data/processed/rpw_corridors.json` (see above) into Firestore `corridors/{corridor_id}`, adding `source` (name/url/attribution) and `loaded_at`. Re-validates the JSON against the same Pydantic models as the parser before writing anything.

Needs a Firestore-writing identity: either `gcloud auth application-default login` against a project you can write to, or `FIRESTORE_EMULATOR_HOST` pointed at a running Firebase emulator (see `docs/runbooks/NF-P1-014-firestore-security-rules.md` for starting one). Defaults to project `nomadfinance-prod`; override with `FIREBASE_PROJECT_ID`.

```bash
python -m src.loaders.corridors --dry-run   # validate only, no writes
python -m src.loaders.corridors             # write all 6 corridors
```

Options: `--input` (default `data/processed/rpw_corridors.json`), `--collection` (default `corridors`). Writing again is safe: each corridor is a plain `set()` on a fixed id, so a re-run replaces the document instead of duplicating it.

Full steps and troubleshooting: [`docs/runbooks/NF-P1-016-corridor-load.md`](../docs/runbooks/NF-P1-016-corridor-load.md).

## Labor-law curation (NF-P1-017)
One JSON file per host country in `data/source/labor-laws/`, 15 rules each, curated by hand and loaded to Firestore by NF-P1-018. Check your file (and start a new one) with:

```bash
python -m src.validators.labor_law
python -m src.validators.labor_law --template SG --output data/source/labor-laws/SG.json
```

Japan and Hong Kong are done; SG, AU, KR and MY are still empty `{}` stubs. Curator guide: [`data/source/labor-laws/README.md`](data/source/labor-laws/README.md). Full steps, results and limits: [`docs/runbooks/NF-P1-017-labor-law-curation.md`](../docs/runbooks/NF-P1-017-labor-law-curation.md).
