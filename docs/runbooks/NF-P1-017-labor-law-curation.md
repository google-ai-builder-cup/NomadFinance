# NF-P1-017 — Labor-Law Curation (Japan and Hong Kong done, format shared)

## Summary

Contract Shield checks an uploaded contract against the labor law of the worker's host country. The law is curated by hand, one JSON file per country with 15 rules, then loaded into Firestore by NF-P1-018. The three of you split the six countries; this task is complete when all six files exist and pass the checker.

**Status on 2026-09-25**

| Person | Countries | Branch | Status |
|---|---|---|---|
| Pranjal | JP, HK | `feature/data-ilo-jp-hk` | **Done as a draft**, waiting for a second person's review |
| Devam | SG, AU | `feature/data-ilo-sg-au` | Not started (files are empty `{}` stubs) |
| Aditya | KR, MY | `feature/data-ilo-kr-my` | Not started (files are empty `{}` stubs) |

This runbook covers three things: the shared format and checker that all three of you use, the guide for curators, and the Japan and Hong Kong results with the limits to know about before relying on them.

**Korea stays a host country.** Only the KR→NP money corridor was replaced (by AU→IN). Aditya's KR curation stands. The host countries, job types and categories in the code, the frontend and the docs were cross-checked and agree (see "Cross-checks").

## What changed from the first plan

The schema doc written in NF-P1-013 gave each category one flat rule. Real law does not fit that: many laws exclude live-in domestic workers, technical interns have extra protections, and some categories have no rule at all. Two additions fix that. No data existed yet, so nothing needed migrating.

- **`coverage`** on every rule: `regulated`, `partly_regulated`, `not_regulated` or `unclear`. It tells "the law sets no rule" apart from "we did not look".
- **`variants`**: the rule per worker group (`all`, or job types such as `domestic_worker`). A job-type variant overrides the `all` variant for that worker.

Other new fields: `confidence` (`high`, `medium`, `low`), `penalty` and `enforced_by` per variant, structured `references` with an optional NATLEX record number, and `reviewed_by` on the file. The full field list is in `docs/data-model/collections/labor_laws.md`.

## Files

| File | Purpose |
|---|---|
| `data-scripts/src/validators/labor_law.py` | Pydantic models for the curated file (`LaborLawFile`), the checker (`python -m src.validators.labor_law`) and the template generator. NF-P1-018 reuses it. |
| `data-scripts/tests/test_labor_law.py` | 23 tests, including checks that the categories match the docs and the job types match the frontend |
| `data-scripts/src/config.py` | New constant `LABOR_LAWS_DIR` |
| `data-scripts/data/source/labor-laws/JP.json`, `HK.json` | The curated files (were empty `{}` stubs) |
| `data-scripts/data/source/labor-laws/README.md` | The curator guide for all three of you |
| `docs/data-model/collections/labor_laws.md`, `versioning.md` | Updated for `coverage` and `variants` |
| `data-scripts/README.md` | Short section pointing here |

Shared files: none changed (`requirements*.txt` and `pyproject.toml` already had everything needed).

## Flow

```
official law texts (Japan Law Translation, HK e-Legislation, ministry pages)
  + NATLEX record numbers (browser only)
    └─ curator writes data/source/labor-laws/<CC>.json
         └─ python -m src.validators.labor_law        (15 rules, no TODO, sources present)
              └─ second person reviews, adds reviewed_by
                   └─ NF-P1-018 loader → labor_laws/{country}/rules/{category} + _meta/current (version)
                        └─ NF-P2-003 retrieves by country → NF-P2-004 compares a contract
```

## All commands, in order

Run from `data-scripts/`. Step 1 is only needed once per machine.

### 1. Set up the environment

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

### 2. Check all six files

```bash
python -m src.validators.labor_law
```

Expected today:

```
SKIP AU.json: not curated yet
OK   HK.json: 15 rules, 26 variants, 41 references | coverage {...} | confidence {...}
OK   JP.json: 15 rules, 20 variants, 31 references | coverage {...} | confidence {...}
SKIP KR.json: not curated yet
SKIP MY.json: not curated yet
SKIP SG.json: not curated yet
```

Add `--require-all` to make the four stubs count as failures. That is the check for "task complete".

### 3. Start your own country (Devam and Aditya)

```bash
python -m src.validators.labor_law --template SG --output data/source/labor-laws/SG.json
```

