# NF-FC-004 — Cost-of-living baselines for South Korea and Malaysia

## Summary

What the Financial Coach (Future Scope, behind the `coach` flag) uses to budget a worker's first months, for two more hosts.

1. **Two curated files**, `KR.json` (South Korea, KRW) and `MY.json` (Malaysia, MYR), next to `SG.json` and `AU.json`. Each has the five recurring costs and the one-off costs of the first month, every one as low, typical and high, with the page it was read from, the day it was read (2026-10-09) and the curator (`AB`).
2. **The checker and the loader from NF-FC-003, unchanged.** Both files pass `python -m src.validators.cost_baselines`, and the loader writes `cost_baselines/KR` and `/MY` at version 1 and writes nothing on a re-run.
3. **A test file** for the two countries, and the documents that mention them.

No endpoint, no Gemini call, no screen. Nothing reads these documents until the plan generator (NF-FC-012).

**Not in this task:** JP and HK (NF-FC-005); how the plan uses the figures (NF-FC-006, -011, -012); changing the pay scale in `question_bank.json` (D-173, only checked); loading into production (D-183).

## The figures

Read on **2026-10-09**. As in NF-FC-003, a figure is a published price or range, **not a measured average of what workers spend**, and each `notes` line says how low, typical and high were read. The default worker is an **E-9 (EPS) worker in an employer dormitory** in KR and a **foreign worker in employer housing** in MY.

### South Korea (KRW)

