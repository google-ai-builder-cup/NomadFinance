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

## Demo users and accounts (NF-P3-021)
Three fictional workers, each a file in `data/seed/users/` (format above): Priya (SG, domestic, India, `hi`), Rajesh (KR, manufacturing, India, `hi`) and Miguel (JP, care, Philippines, `tl`). They are made to score differently: Miguel about 94, Priya 85, Rajesh about 63. Rajesh has no transfers on purpose, because no corridor starts in KR, so his remittance metric shows "no data". Miguel's transfers move from Kapitan Padala (the invented operator flagged in the radar seed) to DCOM Money Express.

`src/loaders/demo_accounts.py` creates one Firebase Auth user per worker, with the uid from the seed file and one of the project's Firebase test phone numbers: `+61 491 570 156` Priya, `157` Rajesh, `158` Miguel. Signing in with a number then shows that worker's history.

```bash
python -m src.loaders.demo_accounts --dry-run   # validate, no Firebase access
python -m src.loaders.demo_accounts             # create the three Auth users
python -m src.loaders.seed                      # write all three histories (also in seed_demo.sh)
```

A number that already signs in under another uid (someone signed in before the accounts were created) is reported and never taken over: load that worker with `seed --only <name> --uid <that uid>` instead. Needs `gcloud auth application-default login`, or `FIREBASE_AUTH_EMULATOR_HOST` and `FIRESTORE_EMULATOR_HOST` for emulators. After loading, run `gcloud scheduler jobs run fib-recompute` to build the profiles.

Full steps, the story in each user's data and limits: [`docs/runbooks/NF-P3-021-demo-users.md`](../docs/runbooks/NF-P3-021-demo-users.md).

## Scam taxonomy (NF-SA-001)
The grounding for the Scam Analyzer: 8 scam types (the seven from the design plus `other_scam`) in `data/source/scam-taxonomy/types.json` and 6 manipulation tactics in `tactics.json`, each with a plain-English definition, 3 to 6 tell-tale signs, a safe response and at least one source (official advisories, read on the date in `retrieved_on`). The labels in other languages are not here: the screens translate by id through the `scam` i18n namespace.

```bash
python -m src.validators.scam_taxonomy        # check both files
python -m src.loaders.scam_taxonomy --dry-run # validate only, no Firestore access
python -m src.loaders.scam_taxonomy           # write
```

The loader writes `scam_taxonomy/{id}` (one document per type or tactic; the id is unique across both) and `scam_taxonomy/_meta` `{version, content_hash, updated_at}` in one batch, after both files have passed the checker's model; if either fails, nothing is written. `_meta.version` goes up by 1 only when the wording changes (sources and curator are not hashed), because a stored check records it as `taxonomy_version` and the check cache ignores checks made under another version. An id removed from the files is deleted from Firestore, and running it again is safe. Options: `--input-dir`, `--collection` (default `scam_taxonomy`). It is not part of `scripts/load_bootstrap.sh`; run it yourself when the files change. Same Firestore identity as the other loaders.

Full steps and results: [`docs/runbooks/NF-SA-001-scam-taxonomy.md`](../docs/runbooks/NF-SA-001-scam-taxonomy.md).

## Scam golden eval sets (NF-SA-003)
Labelled messages the Scam Analyzer is scored against: `evals/scam_golden_en_hi.jsonl` (40 messages, English and Hindi); the Tagalog and Indonesian (NF-SA-004) and Nepali and Bengali (NF-SA-005) sets use the same format and the same checker. The messages are invented; the rules for the labels are in [`docs/evals/scam-golden-set.md`](../docs/evals/scam-golden-set.md).

```bash
python -m src.validators.scam_golden                    # check every evals/scam_golden_*.jsonl
python -m src.validators.scam_golden --spot-check 10    # the 10 rows a second teammate reviews
python -m src.validators.scam_golden --require-reviewed 10   # before merging a set
```

The checker also guards against real data: a link must be on a reserved name (`.example`), an address too, and a long number must hold a run of zeros. `load_rows(path)` is what the eval runner (NF-SA-014) reads the files with. A test (`tests/test_scam_golden.py`) validates the committed files, so data CI fails on a bad row.

`evals/scam_golden_tl_id.jsonl` (NF-SA-004, 40 messages, Tagalog and Indonesian) follows the same format: 14 scams and 6 benign look-alikes per language, every row `script: native` (both languages are written in Latin letters), routes SG-PH, JP-PH and AU-PH for Tagalog and MY-ID for Indonesian. Its 10 rows for the second reviewer: `python -m src.validators.scam_golden evals/scam_golden_tl_id.jsonl --spot-check 10`. Full steps: [`docs/runbooks/NF-SA-004-scam-golden-tl-id.md`](../docs/runbooks/NF-SA-004-scam-golden-tl-id.md).

Full steps and results: [`docs/runbooks/NF-SA-003-scam-golden-en-hi.md`](../docs/runbooks/NF-SA-003-scam-golden-en-hi.md).

`evals/scam_golden_ne_bn.jsonl` (NF-SA-005, 40 messages, Nepali and Bengali) follows the same format: 14 scams and 6 benign look-alikes per language, 17 rows in the language's own script and 3 typed in Latin letters, and a `corridor_id` only where the story fits one (none starts in Nepal or Bangladesh, so Nepali rows carry none and four Bengali rows carry SG-IN or AU-IN). Its 10 rows for the second reviewer: `python -m src.validators.scam_golden evals/scam_golden_ne_bn.jsonl --spot-check 10`. Full steps: [`docs/runbooks/NF-SA-005-scam-golden-ne-bn.md`](../docs/runbooks/NF-SA-005-scam-golden-ne-bn.md).
