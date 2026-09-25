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

One curated legal rule. The document id is the category id, so each country has exactly one rule per category and re-running the loader overwrites it.

| Field | Type | Required | Description |
|---|---|---|---|
| `country` | string | yes | ISO-2 |
| `category` | string | yes | One of the 15 ids below, same as the document id |
| `title` | string | yes | Short English title |
| `summary` | string | yes | The rule in plain English, as a worker would need to understand it |
| `applies_to` | array of string | no | Job types the rule covers, when it does not cover everyone (for example `["domestic_worker"]`). Absent means all workers. |
| `requirements` | array of string | yes | The specific obligations, one per item. This is what the clause comparison (NF-P2-004) checks a contract against. |
| `limits` | map | no | Numbers a clause can be compared with. Each key maps to `{ "value": number, "unit": string }`. |
| `references` | array of map | yes | Sources: `{ "name": "...", "section": "...", "url": "..." }`. At least one. |
| `ilostat_check` | map or null | no | `{ "indicator": "...", "value": number, "checked_on": "YYYY-MM-DD" }` when ILOSTAT confirms a number, otherwise `null` |
| `notes` | string | no | Exceptions and caveats |
| `last_verified_on` | string (date) | yes | |
| `schema_version` | number | yes | `1` |

**Example** — `labor_laws/SG/rules/working_hours`. **This shows the shape only. The values are placeholders and are not curated law.**

```json
{
  "country": "SG",
  "category": "working_hours",
  "title": "Working hours",
  "summary": "Example text: how many hours a worker can be required to work.",
  "requirements": ["Example requirement: a limit on regular weekly hours."],
  "limits": { "max_regular_hours_per_week": { "value": 40, "unit": "hours" } },
  "references": [{ "name": "Example Act", "section": "Example section", "url": "https://example.org/act" }],
  "ilostat_check": null,
  "last_verified_on": "2026-09-27",
  "schema_version": 1
}
```

## The 15 categories [P]

These are the document ids under `rules`. They were chosen from the design doc's own examples ("uncompensated overtime, illegal deductions, termination penalties"), the passport-retention example in ADR-002, the social-security comparison in the design doc (Singapore CPF, Malaysia EPF, Korean NPS) and the typical complaints of migrant workers. **The team should confirm the list before NF-P1-017 curation starts**, because renaming a category later means changing 6 countries of data and every stored report.

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

A category that a country does not regulate is still written, with `requirements` saying so (for example "No statutory minimum wage") and a reference. This keeps the count at 15 and lets the comparison step tell "no rule" apart from "not curated".

## Loading (NF-P1-018)

1. Validate each country's JSON: 15 categories, all fields present, at least one reference per rule.
2. Write the rules with `set` on `labor_laws/{country}/rules/{category}`.
3. Compute the country's `content_hash`. If it differs from the one in `_meta/current`, write `_meta/current` with `version` increased by 1 and the new hash. If it is the same, leave the version alone. This keeps the loader safe to re-run without invalidating every cached report.
4. Write the `labor_laws/{country}` header.

## Access and tasks

- **Access:** signed-in users read; only the data script writes.
- **Index:** none beyond the automatic ones. The rules of one country are read as one collection: `labor_laws/{country}/rules` (15 documents).
- **Tasks:** NF-P1-017 (curate), NF-P1-018 (load), NF-P2-003 (retrieve by country), NF-P2-004 (compare), NF-P2-007 (cache keyed on `version`).
