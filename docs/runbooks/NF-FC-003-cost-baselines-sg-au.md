# NF-FC-003 — Cost-of-living baselines for Singapore and Australia

## Summary

What the Financial Coach (Future Scope, behind the `coach` flag) uses to budget a worker's first months: the monthly cost of living in the host country.

1. **Two curated files**, `SG.json` (Singapore, SGD) and `AU.json` (Australia, AUD). Each has the five recurring costs (accommodation, food, transport, phone and data, mandatory deductions) and the one-off costs of the first month, every one as low, typical and high, with the page it was read from, the day it was read and the curator.
2. **A checker** (`python -m src.validators.cost_baselines`) that refuses a file with a figure out of order, a wrong currency, a missing source and 21 other slips. NF-FC-004 (KR, MY) and NF-FC-005 (JP, HK) use the same one.
3. **A loader** (`python -m src.loaders.cost_baselines`) that writes `cost_baselines/{host}`, raises `version` only when the content changes, and writes nothing on a re-run.

No endpoint, no Gemini call, no screen. The plan generator (NF-FC-012) reads these documents later.

**The second country is Australia.** The tracker row for this task still names a different one. The team's scope is the six hosts SG, KR, MY, JP, HK and AU, so this task curates `SG` and `AU` (D-102). The tracker row and the branch name in it are still to be corrected in the workbook.

**Not in this task:** KR, MY, JP and HK baselines (NF-FC-004, -005); how the plan uses the figures (NF-FC-006, -011, -012); changing the pay scale in `question_bank.json` (D-173, only checked here); Firestore rules (`cost_baselines` is already readable by signed-in users, and the rules tests already list `SG` and `AU`).

## The figures

All amounts are in the country's currency, per month unless the unit says otherwise. Read on **2026-10-08**. A figure is a published price or range, **not a measured average of what workers spend**; the `notes` of each figure say how low, typical and high were read.

### Singapore (SGD): default worker is a Work Permit holder in a dormitory

| Line | Low | Typical | High | Where it comes from |
|---|---|---|---|---|
| accommodation | 420 | 450 | 450 | MOM medians for a dormitory bed: Q1 2023 (420) and 2023 (about 450). No newer figure could be read (D-182). A **live-in domestic worker: 0** (MOM puts housing on the employer). The worker pays what the employer deducts, at most 25% of salary |
| food | 130 | 165 | 200 | Catered meals in a dormitory, TWC2 article of 7 May 2023 (130 to 200); typical is the midpoint. Domestic worker: 0 (MOM puts meals on the employer) |
| transport | 67 | 100 | 134 | PTC adult card fares (1.28 to 2.57 a journey) times 52 journeys (2 a day for 26 days, an assumption); typical is the midpoint. The monthly pass is for citizens and PRs only, so it is not used |
| phone_data | 10 | 12 | 20 | SIMBA 30-day prepaid plans (10 cheapest, 12 "Most Popular", 20 with 800 call minutes); Singtel hi! plans start at 15 |
| mandatory_deductions | 0 | 0 | 0 | % of wage. No CPF for foreign workers (MOM). Housing, food and transport deductions need written consent and sit in their own lines. Income tax not checked |
| setup: transport_card | 10 | 10 | 10 | SimplyGo EZ-Link adult card: 5 card cost plus 5 stored value |
| setup: sim_card | 0 | 0 | 0 | Singtel hi!: collecting the SIM is free; the first plan is in phone_data |

### Australia (AUD): default worker is a working-holiday maker

| Line | Low | Typical | High | Where it comes from |
|---|---|---|---|---|
| accommodation | 1,192 | 1,257 | 2,383 | A share-house room, weekly times 52/12: Monash 275 (Melbourne), PropTrack national median 290 (December 2023), UTS 550 (near UTS, Sydney). Bills and internet may be extra (D-187) |
| food | 400 | 600 | 800 | Sydney food and groceries, UTS (based on the Study Australia calculator); typical is the midpoint |
| transport | 108 | 163 | 217 | Monash public transport 25 to 50 a week times 52/12; typical is the midpoint. Sydney's Opal adult cap is 50 a week, the same top end |
| phone_data | 30 | 42 | 80 | Boost 28-day plans 28, 39 and 74, times 13/12; typical is the 39 plan |
| mandatory_deductions | 15 | 15 | 30 | % of wage. ATO Schedule 15 from 1 July 2026: 15% up to 45,000 a year, 30% above, so the share never passes 30% |
| setup: rental_bond | 1,100 | 1,160 | 2,200 | Four weeks' rent, the most a NSW landlord may take, on the weekly rents above (275, 290, 550) |
| setup: sim_card | 0 | 0 | 0 | A Boost SIM includes the first recharge, counted in phone_data |

