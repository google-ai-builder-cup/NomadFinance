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

All six countries are curated as drafts (review and NATLEX record numbers still open). Curator guide: [`data/source/labor-laws/README.md`](data/source/labor-laws/README.md). Full steps, results and limits: [`docs/runbooks/NF-P1-017-labor-law-curation.md`](../docs/runbooks/NF-P1-017-labor-law-curation.md).

## Labor-law loader (NF-P1-018)
Loads the six curated files into Firestore: `labor_laws/{country}` (header), `labor_laws/{country}/rules/{category}` (15 rules) and `labor_laws/{country}/_meta/current` (version). Every file is validated first with the checker's model; if any file fails, nothing is written. `_meta.version` goes up only when a country's rules change (it is what stored contract reports are cached against), so running the loader again is safe.

Same identity requirements as the corridor loader (`gcloud auth application-default login`, or `FIRESTORE_EMULATOR_HOST` pointed at an emulator; project `nomadfinance-prod` unless `FIREBASE_PROJECT_ID` says otherwise).

```bash
python -m src.loaders.ilo_natlex --dry-run   # validate only, no Firestore access
python -m src.loaders.ilo_natlex             # write all curated countries
```

Options: `--only SG JP` (some countries), `--input-dir`, `--collection` (default `labor_laws`), `--require-all` (fail while any file is still `{}`). Each country is written in one batch, so it is never half-loaded. `scripts/load_bootstrap.sh` calls this after the corridor loader.

Full steps and troubleshooting: [`docs/runbooks/NF-P1-018-labor-law-load.md`](../docs/runbooks/NF-P1-018-labor-law-load.md).

## Complaint templates (NF-P2-006)
One JSON file per host country in `data/source/complaint-templates/`: who a worker complains to (authority, channels, official pages checked on 2026-09-28) and the letter frame the backend fills in. Each file holds one `general` template that covers every violation; its `letter_language` is the language the authority works in (`en`, `ko`, `ms`, `ja`). Authority details must be read from the authority's own pages listed in `sources`: a wrong phone number sends a worker to the wrong place.

```bash
python -m src.validators.complaint_template --require-all   # check the six files
python -m src.loaders.complaint_templates --dry-run         # validate only, no Firestore access
python -m src.loaders.complaint_templates                   # write all countries
```

The loader writes `complaint_templates/{country}` (header) and `complaint_templates/{country}/types/{type}` in one batch per country, after every file has passed the checker's model; if any file fails, nothing is written. A type removed from a file is deleted from Firestore, and running it again is safe. There is no version number: a stored report keeps the letter it was made with. Options: `--only SG JP`, `--input-dir`, `--collection` (default `complaint_templates`), `--require-all`. It is not part of `scripts/load_bootstrap.sh`; run it yourself when the files change.

Full steps and results: [`docs/runbooks/NF-P2-006-contract-complaint.md`](../docs/runbooks/NF-P2-006-contract-complaint.md).

## Rate history backfill (D-36, NF-P2-015)
Fetches the European Central Bank's daily reference rates from Frankfurter (no key) for the six corridor pairs and adds them to `rates_history/{pair}.daily`, the series the remittance trends endpoint reads. Days already stored (by the rate cron or an earlier backfill) are never overwritten, so a re-run adds nothing.

```bash
python -m src.loaders.frankfurter_backfill --dry-run   # fetch and count, no Firestore access
python -m src.loaders.frankfurter_backfill             # last 365 days, all six pairs
```

Options: `--days 365` (1 to 3650), `--end YYYY-MM-DD` (default today UTC), `--only SGD_PHP AUD_INR`. Needs internet access to `api.frankfurter.dev`, and the same Firestore identity as the loaders above.

Full steps and results: [`docs/runbooks/NF-P2-015-remittance-trends.md`](../docs/runbooks/NF-P2-015-remittance-trends.md).

