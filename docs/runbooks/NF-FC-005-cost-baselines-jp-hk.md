# NF-FC-005 — Cost-of-living baselines for Japan and Hong Kong

## Summary

The last two of the six hosts for the Financial Coach (Future Scope, behind the `coach` flag): **Japan** (JPY) and **Hong Kong** (HKD). With `SG`, `AU` (NF-FC-003) and `KR`, `MY` (NF-FC-004), every host now has a baseline.

1. **Two curated files**, `JP.json` and `HK.json`. Each has the five recurring costs and the one-off costs of the first month, every one as low, typical and high, with the page it was read from, the day it was read (2026-10-09) and the curator (`AB`).
2. **The checker and the loader from NF-FC-003, unchanged.** All six files pass `python -m src.validators.cost_baselines`; the loader writes the two new documents at version 1 and writes nothing on a re-run.
3. **A test file** for the two countries, and the documents that mention them.

No endpoint, no Gemini call, no screen. Nothing reads these documents until the plan generator (NF-FC-012).

The tracker lists this task for Pranjal; Aditya did it.

**Not in this task:** how the plan uses the figures (NF-FC-006, -011, -012); changing the question bank's pay scale (D-173, only checked, now closed); loading into production (D-183).

## The figures

Read on **2026-10-09**. As before, a figure is a published price or range, **not a measured average of what workers spend**; each `notes` line says how low, typical and high were read. The default worker is a **technical intern in company housing** in JP and a **live-in foreign domestic helper** in HK (the tracker's wording for both).

### Japan (JPY)

| Line | Low | Typical | High | Where it comes from |
|---|---|---|---|---|
| accommodation | 20,000 | 30,000 | 57,000 | Rent deducted for company housing: a recruitment-help site says 20,000 to 30,000 is usual (shared by residents, never above actual cost, no legal cap). High is JASSO's Tokyo student rent average (2023). Utilities (5,000 to 10,000) are extra and not counted (D-187) |
| food | 20,000 | 27,700 | 45,000 | E-Housing (July 2025): budget cooking, average groceries, mixed cooking and eating out |
| transport | 0 | 6,000 | 12,000 | Low: employers often pay the commuter pass (Tokyo government FAQ). High: Japan Living Life's moderate Tokyo budget. Typical is the midpoint, an assumption |
| phone_data | 950 | 1,400 | 2,970 | IIJmio 5 GB and 10 GB (April 2025); ahamo 30 GB, no admin fee |
| mandatory_deductions (% of wage) | 14.49 | 14.69 | 15.04 | Worker's half, FY2026: pension 9.15, health half of 9.44 (Okinawa) / 9.85 (Tokyo) / 10.55 (Saga), support levy 0.115, employment insurance 0.5. Income and resident tax not checked (D-197) |
| setup: sim_card | 0 | 0 | 0 | ahamo: no admin fee, no shipping |
| setup: private_rental_move_in | 400,000 | 600,000 | 800,000 | Only for a worker who rents privately, not in company housing. Consumer guide, not official |

### Hong Kong (HKD)

| Line | Low | Typical | High | Where it comes from |
|---|---|---|---|---|
| accommodation | 0 | 0 | 0 | The employer must provide suitable accommodation free (Labour Department FAQ) |
| food | 0 | 1,236 | 1,236 | Free food, or a food allowance of at least 1,236 (unchanged from 30 September 2025). With the allowance the helper buys her own food |
| transport | 32 | 126 | 240 | **Assumed** 8 journeys a month times 4.0 (cheapest MTR fare), 15.7 (Citybus Hong Kong Island top) and 30.0 (Citybus Kowloon / New Territories top), Transport Department fact sheet, July 2025 |
| phone_data | 48 | 73 | 98 | csl local prepaid SIMs (48, 58, 78, 98); typical is the midpoint |
| mandatory_deductions (% of wage) | 0 | 0 | 0 | Domestic employees are exempt from MPF (MPFA). Salaries tax not checked |
| setup: transport_card | 50 | 200 | 200 | Octopus: 50 refundable deposit + 150 stored value |
| setup: agency_commission | 0 | 510 | 510 | The legal maximum: 10% of the first month's wage (5,100 minimum), payable only after that wage. What agencies charge was not read |

**Pay-scale check (D-173).** Typical recurring costs are 65,100 yen in JP (33% of the question bank's 200,000) and HK$1,435 in HK (29% of 5,000; the helpers' Minimum Allowable Wage is HK$5,100). The scale is the right size; no change was made, and D-173 is now closed for all six currencies.

## Files

| File | Change |
|---|---|
| `data-scripts/data/source/cost-baselines/JP.json`, `HK.json` | New: the curated figures |
| `data-scripts/tests/test_cost_baselines_jp_hk.py` | New: committed files, all six hosts, the sums behind the deduction, commission and transport figures, loader round trip (11 tests) |
| `data-scripts/README.md`, `docs/data-model/collections/cost_baselines.md` | The two files exist; the default worker of each |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched. No checker, loader, backend or frontend file changed.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Hong Kong default | The live-in helper (the tracker says "domestic workers"). No baseline for other Hong Kong workers (D-196) |
| 2 | Japan default | A technical intern in company housing. The care-worker group is not given its own override: no cost difference was found |
| 3 | Source quality | Official pages where they opened; otherwise consumer guides and operator pages, named in `publisher`. Search-result summaries were used only to find pages |
| 4 | Pages that would not open | Tokyo Metro, JR East, Toei, MTR fares and the MHLW intern guidance PDF refused or were unreadable on 2026-10-09 (D-195) |
| 5 | Japan deductions | Health uses the Japan Health Insurance Association rates for three prefectures as low, typical, high; a company health society can differ (D-197) |
| 6 | Hong Kong transport | Derived from published fares and an assumed 8 journeys, said in `notes` |
| 7 | Whole units | JPY and HKD amounts are whole numbers (27,700; 126 from 125.6); percentages have up to 3 decimals |
| 8 | Curator initials | `AB` |

## Run it

From `data-scripts/`, with the virtual environment active (`source .venv/Scripts/activate` in bash, `.venv\Scripts\Activate.ps1` in PowerShell).

**1. Check and test** (same in bash and PowerShell):

```bash
python -m src.validators.cost_baselines
python -m pytest tests/test_cost_baselines.py tests/test_cost_baselines_loader.py tests/test_cost_baselines_kr_my.py tests/test_cost_baselines_jp_hk.py -q
```

Expect six `OK` lines (AU, HK, JP, KR, MY, SG), then `76 passed`.

**2. Dry run:**

```bash
python -m src.loaders.cost_baselines --only JP HK --dry-run
```

**3. Load into the Firestore emulator.** Terminal 1, from `frontend/`:

```bash
firebase emulators:start --only firestore --project demo-nomadfinance
```

Terminal 2, from `data-scripts/`. bash:

```bash
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance GOOGLE_CLOUD_PROJECT=demo-nomadfinance
python -m src.loaders.cost_baselines
python -m src.loaders.cost_baselines
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"; $env:GOOGLE_CLOUD_PROJECT = "demo-nomadfinance"
python -m src.loaders.cost_baselines
python -m src.loaders.cost_baselines
```

Expect `version 1, new` for all six on the first run and `version 1, unchanged` on the second. Open <http://127.0.0.1:4000/firestore> to see `cost_baselines` with `AU`, `HK`, `JP`, `KR`, `MY`, `SG`.

**4. Lint and types:**

```bash
python -m black --check . && python -m ruff check . && python -m mypy src tests
```

## Checks run (2026-10-09)

| Check | Result |
|---|---|
| Checker | `OK` for all six hosts |
| Cost-baseline tests | 76 passed (65 from NF-FC-003 and -004, 11 new) |
| `black --check .`, `ruff check .` | clean (72 files) |
| `mypy` | the new file and `src/validators`, `src/loaders` are clean. The error in `src/embedding.py` (missing `google.genai` stubs) is in a file this task does not touch |
| Whole data-scripts suite | 552 passed, 1 skipped, **3 failed**: all in `tests/test_embedding_resilience.py`, `ModuleNotFoundError: No module named 'google.genai'` in this virtual environment. Same three as before this task |
| **Firestore emulator** | JP and HK `new`, then `unchanged`; then all six together: the four already loaded stayed as they were and the emulator held six documents. The emulator was stopped afterwards |

**Not verified:** a load into `nomadfinance-prod` (D-183); the figures against a second reader (D-198); the backend and frontend suites (no file changed in either).

## Spot-check list (for the second reader)

Open the page, find the number, and say if it differs.

| # | Figure | Page |
|---|---|---|
| 1 | JP rent deduction 20,000 to 30,000, no legal cap | gaikokusaiyo.com, 11 September 2025 |
| 2 | JP Tokyo rent average 57,000 | Study in Japan, accommodation |
| 3 | JP food 27,700 groceries; 45,000 mixed | E-Housing, 28 July 2025 |
| 4 | JP IIJmio 5 GB 950, 10 GB 1,400; ahamo 2,970 | IIJmio article 15 April 2025; ahamo plan page |
| 5 | JP pension 18.3% split; employment insurance worker 5/1,000 | Japan Pension Service; Tachikawa Hello Work |
| 6 | JP health 9.85 Tokyo, 9.44 Okinawa, 10.55 Saga; support levy 0.23 | Japan Health Insurance Association FY2026; Children and Families Agency |
| 7 | HK free accommodation and food or allowance 1,236; MAW 5,100 | Labour Department FAQ; press release 29 September 2025 |
| 8 | HK agency commission 10% of first month's wage | Labour Department FAQ, Q24 |
| 9 | HK MTR 4.0 to 66; Citybus 15.7 and 30.0 | Transport Department fact sheet, July 2025 |
| 10 | HK csl 48 / 58 / 78 / 98; Octopus 50 + 150; MPF exempt | csl prepaid page; Octopus; MPFA coverage |

## Definition of Done

Tracker row: *cost_baselines/JP and /HK loaded with low / typical / high per category; sources column complete.*

- [x] JP and HK files with low, typical and high for all five categories, and the setup costs
- [x] Sources complete: every figure has a source, a day and the curator (the checker refuses a figure without)
- [x] Loaded into the Firestore **emulator** and read back. [ ] **Not loaded into production** (D-183)

Curated dataset:

- [x] Every figure carries source URL and retrieval date; curator initials recorded
- [x] Validated against schema; loader is idempotent (tested on the emulator)
- [ ] Second teammate spot-checked a sample (D-198)
- [x] No worker data: public price and rule pages only

Data ingestion script: [x] safe to re-run; [x] validates before writing; [x] logs each host; [x] documented in `data-scripts/README.md` (no script changed).

Documentation: [x] Markdown, [x] under `docs/`, [x] no attribution lines, [ ] teammate review.

## Noticed, not fixed

Left for later: D-195 (Japanese weak sources and unread fares), D-196 (Hong Kong covers only the live-in helper), D-197 (Japanese deductions vary), D-198 (spot-check and tracker owner). Also outside this task: `google.genai` is missing from the data-scripts virtual environment, so three embedding tests fail there.

## Commit

Branch: `feature/NF-FC-005-data-baselines-jp-hk` (already created).

Commit message:

```
feat(coach): add JP and HK cost baselines
Refs: NF-FC-005
```