The page for each figure is in the file (`source`, and `other_sources` where a range needed a second page).

**Pay-scale check (D-173).** Recurring costs (accommodation, food, transport, phone) come to about 727 for a dormitory worker in SG and 2,062 in AU, which is 48% of the question bank's SGD 1,500 and 46% of its AUD 4,500. The baselines are costs and the scale is pay, so one cannot replace the other; the check only shows the scale is the right size. No change was made. The AUD 4,500 is also close to a full-time month at the minimum wage in the AU labor-law file (about 4,355). The SGD 1,500 has no pay source.

## Files

| File | Change |
|---|---|
| `data-scripts/data/source/cost-baselines/SG.json`, `AU.json` | New: the curated figures |
| `data-scripts/src/validators/cost_baselines.py` | New: the schema and the CLI check |
| `data-scripts/src/loaders/cost_baselines.py` | New: the loader |
| `data-scripts/src/config.py` | One line: `COST_BASELINES_DIR` |
| `data-scripts/tests/test_cost_baselines.py` | New: the committed data, 24 refused slips, the CLI (39 tests) |
| `data-scripts/tests/test_cost_baselines_loader.py` | New: first load, re-run, changed figure, source-only change, hash, collections (17 tests) |
| `data-scripts/README.md` | New section "Cost baselines" |
| `docs/data-model/collections/cost_baselines.md` | Real example, `other_sources`, what the checker refuses, how a figure is read, the hash rule |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched. No backend or frontend file changed.

## How it works

- **One file per host**, named for it (`SG.json`). The checker refuses a file whose name is not the country inside, a country outside the six, and a currency that is not that country's.
- **Exactly five recurring categories**, because the plan's budget lines are built from them. Units are `month`, except `mandatory_deductions` which is `pct_of_wage` (or `month`); setup costs are `one_off`.
- **A figure of 0 needs a note** that says why (an employer who pays is a finding, not a gap). `mandatory_deductions` always needs one.
- **`by_job_type`** replaces the three numbers for one worker group (`domestic_worker` in SG pays 0 for housing and food).
- **The loader** validates every selected file, then writes all hosts in one batch. A new host is version 1. A changed figure, unit, override or note raises that host's version by 1. A changed source or curator on the same figures is stored with the same version (`refreshed`). Nothing changed writes nothing (`unchanged`). A host with no file is left alone and nothing is deleted, so KR, MY, JP and HK can be loaded before or after this task.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Second country | AU, not the tracker's name for it (decision of 2026-10-06, D-102) |
| 2 | Where the files live | `data-scripts/data/source/cost-baselines/`, like the labor laws: they are loaded into Firestore and read by the Coach. Not beside the code, as NF-FC-001's question bank is |
| 3 | `other_sources` | New optional list on a figure. A range often needs two pages (the low from one, the high from another); the collection doc lets curators refine fields. KR, MY, JP and HK may use it |
| 4 | What the hash leaves out | `source`, `other_sources` and `curator`, as the scam taxonomy does. Re-checking a page that says the same must not raise the version a plan records |
| 5 | Only pages that were read | Every figure comes from a page opened on 2026-10-08. Search-result summaries were used to find pages, never as a source. Pages behind a bot check (EdgeProp) were not opened by other means, and the numbers a search summary gave for them were left out (D-182) |
| 6 | Default worker group | SG: a dormitory Work Permit holder, with a domestic-worker override. AU: a working-holiday maker, with no override (resident tax and rent differences are in D-188) |
| 7 | Dormitory bed price against what the worker pays | `accommodation` is the bed price. The worker pays only the deduction (at most 25% of salary), which the plan must handle (D-186) |
| 8 | SG transport | Derived from fares, because the monthly pass is closed to non-residents. The 52 journeys a month is an assumption, said in `notes` |
| 9 | Rounding | Whole currency units. A weekly figure is times 52/12, a 28-day price times 13/12, and a midpoint of 162.5 is written 163 |
| 10 | `--only` | Validates just the hosts named, so one country's unfinished file does not block another's load |
| 11 | Curator initials | `DD`, from the repo's commit history (Devam Dixit). Say if you want different initials |
| 12 | Line name | The baseline calls it `mandatory_deductions`; the plan's budget line is `deductions` (`docs/api/v2-coach.md`). NF-FC-012 maps one to the other |

