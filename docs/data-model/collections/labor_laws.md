# labor_laws

Shape sources: the three paths are **[D]** (`_meta` needs a document id, see `firestore-schema.md`). "15 categories per country" and "a `_meta` document per country with version metadata" come from NF-P1-017 and NF-P1-018 **[T]**. The 15 category ids and the rule fields are **[P]**: no document names the categories, and the team must confirm them before curation starts.

Six countries: `SG`, `KR`, `MY`, `JP`, `HK`, `AU`. The curated source is NATLEX (manually curated, one JSON file per country in `data-scripts/data/source/labor-laws/`), with ILOSTAT used to spot-check numbers. Curation split: Devam SG and AU, Aditya KR and MY, Pranjal JP and HK.

```
labor_laws/{country}                    header
labor_laws/{country}/_meta/current      version (used by the contract cache)
labor_laws/{country}/rules/{category}   15 rules
```

## `labor_laws/{country}`

| Field | Type | Required | Description |
|---|---|---|---|
| `country` | string | yes | ISO-2, same as the document id |
| `name` | string | yes | Country name in English |
| `rule_count` | number | yes | Number of documents in `rules` (15) |
| `updated_at` | timestamp | yes | Last load |

## `labor_laws/{country}/_meta/current`

The version number that decides whether a stored contract report is still valid.

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | number | yes | Whole number, starts at 1. **Increase it whenever any rule of this country changes** (see `versioning.md`). |
| `updated_at` | timestamp | yes | When this version was loaded |
| `category_ids` | array of string | yes | The category ids loaded, in the order below |
| `content_hash` | string | yes | SHA-256 of the country's source JSON. The loader compares it to decide whether to bump `version`. |
| `curated_by` | array of string | yes | Who curated the rules |
| `reviewed_by` | array of string | no | Who checked the curation; empty until a second person has reviewed |
| `last_verified_on` | string (date) | yes | When the numbers were last checked against the sources |
| `notes` | string | no | Free text for curators |
| `schema_version` | number | yes | `1` |

**Example** — `labor_laws/SG/_meta/current`

```json
{
  "version": 1,
  "updated_at": "2026-09-27T12:00:00Z",
  "category_ids": ["minimum_wage", "working_hours", "overtime_pay", "rest_days_and_holidays", "annual_leave", "sick_leave", "salary_payment", "salary_deductions", "termination_notice", "early_termination", "recruitment_fees", "passport_retention", "accommodation", "insurance_and_injury", "social_security"],
  "content_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "curated_by": ["Devam"],
  "last_verified_on": "2026-09-27",
  "schema_version": 1
}
```

## `labor_laws/{country}/rules/{category}`

One curated legal rule. The document id is the category id, so each country has exactly one rule per category and re-running the loader overwrites it. The document is the rule from the curated JSON file (see "Curation files" below) plus `country`, `category` and `schema_version`.

Different worker groups can fall under different law. A live-in domestic worker is outside the minimum wage of most countries, for example, and a technical intern has protections a general employee does not. So a rule holds one or more **variants**, one per worker group.

| Field | Type | Required | Description |
|---|---|---|---|
| `country` | string | yes | ISO-2 |
| `category` | string | yes | One of the 15 ids below, same as the document id |
| `coverage` | string | yes | `regulated`, `partly_regulated`, `not_regulated` or `unclear`. This tells "the law sets no rule" apart from "we have not looked". |
| `title` | string | yes | Short English title |
| `summary` | string | yes | The rule in plain English for a worker, 20 to 800 characters |
| `variants` | array of map | yes, at least 1 | The rule per worker group, see below |
| `references` | array of map | yes, at least 1 | Where the rule comes from, see below |
| `ilostat_check` | map or null | no | `{ "indicator": "...", "value": number, "checked_on": "YYYY-MM-DD" }` when ILOSTAT confirms a number |
| `confidence` | string | yes | `high`, `medium` or `low`. `unclear` coverage must be `low`. |
| `notes` | string | no | Exceptions, caveats and things not checked |
| `last_verified_on` | string (date) | yes | |
| `schema_version` | number | yes | `1` |