| Line | Low | Typical | High | Where it comes from |
|---|---|---|---|---|
| accommodation | 172,550 | 301,963 | 431,376 | **A ceiling, not a price.** 8% to 20% of ordinary wage (MOEL's earlier guideline range) on the 2026 minimum monthly wage, 10,320 x 209 h = 2,156,880; typical is 14%. MOEL announced on 5 July 2023 that it was moving to market-based rents, so the current cap was not confirmed (D-189) |
| food | 200,000 | 250,000 | 300,000 | Study in Korea, student budget (June 2024); typical is the midpoint |
| transport | 50,000 | 75,000 | 100,000 | Study in Korea; check: 52 journeys at the 1,550 card base fare (Seoul, from 28 June 2025) is 80,600 |
| phone_data | 35,000 | 45,000 | 55,000 | KT Welcome prepaid for foreigners, 30 days: 1 GB, 3 GB, 5 GB |
| mandatory_deductions (% of wage) | 4.97 | 9.72 | 9.72 | Worker's share in 2026: pension 4.75, health 3.595, long-term care 0.4724, employment insurance 0.9. Low leaves out the pension (reciprocity, D-193) |
| setup: residence_card | 35,000 | 35,000 | 35,000 | Immigration Service: 35,000 from 1 January 2025 (30,000 before) |
| setup: transport_card | 2,500 | 3,000 | 5,000 | T-money card, gogohanguk (May 2026); Visit Seoul gives 3,000 |
| setup: return_cost_insurance | 400,000 | 500,000 | 600,000 | EPS page for E-9 workers, by country; the page also shows older rates, so check it (D-192) |

### Malaysia (MYR)

| Line | Low | Typical | High | Where it comes from |
|---|---|---|---|---|
| accommodation | 50 | 100 | 150 | What the worker pays. High is the legal maximum an employer may collect or deduct: RM150 from 1 March 2026 (P.U.(A) 49/2026), RM100 before. Low is a contractor's "nominal fee" of RM50 (2019). Typical is the old cap, an assumption (D-191) |
| food | 300 | 525 | 750 | UNITAR student budget: RM300 to 500 cooking, RM500 to 750 eating out; typical is the midpoint of 300 to 750 |
| transport | 100 | 125 | 150 | UNITAR estimate for passes; the My50 pass is for citizens only |
| phone_data | 30 | 40 | 55 | Hotlink prepaid 30-day plans (RM30, RM40, RM55) |
| mandatory_deductions (% of wage) | 3.25 | 3.25 | 3.5 | EPF 2% (mandatory for foreign workers from October 2025, not domestic helpers) + SOCSO 0.5% invalidity + 0.75% non-employment injury. High: the last rises to 1.00% in years 3 to 5 from 1 June 2026 |
| setup: foreign_worker_levy | 0 | 0 | 0 | Employer pays (Kathmandu Post, 1 January 2017); reversed once before in 2009, so confirm (D-194) |

**Pay-scale check (D-173).** At the typical figure, recurring costs are about 671,963 won in KR (27% of the question bank's 2,500,000; the 2026 minimum monthly wage is 2,156,880) and RM790 in MY (40% of 2,000; the minimum wage is RM1,700). The scale is the right size; no change was made.

## Files

| File | Change |
|---|---|
| `data-scripts/data/source/cost-baselines/KR.json`, `MY.json` | New: the curated figures |
| `data-scripts/tests/test_cost_baselines_kr_my.py` | New: committed files, the sums behind the housing and deduction figures, loader round trip (9 tests) |
| `data-scripts/README.md`, `docs/data-model/collections/cost_baselines.md` | One sentence each: the two files exist, and what the default worker is |
| `docs/deferred-items.md` | D-173, D-183 and D-185 updated; D-189 to D-194 added |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched. No checker, loader or backend/frontend file changed.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Source quality | Official pages where they opened; otherwise news, a university and operator pages, named in `publisher`. Search-result summaries were used only to find pages, never as a source |
| 2 | KR housing | The old guideline range as a ceiling (agreed before writing), not a measured deduction |
| 3 | Pages that would not open | JTKSM and KWSP (Malaysia) refused or were down on 2026-10-09; the EPF rule is from Bernama and the SOCSO rates from PERKESO, the rent cap from a property firm's article quoting the regulation |
| 4 | KR deductions | Pension 4.75% is counted in typical and high; a worker from a country without equal cover for Koreans is excluded, which the plan must ask (D-193) |
| 5 | MY SOCSO | Employment injury (1.25%) is the employer's and is not counted |
| 6 | Whole units | KRW and MYR amounts are whole numbers; percentages have up to 3 decimals |
| 7 | Curator initials | `AB` |
| 8 | Setup costs | MY has one (the levy at 0) because no other first-month price page could be read (D-191) |

## Run it

From `data-scripts/`, with the virtual environment active (`source .venv/Scripts/activate` in bash, `.venv\Scripts\Activate.ps1` in PowerShell).

**1. Check and test** (same in bash and PowerShell):

```bash
python -m src.validators.cost_baselines --only KR MY
python -m pytest tests/test_cost_baselines.py tests/test_cost_baselines_loader.py tests/test_cost_baselines_kr_my.py -q
```

Expect `OK   KR KRW: 5 categories, 3 setup cost(s)`, `OK   MY MYR: 5 categories, 1 setup cost(s)`, then `65 passed`.

**2. Dry run:**

```bash
python -m src.loaders.cost_baselines --only KR MY --dry-run
```

**3. Load into the Firestore emulator.** Terminal 1, from `frontend/`:

```bash
firebase emulators:start --only firestore --project demo-nomadfinance
```

Terminal 2, from `data-scripts/`. bash:

```bash
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance GOOGLE_CLOUD_PROJECT=demo-nomadfinance
python -m src.loaders.cost_baselines --only KR MY
python -m src.loaders.cost_baselines --only KR MY
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"; $env:GOOGLE_CLOUD_PROJECT = "demo-nomadfinance"
python -m src.loaders.cost_baselines --only KR MY
python -m src.loaders.cost_baselines --only KR MY
```

Expect `version 1, new` for both on the first run and `version 1, unchanged` on the second. Open <http://127.0.0.1:4000/firestore> to see `cost_baselines/KR` and `/MY`.

**4. Lint and types:**

```bash
python -m black --check . && python -m ruff check . && python -m mypy src tests
```

## Checks run (2026-10-09)

| Check | Result |
|---|---|
| Checker | `OK` for AU, KR, MY, SG |
| Cost-baseline tests | 65 passed (56 from NF-FC-003, 9 new) |
| `black --check .`, `ruff check .` | clean (71 files) |
| `mypy` | the new files and `src/validators`, `src/loaders` are clean. Two errors remain in `src/embedding.py` and `tests/test_embedding_resilience.py` (missing `google.genai` stubs), files this task does not touch |
| Whole data-scripts suite | 541 passed, 1 skipped, **3 failed**: all in `tests/test_embedding_resilience.py`, `ModuleNotFoundError: No module named 'google.genai'` in this virtual environment. Not related to this task |
| **Firestore emulator** | First load (KR and MY `new`, version 1); second load (`unchanged`); read back through the client (five categories, setup costs, deductions); a copy with KR `food.typical` changed loaded as KR version 2 `changed` and MY `unchanged`. The emulator was stopped afterwards |

**Not verified:** a load into `nomadfinance-prod` (D-183); the figures against a second reader (D-190); the backend and frontend suites (no file changed in either).

## Spot-check list (for the second reader)

Open the page, find the number, and say if it differs.

| # | Figure | Page |
|---|---|---|
| 1 | KR 8% to 20% of ordinary wage; move to market rents | MOEL press release, 5 July 2023 (`moel.go.kr` news 15223) |
| 2 | KR minimum wage 10,320; 209 hours | Korea.net, 15 July 2026 |
| 3 | KR food 200,000 to 300,000; transport 50,000 to 100,000 | Study in Korea, living expenses |
| 4 | KR prepaid 35,000 / 45,000 / 55,000 | KT Global Shop, LTE Welcome Prepaid |
| 5 | KR pension 4.75, health 7.19 split 50/50, long-term care 0.9448, employment 0.9 | 4insure calculator; NPS and NHIS rate pages |
| 6 | KR residence card 35,000 | Immigration Service notice, 14 December 2024 |
| 7 | MY rent cap RM150 from 1 March 2026 | Raine & Horne article (and the regulation P.U.(A) 49/2026, not read) |
| 8 | MY EPF 2% each, from October 2025 | Bernama, 25 June 2025 |
| 9 | MY SOCSO 0.5% + 0.75% worker; phases 0.75 / 1.00 / 1.25 | PERKESO, foreign workers |
| 10 | MY food 300 to 750, transport 100 to 150; Hotlink 30 / 40 / 55 | UNITAR; Hotlink prepaid page |

## Definition of Done

Tracker row: *cost_baselines/KR and /MY loaded with low / typical / high per category; sources column complete.*

- [x] KR and MY files with low, typical and high for all five categories, and the setup costs
- [x] Sources complete: every figure has a source, a day and the curator (the checker refuses a figure without)
- [x] Loaded into the Firestore **emulator** and read back. [ ] **Not loaded into production** (D-183)

Curated dataset:

- [x] Every figure carries source URL and retrieval date; curator initials recorded
- [x] Validated against schema; loader is idempotent (tested on the emulator)
- [ ] Second teammate spot-checked a sample (D-190)
- [x] No worker data: public price and rule pages only

Data ingestion script: [x] safe to re-run; [x] validates before writing; [x] logs each host; [x] documented in `data-scripts/README.md` (no script changed).

Documentation: [x] Markdown, [x] under `docs/`, [x] no attribution lines, [ ] teammate review.

## Noticed, not fixed

All are in `docs/deferred-items.md`: D-189 (current Korean housing rule), D-190 (spot-check), D-191 (Malaysian weak sources and missing first-month costs), D-192 (Korean weak sources), D-193 (pension, SOCSO phases and income tax), D-194 (Malaysian levy). Also, outside this task: `google.genai` is missing from the data-scripts virtual environment, so three embedding tests fail there.

## Commit

Branch: `feature/NF-FC-004-data-baselines-kr-my` (already created).

Commit message:

```
feat(coach): add KR and MY cost baselines
Refs: NF-FC-004
```