The command refuses to overwrite a file that already has content unless you add `--force`. Then follow `data-scripts/data/source/labor-laws/README.md`, and run step 2 with your file's path after every few categories.

### 4. Run the tests and quality checks

```bash
pytest
ruff check .
black --check .
mypy src tests
```

Expected: `41 passed, 5 skipped` (four skips are countries not curated yet, one is a frontend cross-check that skips on an older checkout), `All checks passed!`, `... would be left unchanged.`, `Success: no issues found`.

### 5. Read a country as a reviewer

```bash
python - <<'EOF'
import json
d = json.load(open("data/source/labor-laws/JP.json", encoding="utf-8"))
for name, r in d["rules"].items():
    print(f"{name:24} {r['coverage']:17} {r['confidence']:7} {r['summary'][:90]}")
EOF
```

On PowerShell, save the same lines to a `.py` file and run it with `python`.

## How to review someone else's file

Pick at least 5 rules, including one with `low` or `medium` confidence and one number that changes every year. For each:

1. Open the `references[].url` and find the cited article.
2. Check every item in `requirements` and every `limits` value against the article. A wrong number is the main risk.
3. Check the `coverage` word fits what you read, and that a "not regulated" claim says in `notes` where it looked.
4. Check `applies_to` on each variant: does the law really exclude or include that worker group?
5. Add your name to `reviewed_by` and commit the file.

## Japan (JP.json)

Curated on 2026-09-25 by Pranjal from the Japanese Law Translation database (Ministry of Justice), the Ministry of Health, Labour and Welfare (MHLW) minimum wage table, and the MHLW guidelines for employers of foreign workers. Worker groups: `all` and `care_worker` (technical intern trainees). Where the `care_worker` column is empty, the `all` rule applies to care workers.

| # | Category | Coverage | Confidence | Worker groups |
|---|---|---|---|---|
| 1 | `minimum_wage` | regulated | high | all, care_worker |
| 2 | `working_hours` | regulated | high | all |
| 3 | `overtime_pay` | regulated | high | all |
| 4 | `rest_days_and_holidays` | partly_regulated | medium | all |
| 5 | `annual_leave` | regulated | high | all |
| 6 | `sick_leave` | partly_regulated | medium | all |
| 7 | `salary_payment` | regulated | high | all |
| 8 | `salary_deductions` | regulated | high | all, care_worker |
| 9 | `termination_notice` | regulated | high | all |
| 10 | `early_termination` | partly_regulated | medium | all, care_worker |
| 11 | `recruitment_fees` | regulated | medium | all, care_worker |
| 12 | `passport_retention` | partly_regulated | medium | all, care_worker |
| 13 | `accommodation` | partly_regulated | medium | all |
| 14 | `insurance_and_injury` | regulated | high | all |
| 15 | `social_security` | regulated | medium | all |

Key facts to spot-check first:

| Point | Value | Where |
|---|---|---|
| Minimum wage FY2025, national weighted average | 1,121 yen/hour (Tokyo 1,226; lowest 1,023) | MHLW national list (Reiwa 7) |
| Working hours | 8 h/day, 40 h/week; breaks 45 min over 6 h, 60 min over 8 h | Labor Standards Act (LSA) Arts. 32, 34 |
| Overtime | 25% premium floor; 50% beyond 60 h/month; caps 45 h/month and 360 h/year | LSA Arts. 36, 37 |
| Annual leave | 10 days after 6 months, up to 20 days at 6.5 years; employer must give 5 days | LSA Art. 39 |
| Dismissal notice | 30 days, or 30 days' average pay | LSA Art. 20 |
| Passport (technical interns) | Employer may not keep it; up to 6 months' prison or a 300,000 yen fine | Technical Intern Training Act Arts. 48, 111 |
| Pension premium | 18.3%, split equally | Employees' Pension Insurance Act Arts. 81, 82 |

**Limits of the Japan draft**

- The English texts are an unofficial translation. Only the Japanese text is legally binding, and a translation can lag behind amendments. The 39 article citations were checked by program against the translation text, which is not the same as checking the Japanese original.
- **Minimum wage is revised every year.** FY2025 figures are in force. FY2026 was recommended on 28 July 2026 at a national average of 1,176 yen (news reports say prefectures average about 1,177), taking effect by prefecture from about October 2026. Update the file when MHLW publishes the FY2026 table.
- Care workers on programs other than technical intern training (specified skilled worker, EPA) were not checked. The technical intern program itself is being replaced by a new employment-for-skill-development system, so check its status before relying on the intern-specific rules.
- **Sick leave:** "no paid sick leave" rests on finding no such provision in the translation (medium confidence).
- **Pension lump-sum cap** (60 months, with a reform to 96 months not yet in force) comes from secondary sources.