## Run it

From `data-scripts/`, with the virtual environment active (`source .venv/Scripts/activate` in bash, `.venv\Scripts\Activate.ps1` in PowerShell; Python 3.11).

**1. Check the files and run the tests** (bash and PowerShell are the same):

```bash
python -m src.validators.cost_baselines
python -m pytest tests/test_cost_baselines.py tests/test_cost_baselines_loader.py -q
```

Expect `OK   AU AUD: 5 categories, 2 setup cost(s)`, `OK   SG SGD: ...`, then `56 passed`.

**2. Dry run** (no Firestore access):

```bash
python -m src.loaders.cost_baselines --dry-run
```

**3. Load into the Firestore emulator.** Terminal 1, from `frontend/` (the emulator port is 8085 in `frontend/firebase.json`):

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

Expect `version 1, new` for both on the first run and `version 1, unchanged` on the second. You can also open <http://127.0.0.1:4000/firestore> and look at `cost_baselines/SG` and `/AU`.

**4. See a change raise the version.** Edit a figure in a copy of the folder (not the committed files) and load the copy:

```bash
cp -r data/source/cost-baselines /tmp/cb   # PowerShell: Copy-Item -Recurse data\source\cost-baselines $env:TEMP\cb
# change categories.food.typical in /tmp/cb/SG.json, then:
python -m src.loaders.cost_baselines --input-dir /tmp/cb   # PowerShell: --input-dir $env:TEMP\cb
```

Expect `SG ... version 2, changed` and `AU ... unchanged`. Change only a `publisher` and expect `refreshed` with the same version. Make `low` bigger than `typical` and expect `Nothing was written`.

**5. Lint and types:**

```bash
python -m black --check . && python -m ruff check . && python -m mypy src tests
```

## Checks run (2026-10-08)

