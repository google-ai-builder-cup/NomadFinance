# NF-P1-015 — Download and Parse World Bank RPW Data

## Summary

The World Bank **Remittance Prices Worldwide (RPW)** workbook lists what real providers charge to send money along hundreds of corridors. `data-scripts/src/loaders/world_bank.py` reads it with pandas + openpyxl, keeps our 6 corridors for the newest survey quarter, validates every record with Pydantic and writes **`data-scripts/data/processed/rpw_corridors.json`**. That JSON is committed, so the Firestore loader (NF-P1-016, Aditya) and the remittance engine (NF-P2-014) never need the 49 MB Excel.

This task only parses. Nothing is written to Firestore.

**Result (2025 Q1, the newest quarter RPW publishes):** 6 corridors, **221 provider records**.

| Corridor | RPW code | Records |
|---|---|---|
| SG→PH | `SGPPHL` | 39 |
| SG→IN | `SGPIND` | 29 |
| AU→IN | `AUSIND` | 35 |
| MY→ID | `MYSIDN` | 42 |
| JP→PH | `JPNPHL` | 44 |
| AU→PH | `AUSPHL` | 32 |

## Things the team must know

1. **The corridor list changed: AU→IN replaced KR→NP.** RPW has no KR→NP data at all. Korea is only surveyed as a sender to Vietnam and China, and Nepal only receives from AE, GB, IN, MY, OM, QA, SA and US. AU→IN is fully covered (35 records from 20 providers, all in AUD). The team scope is now: **SG→PH, SG→IN, AU→IN, MY→ID, JP→PH, AU→PH**. It was updated in `CLAUDE.md`, `README.md`, the tracker note for NF-P1-015 and the parser config. Anything still saying KR→NP is out of date.
   - **Not changed:** South Korea (KR) is still one of the 6 **host countries** (Contract Shield labor laws, NF-P1-017, the Rajesh demo user). Only the money corridor was replaced.
   - **Not changed, still open:** the language list still has Nepali (`ne`), which was there for KR→NP workers. Whether to keep it is a separate team decision.
2. **The tracker said "about 48 records". Reality is 221.** The tracker estimate was about 8 providers per corridor. RPW records one row per *service* (firm + how the sender pays + access point + how the receiver collects), so one firm appears several times. We keep every surveyed service so the engine can filter cash vs bank pickup. It is still tiny (198 KB).
3. **The data is from Q1 2025.** RPW has not published anything newer. Records carry `surveyed_on`, so the UI can say "prices surveyed Feb–Mar 2025". Do not present them as live.
4. **Six services pay out in USD, not local currency.** For DBS (SG→PH, SG→IN) and GoRemit, Japan Post Bank and Metro Bank (JP→PH) the quoted `fx_rate` is USD per sending currency. Those records have `payout_currency: "USD"`. Their `total_cost_pct` is still comparable, but **their `fx_rate` must not be used in a "recipient receives" comparison** against local-currency providers.
5. **Negative costs are real.** Five quotes have a negative total cost because the provider's exchange rate beat the interbank rate: InstaReM on AU→IN (−0.24% at both USD 200 and 500) and three MoneyGram services on AU→PH at USD 500 (−1.15%, −1.13%, −0.76%). The model allows −20 to 100.
6. **Use the reported `total_cost_pct`, do not recompute it.** Recomputing `1 − (send − fee) × fx_rate ÷ (send × interbank_rate)` matches within 0.8 percentage points (most within 0.05). The gap is rounding in the published rates. RPW's figure is the authoritative one.
7. **A corridor with no rows stops the parser.** All 6 corridors exist in RPW, so zero rows means a wrong code in `config.py`, not a real gap. The script fails with the corridor name instead of writing an empty corridor.
8. **Attribution is mandatory** wherever the data is shown: "The World Bank, Remittance Prices Worldwide, available at http://remittanceprices.worldbank.org". It is stored in the JSON under `source.attribution`. Do not use the World Bank logo or imply endorsement.

## Files