## Hong Kong (HK.json)

Curated on 2026-09-25 by Pranjal from the Hong Kong e-Legislation database, the Labour Department and Immigration Department guidance for foreign domestic helpers (the Standard Employment Contract ID 407), government press releases for the current rates, and the MPF Authority. Worker groups: `all` and `domestic_worker`.

| # | Category | Coverage | Confidence | Worker groups |
|---|---|---|---|---|
| 1 | `minimum_wage` | regulated | high | all, domestic_worker |
| 2 | `working_hours` | not_regulated | medium | all |
| 3 | `overtime_pay` | not_regulated | medium | all |
| 4 | `rest_days_and_holidays` | regulated | high | all, domestic_worker |
| 5 | `annual_leave` | regulated | high | all, domestic_worker |
| 6 | `sick_leave` | regulated | high | all |
| 7 | `salary_payment` | regulated | high | all, domestic_worker |
| 8 | `salary_deductions` | regulated | high | all, domestic_worker |
| 9 | `termination_notice` | regulated | high | all, domestic_worker |
| 10 | `early_termination` | regulated | high | all, domestic_worker |
| 11 | `recruitment_fees` | regulated | high | all, domestic_worker |
| 12 | `passport_retention` | unclear | low | all |
| 13 | `accommodation` | partly_regulated | medium | all, domestic_worker |
| 14 | `insurance_and_injury` | regulated | high | all, domestic_worker |
| 15 | `social_security` | partly_regulated | high | all, domestic_worker |

Key facts to spot-check first:

| Point | Value | Where |
|---|---|---|
| Statutory minimum wage | HK$43.1/hour from 1 May 2026 (live-in domestic workers excluded) | Minimum Wage Ordinance Sch. 3, s. 7(3) |
| Helper Minimum Allowable Wage | HK$5,100/month for contracts from 30 Sep 2025; food allowance at least HK$1,236 | Press release 29 Sep 2025 |
| Statutory holidays | 15 in 2026, 17 by 2030 | Employment Ordinance (EO) s. 39; press release |
| Annual leave | 7 days after 12 months, up to 14 days from year 9 | EO s. 41AA |
| Sickness allowance | 2 days/month in year 1, then 4; four-fifths pay; max 120 days | EO ss. 33, 35 |
| Wage payment | within 7 days after the wage period | EO ss. 22 to 25 |
| Agency commission | at most 10% of the first month's wages, after placement | Employment Agency Regulations, 2nd Schedule Part II |
| Helper notice | one month's written notice or pay; must leave within 2 weeks | Standard Employment Contract Clause 10; Immigration notes |

**Limits of the Hong Kong draft**

- **`passport_retention` is `unclear` with `low` confidence.** The Labour Department says nobody can compel a helper to hand over a passport, but the sources reviewed did not name a specific offence. A lawyer or the Labour Department should confirm before a contract is judged on this.
- **`working_hours` and `overtime_pay` are `not_regulated`** (medium confidence): the government states that hours and overtime pay are left to the contract. This is a claim about the sources reviewed.
- **The Minimum Allowable Wage is reviewed every September.** The latest announcement found is 29 September 2025. Check for a 2026 announcement.
- Some Immigration Department explanatory notes were last revised in 2019; the rates in them are superseded by the press releases cited in the file.

## Cross-checks done (2026-09-25)

| Check | Result |
|---|---|
| Host countries in `labor_law.py` vs the frontend `HOST_COUNTRIES` on `origin/main` | Same six: SG, KR, MY, JP, HK, AU |
| Job types in `labor_law.py` vs the frontend `JOB_TYPES` | Identical (a test checks it) |
| 15 category ids in `labor_law.py` vs the table in `labor_laws.md` | Identical (a test checks it) |
| KR→NP in any live corridor list | None. Korea remains a host country. |
| `JP.json` article citations | 39 checked against the law text by program: 0 problems |
| `HK.json` sections | Read in the e-Legislation viewer and in the government pages cited |
| Checker vs both files | OK. It also rejects a missing category, an unknown worker group, a TODO left in, and a file whose country does not match its name |

## Sources used