| Check | Result |
|---|---|
| `black --check .`, `ruff check .` | clean (70 files) |
| `mypy src tests` | clean (68 files) |
| Data-scripts tests | 535 passed, 1 skipped (the skipped one needs the backend's packages and was skipped before); 56 are new |
| The checker works | 24 edits of `SG.json` (low above typical, a wrong currency, a missing category, a zero without a note, an `http` source, a future date and so on) each refused. Printing the message for each showed two were refused for the wrong reason (the 100% limit, the zero rule); both were rewritten to hit only their own rule |
| The tests notice a broken loader | Hashing the sources failed 2 tests; always committing failed 1; both restored |
| **Firestore emulator** | Dry run; first load (both `new`, version 1); second load (both `unchanged`, `updated_at` identical); a changed figure (SG to version 2, AU unchanged); a changed publisher (AU `refreshed`, same version); a broken file (nothing written). Read back through the client: all five categories and the setup costs, `by_job_type` and the source intact |
| Search for the old second country's name and code | none in any file this task adds or changes (apart from the old tracker text the log already quotes) |

**Not verified:**

- **A load into `nomadfinance-prod`** (D-183): it needs credentials and billing (D-17).
- **The figures against a second reader** (D-184).
- **Coverage**: `pytest-cov` is not in the data-scripts requirements, and adding it is a shared-file change.
- **commitlint and pre-commit**: not installed here. The header below is 52 characters, counted by hand.
- **Backend and frontend suites**: no file in either changed.

## Spot-check list (for the second reader)

Open the page, find the number, and say if it differs. Each is a figure in the files above.

| # | File and line | Page |
|---|---|---|
| 1 | SG accommodation typical 450 | MOM reply of 5 Feb 2024: "about $450 per bed" for 2023 |
| 2 | SG accommodation low 420 | MOM reply of 2 Aug 2023: median 420 for Q1 2023 |
| 3 | SG food 130 to 200 | TWC2, 7 May 2023 |
| 4 | SG transport 1.28 and 2.57 | PTC fares page; and SimplyGo (the monthly card is for citizens and PRs) |
| 5 | SG phone 10, 12, 20 | `simba.sg/plans` |
| 6 | SG deductions: no CPF; 25% and 50% limits | MOM "paying the salary" and "salary deductions" |
| 7 | AU accommodation 275, 290, 550 a week | Monash, PropTrack, UTS |
| 8 | AU food 400 to 800 | UTS |
| 9 | AU phone 28, 39, 74 a 28 days | Boost prepaid plans |
| 10 | AU tax 15% to 45,000, 30% above; bond 4 weeks | ATO Schedule 15; NSW "costs at the start of a tenancy" |

## Definition of Done

Tracker row: *cost_baselines/SG and /AU loaded with low / typical / high per category in local currency; sources column complete.*

- [x] SG and AU files with low, typical and high for all five categories in SGD and AUD, and the setup costs
- [x] Sources complete: every figure has a source, a day and the curator (the checker refuses a figure without)
- [x] Loaded into the Firestore **emulator** and read back. [ ] **Not loaded into production** (D-183)

Curated dataset:

- [x] Every figure carries source URL and retrieval date; curator initials recorded
- [x] Validated against schema; loader is idempotent (tested on the emulator)
- [ ] Second teammate spot-checked a sample (D-184)
- [x] No worker data: public price and rule pages only

Data ingestion script:

- [x] Safe to re-run; [x] validates before writing; [x] logs each host and the problems; [x] Admin SDK through `firestore_client` (emulator run); [x] documented in `data-scripts/README.md`

Documentation: [x] Markdown, [x] under `docs/`, [x] no attribution lines, [ ] teammate review.

## Noticed, not fixed

Left for later: D-182 (newer dormitory rent), D-183 (load into production), D-184 (spot-check), D-185 (KR, MY, JP, HK use the same checker), D-186 (read `by_job_type` and the worker's share), D-187 (no `utilities` line), D-188 (limits of the figures). D-102 and D-173 have a new note.

## Commit

Branch: `feature/NF-FC-003-data-baselines-sg-au`. The tracker's branch name ends in the old second country's code, so it is not used. The repo was on `main` when this was written, so create the branch first.

```bash
git switch -c feature/NF-FC-003-data-baselines-sg-au
git add data-scripts/README.md data-scripts/src/config.py data-scripts/src/loaders/cost_baselines.py data-scripts/src/validators/cost_baselines.py data-scripts/tests/test_cost_baselines.py data-scripts/tests/test_cost_baselines_loader.py data-scripts/data/source/cost-baselines docs/data-model/collections/cost_baselines.md docs/runbooks/NF-FC-003-cost-baselines-sg-au.md
git commit -m "feat(coach): add SG and AU cost baselines and loader" -m "Refs: NF-FC-003"
```

PR title: `feat(coach): cost baselines for Singapore and Australia (NF-FC-003)`

PR description:

> **What.** Monthly cost-of-living baselines for Singapore (SGD) and Australia (AUD) for the Financial Coach: five recurring costs and the first month's one-off costs, each low, typical and high, each with the page it was read from, the day it was read and the curator. Adds the checker and the loader that NF-FC-004 and NF-FC-005 reuse for KR, MY, JP and HK.
>
> **Why.** The 90-day plan (NF-FC-012) may only use the worker's answers, these baselines and live exchange rates, so the baselines need a source for every number. The tracker names a different second country; the project scope is the six hosts SG, KR, MY, JP, HK and AU, so this covers `SG` and `AU`.
>
> **How to check.** `python -m src.validators.cost_baselines`, then `pytest tests/test_cost_baselines.py tests/test_cost_baselines_loader.py`. To see the loader: start the Firestore emulator and run `python -m src.loaders.cost_baselines` twice (second run changes nothing). Steps are in `docs/runbooks/NF-FC-003-cost-baselines-sg-au.md`.
>
> **Limits.** The figures are published prices and ranges, not what workers measurably spend. The newest dormitory rent that could be read is MOM's 2023 median (D-182). Australian ranges rest partly on university student-budget pages (D-188). There is no `utilities` line yet (D-187). Not yet loaded into `nomadfinance-prod` (D-183), and not yet spot-checked by a second reader (D-184).
>
> **Rollback.** Nothing reads `cost_baselines` yet. Delete the two documents, or revert the PR; no route, rule or index changed, and the `coach` flag is not involved.