| File | Purpose |
|---|---|
| `data-scripts/src/config.py` | Paths, sheet name, attribution text and the 6-corridor table (ids, RPW codes, currencies) |
| `data-scripts/src/loaders/world_bank.py` | Read the sheet, build one document per corridor, write the JSON. Also the command-line entry point. |
| `data-scripts/src/validators/corridor.py` | Pydantic v2 models (the output contract) and the check against the raw sheet |
| `data-scripts/tests/test_loaders.py` | 18 tests |
| `data-scripts/data/processed/rpw_corridors.json` | The parsed output, committed |
| `data-scripts/data/source/README.md` | How to download the Excel (the Excel itself is gitignored) |
| `data-scripts/requirements.txt`, `requirements-dev.txt`, `pyproject.toml` | Pinned dependencies and lint/type settings (same rules as the backend) |
| `data-scripts/README.md` | Setup and usage section added |

## Flow

```
rpw_dataset_2011_2025_q1.xlsx   (download once, gitignored)
  └─ sheet "Dataset (from Q2 2016)"   ~198,000 rows, 42 columns
       └─ keep rows where corridor = SGPPHL, SGPIND, AUSIND, MYSIDN, JPNPHL, AUSPHL
            └─ keep the newest period (2025_1Q)
                 └─ one ProviderRecord per row (Pydantic validation, rounding, USD-payout tag)
                      └─ spot-check 15 random records against the raw rows
                           └─ data/processed/rpw_corridors.json   (committed)
                                └─ NF-P1-016 loads it into Firestore corridors/{corridor_id}
```

RPW corridor codes are the source and destination ISO-3 codes joined: `AUS`+`IND` = `AUSIND`.

## All commands, in order

Everything runs from the `data-scripts/` folder.

### 0. Prerequisites

- Python 3.11.9 (`python3.11 --version`, PowerShell: `py -3.11 --version`).
- The Excel file, downloaded by hand (step 1).

### 1. Download the RPW Excel (once per person)

The direct link is behind a Cloudflare check, so use a normal browser. Scripts and `curl` get a 403.

1. Open <https://remittanceprices.worldbank.org/data-download>.
2. Click the link "RPW dataset request form". This downloads `rpw_dataset_2011_2025_q1.xlsx` (about 49 MB).
3. Put it at `data-scripts/data/source/rpw_dataset_2011_2025_q1.xlsx`. Keep the exact name.

Check it landed:

**bash**
```bash
ls -l data/source/rpw_dataset_2011_2025_q1.xlsx
```

**Windows PowerShell**
```powershell
Get-Item data\source\rpw_dataset_2011_2025_q1.xlsx
```

The file is gitignored (`*.xlsx`), so `git status` will not show it. That is expected.

### 2. Create the virtualenv and install dependencies

**bash**
```bash
cd data-scripts
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

**Windows PowerShell**
```powershell
cd data-scripts
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Expected: `pip list` shows pandas 3.0.6, openpyxl 3.1.5, pydantic 2.13.5. Do not reuse the `backend/` virtualenv; it has no pandas.

### 3. Run the parser

```bash
python -m src.loaders.world_bank
```

Run it with `-m` from `data-scripts/`; running the file directly fails to find `src`. It takes about 20 seconds, most of it reading the Excel. Expected output:

```
Reading .../data/source/rpw_dataset_2011_2025_q1.xlsx (about 30 s)
  verified: AU-IN id 521251290 Aussie Forex & Finance: cost@200=1.09% cost@500=0.79% -> OK
  ... 14 more verified lines, all OK ...
SG-PH   39 records
SG-IN   29 records
AU-IN   35 records
MY-ID   42 records
JP-PH   44 records
AU-PH   32 records
Period 2025_1Q, 221 records written to .../data/processed/rpw_corridors.json
```

The sampled ids differ from run to run only if the source changes; the sample is seeded. A `MISMATCH` line or a `source verification failed` error means the output does not match the Excel; do not commit it.

Options:

| Option | Default | Use |
|---|---|---|
| `--period 2025_1Q` | newest quarter in the file | Parse a different quarter |
| `--sample 15` | 15 | How many random records to compare with the raw rows (the count check covers all rows) |
| `--source PATH` | `data/source/rpw_dataset_2011_2025_q1.xlsx` | Another workbook |
| `--output PATH` | `data/processed/rpw_corridors.json` | Another output file |

### 4. Check the script is idempotent

Run it twice and compare checksums. The output has no timestamp, so the two must be identical and `git diff` on the JSON stays empty:

**bash**
```bash
python -m src.loaders.world_bank > /dev/null 2>&1; md5 -q data/processed/rpw_corridors.json
python -m src.loaders.world_bank > /dev/null 2>&1; md5 -q data/processed/rpw_corridors.json
```

Use `md5sum` instead of `md5 -q` on Linux, and on PowerShell: `Get-FileHash data\processed\rpw_corridors.json`.

### 5. Look at the output

```bash
python - <<'EOF'
import json
d = json.load(open("data/processed/rpw_corridors.json"))
print(d["period"], [(c["corridor_id"], c["provider_count"]) for c in d["corridors"]])
EOF
```

Expected: `2025_1Q [('SG-PH', 39), ('SG-IN', 29), ('AU-IN', 35), ('MY-ID', 42), ('JP-PH', 44), ('AU-PH', 32)]`.

### 6. Manual sample validation (compare with the spreadsheet by eye)

The script already checks 15 records automatically. To check by hand as well, pick any `rpw_id` from the JSON, then in Excel open the sheet `Dataset (from Q2 2016)`, filter column `id` to that number and compare:

| JSON field | Excel column |
|---|---|
| `firm`, `firm_type` | `firm`, `firm_type` |
| `payment_instrument`, `access_point`, `pickup_method`, `speed` | `payment instrument`, `access point`, `pickup method`, `speed actual` |
| `quote_200.fee_lcu`, `.fx_rate`, `.fx_margin_pct`, `.total_cost_pct` | `cc1 lcu fee`, `cc1 lcu fx rate`, `cc1 fx margin`, `cc1 total cost %` |
| `quote_500.…` | the `cc2 …` columns |
| `interbank_rate` | `inter lcu bank fx` |
| `surveyed_on` | `date` |

`cc1` is the USD 200 quote and `cc2` is the USD 500 quote.

### 7. Run the checks

```bash
pytest
ruff check .
black --check .
mypy src tests
```

Expected: `18 passed`, `All checks passed!`, `16 files would be left unchanged.`, `Success: no issues found in 16 source files`.

`test_committed_output_file_is_valid_and_covers_all_corridors` reads the committed JSON, so it also fails if someone edits that file into an invalid shape or the corridor list in `config.py` and the JSON drift apart.

## Output schema

Top level (`RpwCorridorFile`):

| Field | Meaning |
|---|---|
| `source` | `name`, `url`, `attribution`, `file_name`, `sheet` |
| `period` | Survey quarter, for example `2025_1Q` |
| `corridors` | Exactly the 6 configured corridors, in the order SG-PH, SG-IN, AU-IN, MY-ID, JP-PH, AU-PH |

Each corridor (`CorridorDoc`), meant to become the Firestore document `corridors/{corridor_id}`:

| Field | Meaning |
|---|---|
| `corridor_id` | `SG-PH` style id |
| `source_country`, `destination_country` | ISO-2 |
| `source_currency`, `destination_currency` | ISO-4217 |
| `period` | Survey quarter of the records |
| `provider_count` | Length of `providers` (validated) |
| `providers` | List of provider records, sorted by firm name. Never empty. |

Each provider record (`ProviderRecord`) is one surveyed service:

| Field | Meaning |
|---|---|
| `rpw_id` | RPW's own id for the service. Unique; use it as a stable key. |
| `firm`, `firm_type` | Provider name and type (Money Transfer Operator, Bank, Mobile Operator, Post Office) |
| `payment_instrument` | How the sender pays: Cash, Bank account transfer, Debit card, Credit card, Mobile money |
| `access_point` | Where the sender starts: Internet, Agent, Bank branch, Call Center, Mobile phone, ATM Network, Post Office branch |
| `pickup_method` | How the receiver collects: Bank account, Cash, Mobile wallet, Own/partner Bank account |
| `speed` | For example `Same day`, `Less than one hour`, `2 days` |
| `network_coverage` | RPW's rating of the receiving network: High, Medium, Low (may be null) |
| `note` | RPW note, for example "Account required for detailed price info" (usually null) |
| `payout_currency` | Currency the receiver gets. `USD` for the six exceptions, otherwise the destination currency. |
| `interbank_rate` | Mid-market rate on the survey date (payout currency per 1 unit of sending currency) |
| `surveyed_on` | Date the price was collected |
| `quote_200`, `quote_500` | Price of sending USD 200 and USD 500 |

