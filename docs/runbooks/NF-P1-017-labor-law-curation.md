# NF-P1-017 — Labor-Law Curation (all six countries drafted; format shared)

## Summary

Contract Shield checks an uploaded contract against the labor law of the worker's host country. The law is curated by hand, one JSON file per country with 15 rules, then loaded into Firestore by NF-P1-018. The three of you split the six countries; this task is complete when all six files exist and pass the checker.

**Status on 2026-09-25**

| Person | Countries | Branch | Status |
|---|---|---|---|
| Pranjal | JP, HK | `feature/data-ilo-jp-hk` | Merged as a draft (PR 23), waiting for a second person's review |
| Devam | SG, AU | `feature/data-ilo-sg-au` | Merged as a draft (PR 24), waiting for Devam's own review (`reviewed_by` is empty) |
| Aditya | KR, MY | `feature/data-ilo-kr-my` | **Drafted** on Aditya's branch, waiting for Aditya's own review (`reviewed_by` is empty) |

This runbook covers three things: the shared format and checker that all three of you use, the guide for curators, and the results for all six countries with the limits to know about before relying on them.

**Korea stays a host country.** Only the KR→NP money corridor was replaced (by AU→IN). The KR file is the host-country curation, not the old corridor. The host countries, job types and categories in the code, the frontend and the docs were cross-checked and agree (see "Cross-checks").

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
| `data-scripts/data/source/labor-laws/JP.json`, `HK.json` | The curated files (were empty `{}` stubs), merged earlier |
| `data-scripts/data/source/labor-laws/SG.json`, `AU.json` | Devam's two countries, merged earlier |
| `data-scripts/data/source/labor-laws/KR.json`, `MY.json` | Aditya's two countries, drafted on `feature/data-ilo-kr-my` |
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
OK   AU.json: 15 rules, 22 variants, 41 references | coverage {...} | confidence {...}
OK   HK.json: 15 rules, 26 variants, 41 references | coverage {...} | confidence {...}
OK   JP.json: 15 rules, 20 variants, 31 references | coverage {...} | confidence {...}
OK   KR.json: 15 rules, 21 variants, 34 references | coverage {...} | confidence {...}
OK   MY.json: 15 rules, 19 variants, 23 references | coverage {...} | confidence {...}
OK   SG.json: 15 rules, 29 variants, 42 references | coverage {...} | confidence {...}
```

A country whose file is still `{}` shows `SKIP`. Add `--require-all` to make every stub count as a failure. That is the check for "task complete", and it passes with all six files.

### 3. Start a new country (only needed if a file is ever reset)

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

Expected with all six files: `46 passed` (no skips), `All checks passed!`, `... would be left unchanged.`, `Success: no issues found`. On a checkout where a country is still a stub, or without the frontend enums, some tests skip.

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

## Singapore (SG.json)

Drafted on 2026-09-25 (listed as `Pranjal (drafted for Devam)`; Devam should review and take over `curated_by`). Statutes were read on Singapore Statutes Online; guidance comes from the Ministry of Manpower (MOM). Worker groups: `all` (Employment Act employees, and Work Permit holders through Part III of the Fourth Schedule) and `domestic_worker`.

| # | Category | Coverage | Confidence | Worker groups |
|---|---|---|---|---|
| 1 | `minimum_wage` | partly_regulated | medium | all, domestic_worker |
| 2 | `working_hours` | partly_regulated | medium | all, domestic_worker |
| 3 | `overtime_pay` | partly_regulated | high | all, domestic_worker |
| 4 | `rest_days_and_holidays` | regulated | high | all, domestic_worker |
| 5 | `annual_leave` | partly_regulated | medium | all, domestic_worker |
| 6 | `sick_leave` | partly_regulated | medium | all, domestic_worker |
| 7 | `salary_payment` | regulated | high | all, domestic_worker |
| 8 | `salary_deductions` | partly_regulated | medium | all, domestic_worker |
| 9 | `termination_notice` | partly_regulated | medium | all, domestic_worker |
| 10 | `early_termination` | regulated | high | all, domestic_worker |
| 11 | `recruitment_fees` | regulated | high | all, domestic_worker |
| 12 | `passport_retention` | partly_regulated | medium | all, domestic_worker |
| 13 | `accommodation` | regulated | high | all, domestic_worker |
| 14 | `insurance_and_injury` | partly_regulated | high | all, domestic_worker |
| 15 | `social_security` | not_regulated | low | all |

Key facts to spot-check first:

| Point | Value | Where |
|---|---|---|
| Domestic workers are outside the Employment Act | Definition of "employee" excludes them; MOM confirms | Employment Act s. 2(1) |
| Hours and overtime | 8 h/day, 44 h/week, overtime at 1.5x, cap 72 h/month; only Part 4 employees | Employment Act ss. 35, 37, 38 |
| Salary deductions | 50% cap; one quarter for damage, accommodation and instalments; advances over at most 12 months | Employment Act ss. 27, 29 to 32 |
| No paying for the job | Fine up to S$30,000 or 2 years or both | Employment of Foreign Manpower Act s. 22A |
| Agency fee cap | One month's salary per year of contract or pass, at most 2 months; refund of at least 50% if the job ends within 6 months | Employment Agencies Rules 2011 rr. 12, 13 |
| Domestic worker rest day | One per 7 days; at least one rest day a month cannot be paid out | Work Passes Regulations, 4th Schedule Part I paras. 12 to 14 |
| Domestic worker insurance | Medical insurance; personal accident cover of at least S$60,000 | 4th Schedule Part II paras. 4, 4A |
| Passport | Rules name the work permit and visit pass only | 4th Schedule Part I para. 16; Part III para. 7 |

**Limits of the Singapore draft**

- **Verification found and fixed errors before this was saved.** A first pass had a wrong section for the deduction limits and a wrong description of rest-day pay; the whole file was re-checked against the statute text and rewritten. Devam's review should still pick at least 5 rules.
- **`social_security` is `not_regulated` with `low` confidence.** MOM says CPF applies to citizens and permanent residents; the CPF Act text read here does not itself exclude foreign workers, so any exclusion is probably in regulations that were not read. Confirm before showing it to a worker.
- **`passport_retention`:** the rules name the work permit and visit pass, not the passport. Other laws were not checked.
- **Domestic workers have no statutory annual leave, notice or list of permitted deductions** in the sources read; these are findings from those sources, so they are `medium`.
- **Criminal offence vs financial penalty.** Breaking a plain condition is an offence (s. 22(1)); breaking a regulatory condition (Part II for domestic workers) leads to a financial penalty of up to S$10,000 (s. 25(2)). The file states which applies.
- Not curated: Part IV of the Fourth Schedule, the Foreign Employee Dormitories Act 2015, the Employment Claims Act 2016, the Penal Code, PWM wage levels. S Pass and Employment Pass holders are not covered.

## Australia (AU.json)

Drafted on 2026-09-25 (listed as `Pranjal (drafted for Devam)`). The Fair Work Act 2009 (compilation of 7 July 2026) and the Criminal Code Act 1995 (compilation of 30 June 2026) were read on the Federal Register of Legislation; guidance comes from the Fair Work Ombudsman (FWO), the Australian Taxation Office (ATO), Home Affairs and Safe Work Australia. AustLII blocks automated access and was not used. Worker groups: `all` and `working_holiday` (visa subclass 417 or 462).

| # | Category | Coverage | Confidence | Worker groups |
|---|---|---|---|---|
| 1 | `minimum_wage` | regulated | high | all |
| 2 | `working_hours` | partly_regulated | high | all, working_holiday |
| 3 | `overtime_pay` | partly_regulated | medium | all |
| 4 | `rest_days_and_holidays` | partly_regulated | medium | all |
| 5 | `annual_leave` | partly_regulated | high | all, working_holiday |
| 6 | `sick_leave` | partly_regulated | high | all, working_holiday |
| 7 | `salary_payment` | regulated | high | all |
| 8 | `salary_deductions` | regulated | high | all, working_holiday |
| 9 | `termination_notice` | partly_regulated | high | all, working_holiday |
| 10 | `early_termination` | partly_regulated | medium | all |
| 11 | `recruitment_fees` | partly_regulated | medium | all |
| 12 | `passport_retention` | partly_regulated | medium | all |
| 13 | `accommodation` | partly_regulated | medium | all |
| 14 | `insurance_and_injury` | partly_regulated | medium | all, working_holiday |
| 15 | `social_security` | regulated | high | all, working_holiday |

Key facts to spot-check first:

| Point | Value | Where |
|---|---|---|
| National Minimum Wage | A$26.44/hour, A$1,004.90/week from 1 July 2026; casual A$33.05/hour (25% loading) | FWO Minimum wages; Award and agreement free page; Fair Work Act ss. 285, 293, 294 |
| Hours | 38 hours a week unless additional hours are reasonable | Fair Work Act s. 62 |
| Annual leave / personal leave | 4 weeks / 10 days a year; not for casuals; untaken annual leave paid out at the end | Fair Work Act ss. 87, 90, 96 |
| Pay | In full, in money, at least monthly; pay slip within one working day; deliberate underpayment is a crime (up to 10 years) | Fair Work Act ss. 323, 327A, 536 |
| Deductions | Only with written authorisation mainly for the employee's benefit, or law, award, agreement; unreasonable payments to the employer banned | Fair Work Act ss. 324 to 326 |
| Notice | 1 to 4 weeks (+1 if over 45 with 2 years); not for casual or fixed-term employees | Fair Work Act ss. 117, 123 |
| Working holiday | 6 months per employer (condition 8547) with exemptions since 1 January 2024 | Home Affairs 6 month work limitation page |
| Super | 12%, paid on each payday from 1 July 2026; DASP tax 65% for working holiday makers | Fair Work Act s. 116B; ATO pages |

**Limits of the Australia draft**

- **Modern awards were not curated.** Most real pay rates, overtime, breaks and rest periods come from awards (for example Hospitality or Horticulture). The file says so; the FWO Pay and Conditions Tool gives the award rate for a job.
- **Casual vs permanent matters.** Many working holiday makers are casual, so annual leave, paid sick leave and notice usually do not apply to them. Whether a worker is casual is decided by the real nature of the job (s. 15A), not the contract label.
- **Rates change every 1 July.** The minimum wage figures are those the FWO published for 1 July 2026. The ATO page showed only the 2025-26 working holiday maker tax rates when checked.
- **Exemptions to the 6-month rule apply "until the Government makes further decisions"** (Home Affairs). Subclass 417 conditions were read only through the shared condition 8547 page.
- **`insurance_and_injury` is `medium`.** Workers' compensation is state law and those statutes were not read; whether visa holders are covered in each state was not confirmed from an official source.
- **`passport_retention`:** no offence for holding a passport was found; deceiving someone about confiscating documents is an offence (Criminal Code ss. 270.7, 271.2). Other laws were not checked.
- India is a listed passport for the subclass 462 visa (through a ballot) on the Home Affairs page. Whether workers in the AU→IN and AU→PH corridors hold these visas was not researched.
- Not curated: penalty amounts in penalty units, the Migration Act text, state labour-hire licensing and tenancy laws.

## South Korea (KR.json)

Drafted on 2026-09-25 (listed as `Pranjal (drafted for Aditya)`; Aditya should review and take over `curated_by`). Every article was read in the **Korean original** on the National Law Information Center (law.go.kr) at the version in force; the English in the file is a paraphrase. The English translation of the Labor Standards Act on the Legislation Research Institute site is from 2012-13 and out of date, so it was not used. Worker groups: `all` and `manufacturing_worker` (foreign workers hired under the Employment Permit System, E-9 visa).

| # | Category | Coverage | Confidence | Worker groups |
|---|---|---|---|---|
| 1 | `minimum_wage` | regulated | high | all |
| 2 | `working_hours` | regulated | high | all |
| 3 | `overtime_pay` | regulated | high | all |
| 4 | `rest_days_and_holidays` | regulated | high | all |
| 5 | `annual_leave` | regulated | high | all |
| 6 | `sick_leave` | not_regulated | medium | all |
| 7 | `salary_payment` | regulated | high | all |
| 8 | `salary_deductions` | regulated | high | all |
| 9 | `termination_notice` | regulated | high | all, manufacturing_worker |
| 10 | `early_termination` | regulated | high | all, manufacturing_worker |
| 11 | `recruitment_fees` | regulated | high | all, manufacturing_worker |
| 12 | `passport_retention` | regulated | high | all |
| 13 | `accommodation` | regulated | medium | all, manufacturing_worker |
| 14 | `insurance_and_injury` | regulated | medium | all, manufacturing_worker |
| 15 | `social_security` | regulated | medium | all, manufacturing_worker |

Key facts to spot-check first:

| Point | Value | Where |
|---|---|---|
| Minimum wage | KRW 10,320/hour in 2026; KRW 10,700/hour from 1 January 2027 | Minimum Wage Act Arts. 6, 10; Korea.net (15 July 2026) |
| Hours | 40 h/week and 8 h/day; up to 12 extra hours a week by agreement (52 max) | Labor Standards Act (LSA) Arts. 50, 53 |
| Premium pay | Overtime, night (10 p.m. to 6 a.m.) and holiday work: at least +50%; holiday work over 8 h: +100% | LSA Art. 56 |
| Annual leave | 15 days at 80% attendance; +1 day per 2 years after 3 years, max 25 | LSA Art. 60 |
| Dismissal | Just cause; 30 days' notice or 30 days' pay; written reasons | LSA Arts. 23, 26, 27 |
| Wages | Full, in cash, monthly; final pay within 14 days; late interest up to 40% a year | LSA Arts. 36, 37, 43 |
| Passport | Taking a foreigner's passport or ID card as security is banned; up to 3 years or KRW 30 million | Immigration Control Act Arts. 33-3, 94(19) |
| Dormitory | Must meet LSA Art. 100 standards; information given before the contract | Foreign Workers Act Art. 22-2 |
| E-9 fees | Only the employer may be charged; no intervention by private parties | Foreign Workers Act Arts. 8(6), 27 |
| Departure insurance | Employer pays monthly; paid out within 14 days of departure | Foreign Workers Act Art. 13 |

**Limits of the Korea draft**

- **Enforcement Decrees and Rules were not read.** They set many numbers: dormitory floor area, the holidays list, which businesses need wage-arrears insurance, the small-business exceptions (fewer than 5 workers). The file says where each matters.
- **`sick_leave` is `not_regulated` with `medium` confidence.** No general paid sick leave was found in the Labor Standards Act as read. Work injuries are covered by insurance.
- **`accommodation`, `insurance_and_injury` and `social_security` are `medium`** because the decrees behind them were not read. Pension coverage also depends on the worker's home country giving Korean nationals equivalent coverage; that list was not checked.
- **Home-country costs** (agent fees, medical checks and training before departure) are outside these Korean rules and were not researched.
- **`passport_retention`:** the Act bans taking the passport "as security" for a contract or debt. Whether "safekeeping" with the worker's agreement is treated the same was not researched.
- The 2027 minimum wage was read from a government news portal (Korea.net), not the Ministry's notice.

## Malaysia (MY.json)

Drafted on 2026-09-25 (listed as `Pranjal (drafted for Aditya)`). Statutes were read from the official PDFs of the Attorney General's Chambers and the Department of Labour Peninsular Malaysia; social security from the PERKESO and EPF pages. The copies are marked "updated text" and are not authentic, so confirm against the Gazette. Worker groups: `all` and `plantation_worker`.

| # | Category | Coverage | Confidence | Worker groups |
|---|---|---|---|---|
| 1 | `minimum_wage` | regulated | high | all, plantation_worker |
| 2 | `working_hours` | regulated | high | all |
| 3 | `overtime_pay` | regulated | high | all |
| 4 | `rest_days_and_holidays` | regulated | high | all |
| 5 | `annual_leave` | regulated | high | all |
| 6 | `sick_leave` | regulated | high | all |
| 7 | `salary_payment` | regulated | high | all |
| 8 | `salary_deductions` | regulated | high | all, plantation_worker |
| 9 | `termination_notice` | regulated | high | all |
| 10 | `early_termination` | partly_regulated | medium | all |
| 11 | `recruitment_fees` | regulated | medium | all |
| 12 | `passport_retention` | regulated | medium | all |
| 13 | `accommodation` | regulated | medium | all, plantation_worker |
| 14 | `insurance_and_injury` | regulated | medium | all, plantation_worker |
| 15 | `social_security` | regulated | medium | all |

Key facts to spot-check first:

| Point | Value | Where |
|---|---|---|
| Minimum wage | RM1,700/month (RM8.72/hour); all employers since 1 August 2025; piece-rate and tonnage workers still RM1,700 | Minimum Wages Order 2024 (P.U. (A) 376) paras. 3, 5 |
| Hours | 8 h/day, 45 h/week (since 1 January 2023), break after 5 hours | Employment Act (EA) s. 60A |
| Overtime | 1.5x; rest-day work at higher rates; public-holiday work +2 days' wages and 3x overtime | EA ss. 60, 60A(3), 60D(3) |
| Leave | Annual 8/12/16 days; sick 14/18/22 days, 60 if hospitalised; 11 paid holidays | EA ss. 60D, 60E, 60F |
| Wages | Within 7 days of the wage period; into a bank account | EA ss. 19, 25 |
| Notice | 4/6/8 weeks if the contract is silent | EA s. 12 |
| Agency fee | Placement fee at most one month's basic wages for a non-citizen; not chargeable if the employer pays | Private Employment Agencies Act ss. 14, 14b |
| Passport | Holding another person's passport is an offence: RM10,000 or 5 years | Passports Act s. 12(1)(f) |
| Plantation housing | Free water and electricity; no rent for estate housing | Housing Act 1990 ss. 6, 13 |
| Social security | EPF 2% employer + 2% employee from October 2025; PERKESO injury and invalidity cover | KWSP and PERKESO pages |

**Limits of the Malaysia draft**

- **The Employment Act and the Housing Act apply to Peninsular Malaysia and Labuan only.** Sabah and Sarawak have their own Labour Ordinances, which were not curated. Much plantation work is done there, so treat MY.json as incomplete for those states. The Minimum Wages Order applies across Malaysia.
- **Regulations under the Employment Act were not read** (overtime hour limits, termination and lay-off benefits), nor the Employees' Social Security Act and Employees Provident Fund Act texts. Social security rules come from PERKESO and EPF pages, so `insurance_and_injury` and `social_security` are `medium`.
- **`recruitment_fees` is `medium`.** The agency fee cap covers licensed agencies in Malaysia. Fees charged in the worker's home country, and any government "employer pays" policy, were not confirmed.
- **`passport_retention` is `medium`.** The Passports Act reprint is dated 2006 and "lawful authority" is not defined in the text read.
- **`early_termination`** is the one `partly_regulated` rule: no provision on repatriation costs or levy refunds was found in the Act; those sit in immigration rules that were not read.
- No newer Minimum Wages Order or Employment Act amendment was found, but the official Gazette portal was not searched.

## Cross-checks done (2026-09-25)

| Check | Result |
|---|---|
| Host countries in `labor_law.py` vs the frontend `HOST_COUNTRIES` on `origin/main` | Same six: SG, KR, MY, JP, HK, AU |
| Job types in `labor_law.py` vs the frontend `JOB_TYPES` | Identical (a test checks it) |
| 15 category ids in `labor_law.py` vs the table in `labor_laws.md` | Identical (a test checks it) |
| KR→NP in any live corridor list | None. Korea remains a host country. |
| `JP.json` article citations | 39 checked against the law text by program: 0 problems |
| `HK.json` sections | Read in the e-Legislation viewer and in the government pages cited |
| `SG.json` sections | Employment Act, Employment of Foreign Manpower Act, Work Passes Regulations (Fourth Schedule), Employment Agencies Rules, Work Injury Compensation Act and CPF Act read on Singapore Statutes Online; MOM claims checked against the saved MOM pages |
| `AU.json` sections | Fair Work Act ss. 62, 87, 90, 96, 102, 114, 116, 116B, 117, 123, 285 to 294, 323 to 327A, 382 to 384, 536 and Criminal Code ss. 270.7, 271.1, 271.2 read on the Federal Register of Legislation; guidance pages read on fairwork.gov.au, ato.gov.au and immi.homeaffairs.gov.au |
| `KR.json` articles | Labor Standards Act, Minimum Wage Act, Act on Foreign Workers' Employment, Immigration Control Act, Employment Security Act, Industrial Accident Compensation Insurance Act, National Pension Act and National Health Insurance Act read in Korean on law.go.kr; 2027 minimum wage from Korea.net |
| `MY.json` sections | Employment Act (updated text as at 1 January 2023; the 1 August 2023 reprint shows the same last amendment), Minimum Wages Order 2024, wages council, private employment agencies, housing, passports and anti-trafficking Acts read from official PDFs; PERKESO and EPF pages read for social security |
| Checker vs all six files | OK. It also rejects a missing category, an unknown worker group, a TODO left in, and a file whose country does not match its name |

## Sources used

Japan: Labor Standards Act (japaneselawtranslation.go.jp law 3567), Minimum Wage Act (3937), Labor Contracts Act (3744), Act on Proper Technical Intern Training (3612), Employment Security Act (4013), Industrial Accident Compensation Insurance Act (3879), Employees' Pension Insurance Act (3554), Employment Insurance Act (3877), Health Insurance Act (3266), the MHLW minimum wage list for FY2025, and the MHLW guidelines for employers of foreign workers (notice 128 on the same site).

Hong Kong: Employment Ordinance (Cap. 57), Minimum Wage Ordinance (Cap. 608), Employees' Compensation Ordinance (Cap. 282) and Employment Agency Regulations (Cap. 57A) on elegislation.gov.hk; the Standard Employment Contract notes (immd.gov.hk); the Foreign Domestic Helpers FAQ (fdh.labour.gov.hk); the Employment Agencies Portal (eaa.labour.gov.hk); press releases of 1 May 2026, 29 September 2025 and 31 December 2021; the reply to LCQ5 of 8 May 2024; the MPF Authority coverage page.

Singapore: Employment Act 1968, Employment of Foreign Manpower Act 1990, Employment of Foreign Manpower (Work Passes) Regulations 2012, Employment Agencies Rules 2011, Work Injury Compensation Act 2019 and Central Provident Fund Act 1953 on sso.agc.gov.sg; MOM pages on the migrant domestic worker employer's guide, salary deductions, the Progressive Wage Model and CPF contributions.

Australia: Fair Work Act 2009 and Criminal Code Act 1995 on legislation.gov.au; Fair Work Ombudsman pages (minimum wages, award and agreement free wages and conditions, casual employees, visa holders and migrants, workers compensation, the Horticulture Showcase deductions page); ATO pages (super guarantee, DASP, working holiday maker tax rates); Home Affairs pages (subclass 462, 6 month work limitation, visa conditions); Safe Work Australia (migrant and multicultural workers).

South Korea: Labor Standards Act, Minimum Wage Act, Act on Foreign Workers' Employment, etc., Immigration Control Act, Employment Security Act, Industrial Accident Compensation Insurance Act, National Pension Act and National Health Insurance Act (Korean texts on law.go.kr); Korea.net for the 2027 minimum wage.

Malaysia: Employment Act 1955 (Act 265), Minimum Wages Order 2024 (P.U. (A) 376), National Wages Consultative Council Act 2011 (Act 732), Private Employment Agencies Act 1981 (Act 246), Employees' Minimum Standards of Housing, Accommodations and Amenities Act 1990 (Act 446), Passports Act 1966 (Act 150) and the Anti-Trafficking in Persons and Anti-Smuggling of Migrants Act 2007 (Act 670), as PDFs from lom.agc.gov.my, jtksm.mohr.gov.my and gajiminimum.mohr.gov.my; the PERKESO foreign-worker page and the EPF page on non-Malaysian citizen employees.

**How the Malaysian PDFs were read.** They were fetched into memory and their text extracted with `pdftotext` in a scratch folder outside the repository. The fetch tool also saved the PDF binaries in its own tool-results folder (outside the repo); nothing was added to the repository. Anyone repeating the check can download the same PDFs from the links in `references`.

**NATLEX** (natlex.ilo.org) sits behind a bot check and could not be opened by the curator, so every `natlex_isn` is empty. Someone with a browser should add the record numbers for JP, HK, SG, AU, KR and MY. **ILOSTAT and NORMLEX** also block scripts, so `ilostat_check` is `null` everywhere.

## Definition of Done

Data ingestion script (the checker is the script here; the loader is NF-P1-018):
- [x] Validates input before anything is written (`LaborLawFile`)
- [x] Logs counts of what it processed and lists every error
- [x] Safe to re-run (read-only; the template command refuses to overwrite curated work)
- [x] Service account or admin SDK: not applicable, nothing is written to Firestore
- [x] Documented in `data-scripts/README.md` and the folder guide

Documentation:
- [x] Markdown, consistent headings and code blocks, no AI attribution
- [ ] Reviewed by at least one other teammate (every file is still a draft with `reviewed_by` empty)
- [ ] Committed

Task complete for all six countries:
- [x] JP.json and HK.json curated and valid (merged)
- [x] SG.json and AU.json curated and valid (merged, waiting for Devam's review)
- [x] KR.json and MY.json curated and valid (this branch, waiting for Aditya's review)
- [ ] NATLEX record numbers added to all six files

## Commit

Branch: `feature/data-ilo-kr-my`. No shared files were changed. Only these files change on this branch:

```bash
git add data-scripts/data/source/labor-laws/KR.json data-scripts/data/source/labor-laws/MY.json \
  docs/runbooks/NF-P1-017-labor-law-curation.md
git commit -m "feat(data): curate South Korea and Malaysia labor laws" -m "Refs: NF-P1-017"
```

Before pushing, run `git status` and confirm nothing else is listed.

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

- Review and sign-off of each country by a second person
- The Firestore loader and the `_meta` version bump: NF-P1-018
- Retrieval and clause comparison: NF-P2-003, NF-P2-004
- Complaint templates and authority details: NF-P2-006
- Adding the NATLEX record numbers (needs a normal browser)
