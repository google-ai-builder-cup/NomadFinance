# Labor-law curation guide (NF-P1-017)

One JSON file per host country, 15 rules each. Contract Shield compares an uploaded contract against these rules, so a wrong number here becomes wrong advice to a worker. Accuracy matters more than speed.

## Who curates what

| Person | Countries | Branch | Worker groups that must be covered |
|---|---|---|---|
| Devam | `SG.json`, `AU.json` | `feature/data-ilo-sg-au` | SG domestic worker; AU working holiday |
| Aditya | `KR.json`, `MY.json` | `feature/data-ilo-kr-my` | KR manufacturing worker; MY plantation worker |
| Pranjal | `JP.json`, `HK.json` | `feature/data-ilo-jp-hk` | JP care worker; HK domestic worker |

`JP.json` and `HK.json` are finished drafts. Use them as worked examples of the format and the level of detail. They still need a second person's review.

## The 15 categories

The keys under `rules`, in this order: `minimum_wage`, `working_hours`, `overtime_pay`, `rest_days_and_holidays`, `annual_leave`, `sick_leave`, `salary_payment`, `salary_deductions`, `termination_notice`, `early_termination`, `recruitment_fees`, `passport_retention`, `accommodation`, `insurance_and_injury`, `social_security`. What to record for each is in `docs/data-model/collections/labor_laws.md`. A country that has no rule for a category still gets an entry (see "Coverage").

## Steps

1. Create your file from the skeleton (run from `data-scripts/`, virtualenv active):

   ```bash
   python -m src.validators.labor_law --template SG --output data/source/labor-laws/SG.json
   ```

   This replaces the empty `{}` stub. It refuses to overwrite a file that already has content unless you add `--force`. On PowerShell use the backslash path `data\source\labor-laws\SG.json`.

2. For each category, find the law, read the article, and fill the entry. Roughly 25 minutes per category is realistic.
3. Run the checker after every few categories:

   ```bash
   python -m src.validators.labor_law data/source/labor-laws/SG.json
   ```

   It prints `OK` with counts, or lists every problem. A file with any `TODO` left does not pass.
4. Ask a teammate to check at least 5 of your rules against the sources. Add their name to `reviewed_by`.
5. Run `pytest` (it validates every non-empty file) and commit.

## What goes in a rule

| Field | How to fill it |
|---|---|
| `coverage` | `regulated`: a law sets a clear rule. `partly_regulated`: a rule covers only part of it, or only some workers. `not_regulated`: you looked and there is no rule. `unclear`: you could not tell. |
| `title`, `summary` | English for a worker, 1 to 3 sentences. Say what the worker can expect. No legal jargon. |
| `variants` | One per worker group. Start with `["all"]` for general workers. Add a variant for a job type only where the law differs (for example live-in domestic workers, technical interns, working-holiday visa holders). A job-type variant overrides `all` for that worker. The job types are `domestic_worker`, `manufacturing_worker`, `care_worker`, `plantation_worker`, `construction_worker`, `working_holiday`, `other`. |
| `requirements` | One obligation per item, each with the article number. These are what a contract is checked against. |
| `limits` | The numbers, as `{ "value": 40, "unit": "hours", "period": "week", "note": "..." }`. Use the number in force today and say when it applies. |
| `penalty`, `enforced_by` | What the employer risks and who enforces it. Leave `null` if you did not find it. |
| `references` | At least one official source: law name and number, articles, an `https` link. Add `year`, `in_force_since` and the NATLEX record number (`natlex_isn`) when you have them. |
| `confidence` | `high`: you read the article and the wording is clear. `medium`: you read it but part rests on a summary or a translation, or you did not check every exception. `low`: guidance only, or the sources conflict. `unclear` coverage must be `low`. |
| `notes` | What you did not check, exceptions, and anything that changes every year. |
| `last_verified_on` | The day you checked. |

## Rules for accuracy

- **Only write what you read.** Open the article and cite it. Do not fill a gap from memory, a blog, or text you cannot trace to an official page.
- **Paraphrase.** Do not copy long passages of legislation. Quote at most a few words.
- **"Not regulated" is a claim about your sources.** Write in `notes` which sources you searched, so the next person knows. Use `medium` confidence at most.
- **Numbers that change** (minimum wages, holiday counts, contribution rates): use the value in force today, give the effective date in the `note`, and say in `notes` that it is revised.
- **Translations.** An English translation of a law may be unofficial or out of date. Say so in the file-level `notes`, and check for recent amendments.
- **Two sources disagree?** Say so in `notes` and lower the confidence.
- **Every statement in `requirements` must be traceable** to one of the `references`.

## Sources

- **Official legislation portals first** (each country's government law database, and the ministry's own pages for rates and guidance).
- **NATLEX** (`natlex.ilo.org`) is the ILO database of national laws and is the source the task names. It is behind a bot check, so open it in a normal browser. Use it to find the law and record its number in `natlex_isn`; read the operative text from the official portal.
- **ILOSTAT** can confirm a few numbers (minimum wage, weekly hours). It is optional (`ilostat_check`). It also blocks scripts, so use a browser.
- Starting points to verify (not conclusions): Singapore's Employment Act and the Employment of Foreign Manpower Act; South Korea's Labor Standards Act, Minimum Wage Act and the Act on Foreign Workers' Employment; Malaysia's Employment Act 1955 and Minimum Wages Order; Australia's Fair Work Act 2009 and the working holiday visa conditions.

## Files here

| File | What it is |
|---|---|
| `<CC>.json` | The curated file for one country. A file that is still `{}` has not been curated yet. |
| `README.md` | This guide |

The Firestore loader (NF-P1-018) reads every non-empty `<CC>.json`, so keep this folder free of other JSON files.