Each quote (`Quote`), all amounts in the **sender's** currency:

| Field | Meaning |
|---|---|
| `send_amount_lcu` | Amount sent that equals USD 200 or 500 |
| `fee_lcu` | Flat fee |
| `fx_rate` | Rate applied by the provider (payout currency per 1 unit of sending currency) |
| `fx_margin_pct` | How much worse the provider's rate is than the interbank rate (negative = better) |
| `total_cost_pct` | Fee plus rate margin as a percentage of the amount sent. The number to rank by. |

Rounding: percentages, fees and amounts are rounded to 6 decimals and rates to 10, only to remove float dust from the Excel (for example `1.8499999999999999` becomes `1.85`). No real precision is lost.

## Notes for the next tasks

**NF-P1-016 (load into Firestore, Aditya):**
- Read `data-scripts/data/processed/rpw_corridors.json` and write one document per entry in `corridors` to `corridors/{corridor_id}`. Every corridor has data.
- Store `source.attribution` and `period` with the data.
- The biggest document (JP-PH, 44 records) is well under Firestore's 1 MiB limit.
- The Firestore schema doc (NF-P1-013) is still empty; this JSON is the working contract until it exists. Agree any change to the field names with Pranjal before the loader is written.

**NF-P2-014 (comparison engine, Pranjal) and NF-P2-018 (corridor picker, Devam):**
- The picker offers the 6 corridors above. There is no corridor without data.
- Rank by `quote_200` or `quote_500` `total_cost_pct` according to the user's amount.
- Leave out (or mark) records where `payout_currency` differs from the corridor's `destination_currency` when showing "recipient receives".
- Show `surveyed_on`.

## Refreshing when the World Bank publishes a newer quarter

1. Download the new workbook (step 1). The file name will change.
2. Update `RPW_SOURCE_FILE` in `src/config.py`. If the sheet name changed, update `RPW_SHEET` too.
3. Run the parser (step 3). It picks the newest quarter automatically.
4. If it stops with `missing columns`, the World Bank changed the layout. Compare the new headers with `REQUIRED_COLUMNS` in `world_bank.py` before changing anything.
5. If a corridor has no rows in the newest quarter, the script stops with `no rows for period`. That is intended: decide whether to use the previous quarter (`--period`) or investigate.
6. The remittance form checks amounts in the browser (NF-P2-018). Run `pnpm exec vitest run src/utils/corridors.test.ts` from `frontend/`. If the surveyed amounts changed, it fails and names the corridor; update `surveyAmounts` in `frontend/src/utils/corridors.ts`.

## Adding or replacing a corridor later

1. Confirm RPW covers it: the code is the source and destination ISO-3 codes joined (`AUSIND`). Look for it in the `corridor` column of the sheet.
2. Edit the `CORRIDORS` table in `src/config.py` (id, RPW code, ISO-2 countries, currencies).
3. Update the tests that name corridors, re-run the parser and commit the new JSON.
4. Update every place that lists the corridors: `CLAUDE.md`, `README.md`, this runbook and the tracker.

## Verified results (2026-09-25)

| Check | Result |
|---|---|
| Workbook | `rpw_dataset_2011_2025_q1.xlsx`, 49 MB; main sheet 197,999 rows, 36 quarters |
| Corridors found | All 6, every one back to 2016 Q2 and up to 2025 Q1 |
| Records for 2025 Q1 | 221 (39 / 29 / 35 / 42 / 44 / 32); 108 distinct firm-per-corridor pairs |
| Missing values in key fields | none (only optional notes and pickup location) |
| Quote sizes | every row is USD 200 (`cc1`) and USD 500 (`cc2`), in the expected sending currency |
| Random sample against the raw sheet | 15 of 15 match, plus record counts per corridor match |
| Repeat run | identical output (same checksum) |
| Output size | 198 KB |
| USD-payout services | 6, all tagged |
| Negative-cost quotes | 5 (InstaReM AU→IN twice, MoneyGram AU→PH three times) |
| pytest / ruff / black / mypy | 18 passed; all clean |
| Cost at USD 200 (local payout), cheapest to dearest | SG-PH 0.73–20.0%, SG-IN 0.69–5.8%, AU-IN −0.24–20.33%, MY-ID 1.57–11.6%, JP-PH 2.25–6.89%, AU-PH 0.35–6.06% |