Japan: Labor Standards Act (japaneselawtranslation.go.jp law 3567), Minimum Wage Act (3937), Labor Contracts Act (3744), Act on Proper Technical Intern Training (3612), Employment Security Act (4013), Industrial Accident Compensation Insurance Act (3879), Employees' Pension Insurance Act (3554), Employment Insurance Act (3877), Health Insurance Act (3266), the MHLW minimum wage list for FY2025, and the MHLW guidelines for employers of foreign workers (notice 128 on the same site).

Hong Kong: Employment Ordinance (Cap. 57), Minimum Wage Ordinance (Cap. 608), Employees' Compensation Ordinance (Cap. 282) and Employment Agency Regulations (Cap. 57A) on elegislation.gov.hk; the Standard Employment Contract notes (immd.gov.hk); the Foreign Domestic Helpers FAQ (fdh.labour.gov.hk); the Employment Agencies Portal (eaa.labour.gov.hk); press releases of 1 May 2026, 29 September 2025 and 31 December 2021; the reply to LCQ5 of 8 May 2024; the MPF Authority coverage page.

**NATLEX** (natlex.ilo.org) sits behind a bot check and could not be opened by the curator, so every `natlex_isn` is empty. Someone with a browser should add the record numbers for JP and HK. **ILOSTAT and NORMLEX** also block scripts, so `ilostat_check` is `null` everywhere.

## Definition of Done

Data ingestion script (the checker is the script here; the loader is NF-P1-018):
- [x] Validates input before anything is written (`LaborLawFile`)
- [x] Logs counts of what it processed and lists every error
- [x] Safe to re-run (read-only; the template command refuses to overwrite curated work)
- [x] Service account or admin SDK: not applicable, nothing is written to Firestore
- [x] Documented in `data-scripts/README.md` and the folder guide

Documentation:
- [x] Markdown, consistent headings and code blocks, no AI attribution
- [ ] Reviewed by at least one other teammate (the JP and HK files especially)
- [ ] Committed

Task complete for all six countries:
- [x] JP.json and HK.json curated and valid
- [ ] SG.json and AU.json (Devam)
- [ ] KR.json and MY.json (Aditya)
- [ ] NATLEX record numbers added to JP.json and HK.json

## Commit

Branch: `feature/data-ilo-jp-hk`. No shared files were changed.

```bash
git add data-scripts/src/config.py data-scripts/src/validators/labor_law.py data-scripts/tests/test_labor_law.py \
  data-scripts/data/source/labor-laws/JP.json data-scripts/data/source/labor-laws/HK.json \
  data-scripts/data/source/labor-laws/README.md data-scripts/README.md \
  docs/data-model/collections/labor_laws.md docs/data-model/versioning.md \
  docs/runbooks/NF-P1-017-labor-law-curation.md
git commit -m "feat(data): curate Japan and Hong Kong labor laws with a shared checker" -m "Refs: NF-P1-017"
```

Devam and Aditya use their own branches and commit only their own country files. Before pushing, run `git status` and confirm nothing else is listed.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `FAIL ...: need exactly the 15 categories; missing [...]` | A category key is absent or misspelled; compare with the 15 ids in the guide |
| `still a TODO placeholder` | A template value was left; search the file for `TODO` |
| `unknown worker group` | `applies_to` needs `all` or one of the seven job types |
| `worker group in more than one variant` | A job type appears in two variants of one rule; merge them |
| `coverage 'unclear' needs confidence 'low'` | Set `confidence` to `low`, or find the answer and change the coverage |
| `Input should be a valid date` | Dates are `YYYY-MM-DD` |
| `Extra inputs are not permitted` | A field name is misspelled or not part of the format |
| `JSONDecodeError` | A trailing comma or missing quote. A byte-order mark is tolerated. |
| `REFUSED ...: already has content` | The template command protects curated files; add `--force` only if you mean to replace the file |
| A law site returns 403 or a "Just a moment" page | Bot check. Open it in a normal browser and read the text there. |
| `test_committed_country_files_are_valid_or_still_stubs` fails after you commit | Run the checker on your file; the test runs the same validation |

## Not covered here

- SG, AU, KR and MY content (Devam and Aditya)
- The Firestore loader and the `_meta` version bump: NF-P1-018
- Retrieval and clause comparison: NF-P2-003, NF-P2-004
- Complaint templates and authority details: NF-P2-006
- Adding the NATLEX record numbers (needs a normal browser)