## Demo user history (NF-P3-015)
Fictional demo workers in `data/seed/users/*.json` (empty files are skipped until their task fills them). `priya_sg_domestic.json` is Priya, a domestic worker in Singapore who sends money to India: 9 income, 6 transfers, 12 bills and 4 savings entries over 6 months. The loader writes them to `users/{uid}/income|transfers|bills|savings/demo_*`, and `users/{uid}` only if it does not exist yet. It does not create a Firebase Auth user and does not write `financial_profile`: the weekly job computes that.

```bash
python -m src.validators.demo_user                  # check the files
python -m src.loaders.seed --dry-run                # validate and count, no Firestore access
python -m src.loaders.seed                          # write (also run by scripts/seed_demo.sh)
python -m src.loaders.seed --only priya_sg_domestic --uid <firebase uid>   # for a real sign-in account
```

Dates are `months_ago` and `day` in the file, turned into real dates when the loader runs, so the history always ends today; an entry that would fall after today is left out and the next run adds it. Writing again replaces the same `demo_*` ids, deletes `demo_*` entries removed from the file, and never touches an entry with another id. The default uid is `uid_priya_demo`, which nobody can sign in as: use `--uid` with the uid of the account that shows the demo (Firebase console → Authentication → Users). Then run `gcloud scheduler jobs run fib-recompute` to build the profile and report text. Same Firestore identity as the other loaders.

Full steps, the story in the data and limits: [`docs/runbooks/NF-P3-015-fib-demo-user.md`](../docs/runbooks/NF-P3-015-fib-demo-user.md).

## Radar demo data (NF-P3-005)
18 synthetic worker reports in `data/seed/radar-reports/seed_reports.json` covering all six corridors and all six host countries, about 8 invented businesses. The loader writes `radar_reports/seed_NN` (marked `source: "seed"`) and works out each business's `radar_entities/{slug}` profile with the backend's rating rules, so the heatmap, badges and alert cron have data. Alerts are made by the cron, not here.

```bash
python -m src.validators.radar_seed        # check the file
python -m src.loaders.radar_seed --dry-run # validate and show the profiles, no Firestore access
python -m src.loaders.radar_seed           # write (also run by scripts/seed_demo.sh)
```

Timestamps are set from the moment the loader runs, so run it shortly before a demo. Writing again replaces the same ids (no duplicates) and removes seed reports that were taken out of the file. A profile is left alone if a real worker report exists for that business. Same Firestore identity as the other loaders. No embeddings are written.

Full steps and limits: [`docs/runbooks/NF-P3-005-radar-seed-data.md`](../docs/runbooks/NF-P3-005-radar-seed-data.md).


## Sample contracts (NF-P3-020)
Six fictional employment contracts for the Contract Shield demo, one per host country, in `data/seed/contracts/`: `sg_domestic_worker` (fair), `kr_manufacturing_worker`, `hk_domestic_worker`, `au_working_holiday` (risky) and `my_plantation_worker`, `jp_care_worker` (mixed). Each is two pages and mixes sound clauses with breaches of that country's curated labor law; `manifest.json` lists what was planted. The texts are in `source/*.txt` and the PDFs are built from them (English only: the built-in PDF fonts have no CJK or Indic glyphs).

```bash
python -m src.validators.sample_contract            # check manifest, texts and PDFs
python -m src.loaders.sample_contract_pdf           # rebuild the PDFs after editing a text
python -m src.loaders.sample_contract_pdf --check   # fail if a PDF is out of date
python -m src.loaders.sample_contracts --dry-run    # validate, no network access
python -m src.loaders.sample_contracts              # upload (also run by scripts/seed_demo.sh)
```

The uploader writes `demo-samples/contracts/{file}.pdf` in the default bucket (`--bucket` or `FIREBASE_STORAGE_BUCKET` to change it). Browsers cannot read that folder (`storage.rules` only opens `contracts/`, `bills/` and `exports/` per user); download the files from the Firebase console or with `gcloud storage cp`, then upload them in the app like a worker would. Running again changes only what differs and deletes objects no longer in the manifest. Needs `gcloud auth application-default login`, or `STORAGE_EMULATOR_HOST` for an emulator.

Full steps and the rehearsal guide: [`docs/runbooks/NF-P3-020-sample-contracts.md`](../docs/runbooks/NF-P3-020-sample-contracts.md).