## Definition of Done

Data ingestion script:
- [x] Script is idempotent (safe to re-run; identical output)
- [x] Validates data before writing (Pydantic models plus the source cross-check)
- [x] Logs count of records processed per corridor; bad rows stop the run with the row id
- [x] Uses service account or admin SDK correctly: not applicable, nothing is written to Firestore
- [x] Documented in `data-scripts/README.md`

Task specific:
- [x] Excel downloaded (by hand, in a browser) and parsed with pandas + openpyxl
- [x] All 6 corridors parsed with sample validation
- [x] Corridor list updated everywhere (KR→NP replaced by AU→IN)
- [x] Output JSON committed for NF-P1-016
- [x] No secrets, no real keys, the large Excel stays out of git

Documentation:
- [x] Written in Markdown with consistent headings and code blocks
- [ ] Reviewed by at least one other teammate
- [ ] Committed to `/docs`

## Commit

Branch: `feature/data-worldbank-rpw-parse`

Three shared files changed (`requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, all in `data-scripts/`) and were agreed before the change. `CLAUDE.md` and `.claude/tasks.md` are gitignored local files: each teammate must make the same one-line corridor change in their own copy (see "Things the team must know", point 1).

```bash
git add README.md data-scripts/requirements.txt data-scripts/requirements-dev.txt data-scripts/pyproject.toml \
  data-scripts/src/config.py data-scripts/src/loaders/world_bank.py data-scripts/src/validators/corridor.py \
  data-scripts/tests/test_loaders.py data-scripts/data/processed/rpw_corridors.json \
  data-scripts/data/source/README.md data-scripts/README.md \
  docs/runbooks/NF-P1-015-worldbank-rpw-parse.md
git commit -m "feat(data): parse World Bank RPW data for six corridors" -m "Refs: NF-P1-015"
```

Before pushing, run `git status` and confirm the 49 MB `.xlsx` and `data-scripts/.venv/` are not listed (both are gitignored).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `FileNotFoundError: ... not found. Download steps: ...` | The Excel is missing or misnamed. Follow step 1 and keep the exact file name. |
| `403` or a Cloudflare page when downloading with `curl` or a script | The World Bank blocks scripts. Download in a normal browser. |
| `ModuleNotFoundError: No module named 'src'` | Run from `data-scripts/` and use `python -m src.loaders.world_bank`, not `python src/loaders/world_bank.py`. |
| `ModuleNotFoundError: pandas` (or openpyxl, pydantic) | The virtualenv is not active or `pip install -r requirements-dev.txt` was skipped. |
| `ValueError: RPW sheet ... is missing columns: [...]` | The World Bank changed the sheet layout. See "Refreshing" step 4. |
| `ValueError: RPW id N (SG-PH): ...` | One row failed validation (bad number, wrong currency, or not a USD 200/500 quote). The message names the row id; look it up in the Excel. |
| `ValueError: AU-IN: no rows for code AUSIND in RPW` | The RPW code in `config.py` is wrong, or the wrong sheet or file is being read. |
| `ValueError: SG-PH: no rows for period ...` | The corridor was not surveyed that quarter. Choose another `--period` or investigate. |
| `source verification failed` | Parsed values differ from the Excel. Do not commit. Rerun; if it persists, compare the listed ids with the Excel. |
| Parse seems to hang | Reading the 49 MB workbook takes about 20 to 30 seconds. Wait. |
| `git status` shows a modified JSON after a rerun | Only expected if the source file or the code changed. An unchanged source must give an identical file. |
| A file or teammate still mentions KR→NP | It is out of date; the corridor is AU→IN. Fix that file (or the local `CLAUDE.md` / `.claude/tasks.md`). |
| pandas install fails on Windows | Use Python 3.11 (`py -3.11`), then `pip install --upgrade pip` and retry. |

## Not covered here

- Loading into Firestore: NF-P1-016
- Firestore schema doc and security rules: NF-P1-013 / NF-P1-014
- Comparison engine and UI: NF-P2-014 and later
- Live FX rates and history: NF-P1-019, NF-P2-015
- Whether Nepali stays in the language list