**Variant** (each entry of `variants`):

| Field | Type | Required | Description |
|---|---|---|---|
| `applies_to` | array of string | yes | `["all"]`, or one or more job types from [users](users.md). A job-type variant **overrides** the `all` variant for that worker. A job type may appear in only one variant, and `all` cannot be combined with job types in one variant. |
| `requirements` | array of string | yes | The obligations, one per item, each naming the article. This is what the clause comparison (NF-P2-004) checks a contract against. |
| `limits` | map | no | Numbers a clause can be compared with. Each key maps to `{ "value": number, "unit": string, "period": string, "note": string }`; `period` is `hour`, `day`, `week`, `month`, `year` or `once`, and `period` and `note` are optional. |
| `penalty` | string or null | no | What happens to an employer who breaks the rule |
| `enforced_by` | string or null | no | The authority that enforces it, useful for the complaint step |

**Reference** (each entry of `references`): `law` (name and number), `section` (articles), `url` (an `https` link to the official text), and optionally `year`, `in_force_since` (date) and `natlex_isn` (the NATLEX record number).

**Example** — `labor_laws/JP/rules/working_hours` (real curated data for Japan)

```json
{
  "country": "JP",
  "category": "working_hours",
  "coverage": "regulated",
  "title": "Working hours and breaks",
  "summary": "Workers may not be made to work more than 8 hours a day or 40 hours a week, not counting breaks. Longer hours are only lawful under a written agreement with the workers' representative that is filed with the labor office.",
  "variants": [
    {
      "applies_to": [
        "all"
      ],
      "requirements": [
        "No more than 40 hours per week and 8 hours per day, excluding break periods (Labor Standards Act, Art. 32).",
        "Breaks: at least 45 minutes if working hours exceed 6 hours, and at least 1 hour if they exceed 8 hours; workers may use breaks freely (Art. 34).",
        "Working beyond these limits is lawful only under a written agreement with the majority union or worker representative, filed with the authority (Art. 36(1))."
      ],
      "limits": {
        "weekly_hours_limit": {
          "value": 40,
          "unit": "hours",
          "period": "week"
        },
        "daily_hours_limit": {
          "value": 8,
          "unit": "hours",
          "period": "day"
        },
        "break_when_over_6_hours": {
          "value": 45,
          "unit": "minutes",
          "period": "day"
        },
        "break_when_over_8_hours": {
          "value": 60,
          "unit": "minutes",
          "period": "day"
        }
      },
      "penalty": null,
      "enforced_by": "Labour standards inspection offices (Ministry of Health, Labour and Welfare)"
    }
  ],
  "references": [
    {
      "law": "Labor Standards Act (Act No. 49 of 1947)",
      "section": "Arts. 32, 34, 36(1) and 116(2)",
      "url": "https://www.japaneselawtranslation.go.jp/en/laws/view/3567/en",
      "year": 1947
    }
  ],
  "ilostat_check": null,
  "confidence": "high",
  "notes": "The Act does not apply to domestic workers employed directly by a household (Art. 116(2)); a helper employed by a company is covered. Exceptions for managers and some variable-hours systems (Arts. 32-2 to 32-5, 41) were not curated in detail.",
  "last_verified_on": "2026-09-25",
  "schema_version": 1
}
```

## Curation files

Each person curates two countries into `data-scripts/data/source/labor-laws/<CC>.json` (`JP.json`, `HK.json`, and so on). The file holds the top-level fields `country`, `name`, `curated_by`, `reviewed_by`, `last_verified_on`, `notes` and `rules` (an object with the 15 category ids as keys). The rule under each key has the fields above without `country`, `category` and `schema_version`, which the loader adds.

`python -m src.validators.labor_law` checks every file (run it from `data-scripts/`). `--template CC` prints a starting skeleton. The step-by-step guide for curators is `data-scripts/data/source/labor-laws/README.md` and the runbook is `docs/runbooks/NF-P1-017-labor-law-curation.md`.

## The 15 categories [P]

These are the document ids under `rules`. They were chosen from the original design's own examples ("uncompensated overtime, illegal deductions, termination penalties"), the passport-retention example in ADR-002, the social-security comparison in the original design (Singapore CPF, Malaysia EPF, Korean NPS) and the typical complaints of migrant workers. **The team should confirm the list before NF-P1-017 curation starts**, because renaming a category later means changing 6 countries of data and every stored report.

| # | Id | What to record |
|---|---|---|
| 1 | `minimum_wage` | Legal minimum wage or wage floor, and who it applies to |
| 2 | `working_hours` | Daily and weekly limits, break requirements |
| 3 | `overtime_pay` | When overtime starts, the pay multiplier, any cap on overtime hours |
| 4 | `rest_days_and_holidays` | Weekly rest day, paid public holidays |
| 5 | `annual_leave` | Paid leave entitlement and how it grows |
| 6 | `sick_leave` | Paid sick leave and medical certificate rules |
| 7 | `salary_payment` | How often and how soon wages must be paid, payment method, payslips |
| 8 | `salary_deductions` | Which deductions are allowed and their limits |
| 9 | `termination_notice` | Notice period and grounds for ending the contract |
| 10 | `early_termination` | Penalties, repatriation costs and return-ticket rules when a contract ends early |
| 11 | `recruitment_fees` | Limits on fees charged to workers, who must pay |
| 12 | `passport_retention` | Whether an employer may hold a passport or documents |
| 13 | `accommodation` | Housing standards and any charge for it |
| 14 | `insurance_and_injury` | Mandatory medical insurance and work-injury compensation |
| 15 | `social_security` | Pension or provident fund and other contributions (CPF, EPF, NPS, ...) |

A category that a country does not regulate is still written, with `coverage` set to `not_regulated` (or `partly_regulated` or `unclear`), `requirements` saying what was and was not found, and a reference to the source that was checked. This keeps the count at 15 and lets the comparison step tell "no rule" apart from "not curated".

## Loading (NF-P1-018)

The loader is `data-scripts/src/loaders/ilo_natlex.py` (`python -m src.loaders.ilo_natlex`).

1. Validate each country's JSON with `LaborLawFile` from `data-scripts/src/validators/labor_law.py`: 15 categories, all fields present, at least one variant and one reference per rule, no placeholder text. Skip a file that is still `{}`. If any file fails, stop before writing anything.
2. Compute the country's `content_hash`: the SHA-256 of the canonical JSON (sorted keys, no extra whitespace) of the validated `country` and `rules`. It is not the hash of the file bytes, so line endings, JSON layout, `reviewed_by` and the file-level `notes` never change it; any change to a rule (including its `last_verified_on`) does.
3. Read `_meta/current`. Missing: `version` is 1. Same hash: keep the version and do not rewrite `_meta`. Different hash: `version` is the stored value plus 1, with the new hash. This keeps the loader safe to re-run without invalidating every cached report. Putting an edited rule back does not restore the old version number; it counts as another change.
4. In **one batch per country**, write the 15 rules (`set` on `labor_laws/{country}/rules/{category}`), the `labor_laws/{country}` header, and `_meta/current` when the version changed. One batch means a crash cannot leave a country with new rules and an old version. The version is read just before the batch, so do not run two loaders at the same time.

## Access and tasks

- **Access:** signed-in users read; only the data script writes.
- **Index:** none beyond the automatic ones. The rules of one country are read as one collection: `labor_laws/{country}/rules` (15 documents).
- **Tasks:** NF-P1-017 (curate), NF-P1-018 (load), NF-P2-003 (retrieve by country), NF-P2-004 (compare), NF-P2-007 (cache keyed on `version`).
