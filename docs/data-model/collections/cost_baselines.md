# cost_baselines

Monthly cost-of-living figures for a migrant worker in each host country, used by the Financial Coach to ground the 90-day plan (design 4.4). Shape sources: the path and purpose are **[T]** (tracker NF-FC-003 to -005, design addendum section 7); field names, categories and ids are **[P]**. The curators of NF-FC-003 (SG, AU), NF-FC-004 (KR, MY) and NF-FC-005 (JP, HK) refine the categories, and should tell the team when they change a field name here.

**Six documents, one per host country: `SG`, `KR`, `MY`, `JP`, `HK`, `AU`.** NF-FC-003 covers Singapore and **Australia** (decision of 2026-10-06; the tracker row still lists a different second country, see D-102). NF-FC-003 curated `SG` and `AU` and wrote the checker and the loader; NF-FC-004 curated `KR` and `MY`; NF-FC-005 (`JP`, `HK`) adds its files to `data-scripts/data/source/cost-baselines/` and runs the same loader. The curator's steps are in [data-scripts/README.md](../../../data-scripts/README.md), "Cost baselines".

```
cost_baselines/{host}      host = ISO-2 country, uppercase
```

## `cost_baselines/{host}`

Written by the NF-FC-003/-004/-005 loader, which overwrites by id, so re-running is safe.

| Field | Type | Required | Description |
|---|---|---|---|
| `host_country` | string | yes | Same as the id |
| `currency` | string | yes | ISO 4217 code of the local currency. **Every amount in this document is in it**, so no amount is a bare number without a currency. |
| `categories` | map | yes | Recurring costs. Category id to a figure (below). Ids: `accommodation`, `food`, `transport`, `phone_data`, `mandatory_deductions` |
| `setup_costs` | map | yes | One-off costs of the first month (SIM, transport card, medical check, deposit and so on). Id to a figure; the ids are chosen by the curator and are `snake_case`. |
| `version` | number | yes | Starts at 1. The loader hashes the validated content and raises it by 1 only when the hash changes. |
| `content_hash` | string | yes | SHA-256 of the content in canonical form, **without** `source`, `other_sources` and `curator` (where a figure was read and who read it do not change what a plan is built from, so re-checking a page that still says the same does not raise the version). The figures, the units, the job-type overrides and the `notes` are hashed. |
| `updated_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

### A figure

| Key | Description |
|---|---|
| `low`, `typical`, `high` | Numbers, `low <= typical <= high`. In the document's `currency` for `unit` `month` or `one_off`; a percentage of wages (2.5 means 2.5%) for `pct_of_wage`. |
| `unit` | `month`, `one_off` or `pct_of_wage` (use the last for deductions that are a share of pay) |
| `by_job_type` | Optional. Job type (as in `users`: `domestic_worker`, `care_worker`, and so on) to `{ "low", "typical", "high" }`, replacing the three numbers above for that job, for example accommodation that the employer provides. A job with no entry uses the top-level numbers. |
| `notes` | Optional. What the figure covers, in one line |
| `source` | `{ "url", "publisher", "retrieved_on" }`. **Required on every figure.** An `https` address, the day the page was read (`YYYY-MM-DD`, never in the future), and a publisher. |
| `other_sources` | Optional list of the same shape. For a range that needs more than one page (for example the low end from one page and the high end from another); `notes` says which page gives which end. Added by NF-FC-003. |
| `curator` | Initials of the person who curated it, 2 or 3 capital letters. Required. |

`mandatory_deductions` is the figure the plan most easily gets wrong, so a curator who finds none for a country records a figure of `0` with a note, not an empty field.

### What the checker refuses

`python -m src.validators.cost_baselines` (and the loader, before it writes anything) refuses: a country that is not one of the six, or written in the wrong currency; a file whose name is not its country; a missing or extra category (exactly the five above); `low <= typical <= high` broken or a negative figure; a recurring cost whose unit is not `month` (only `mandatory_deductions` may be `pct_of_wage`), a setup cost whose unit is not `one_off`, or a share above 100; a job type that is not one of the users' `job_type` values; **a figure of 0 without a `notes` line** and any `mandatory_deductions` without one; a missing or `http` source, a source day in the future, a `TODO` left in a note, a note of over 320 characters, curator initials that are a name; and any field the loader owns (`version`, `content_hash`, `updated_at`, `schema_version`) written into the file.

### How low, typical and high are read

A figure is a **published price or range, not a measured average of what workers spend**. The `notes` line says how each of the three numbers was read: the ends of a published range, a median, or the midpoint of a range (labelled as such). Where a source gives a weekly amount, the month is weekly times 52/12, and where it gives a 28-day price the month is that price times 13/12. A figure that is arithmetic on a rule (for example a rental bond of four weeks' rent) says so.

**Example** — `cost_baselines/AU`, abridged (the real document is `data-scripts/data/source/cost-baselines/AU.json` plus the four loader fields; `food`, `transport`, `phone_data` and one more setup cost are left out here, and the notes are shortened)

```json
{
  "host_country": "AU",
  "currency": "AUD",
  "categories": {
    "accommodation": {
      "low": 1192, "typical": 1257, "high": 2383, "unit": "month",
      "notes": "A room in a share house, weekly rent times 52/12. Low: Monash. Typical: PropTrack national median. High: UTS. ...",
      "source": { "url": "https://www.proptrack.com.au/?p=5122", "publisher": "PropTrack, article of 22 January 2024", "retrieved_on": "2026-10-08" },
      "other_sources": [
        { "url": "https://www.monash.edu/study/why-choose-monash/our-locations/life-in-melbourne/cost-of-living", "publisher": "Monash University, cost of living", "retrieved_on": "2026-10-08" },
        { "url": "https://www.uts.edu.au/for-students/international/life-in-sydney/cost-of-living", "publisher": "University of Technology Sydney, cost of living in Sydney", "retrieved_on": "2026-10-08" }
      ],
      "curator": "DD"
    },
    "mandatory_deductions": {
      "low": 15, "typical": 15, "high": 30, "unit": "pct_of_wage",
      "notes": "Tax withheld from a working holiday maker's pay from 1 July 2026: 15% up to 45,000 a year, 30% above. ...",
      "source": { "url": "https://www.ato.gov.au/tax-rates-and-codes/schedule-15-tax-table-for-working-holiday-makers", "publisher": "Australian Taxation Office, Schedule 15, published 17 June 2026", "retrieved_on": "2026-10-08" },
      "curator": "DD"
    }
  },
  "setup_costs": {
    "rental_bond": {
      "low": 1100, "typical": 1160, "high": 2200, "unit": "one_off",
      "notes": "Four weeks' rent, the most a NSW landlord may take as a bond. ...",
      "source": { "url": "https://www.nsw.gov.au/housing-and-construction/rules/costs-at-start-of-a-residential-tenancy", "publisher": "NSW Government (NSW Fair Trading), costs at the start of a tenancy", "retrieved_on": "2026-10-08" },
      "curator": "DD"
    }
  },
  "version": 1,
  "content_hash": "88234aefa49f... (64 hex characters)",
  "updated_at": "2026-10-08T15:18:07Z",
  "schema_version": 1
}
```

**A job-type override** — from `cost_baselines/SG`: the default `accommodation` is a dormitory bed for a Work Permit holder; a live-in domestic worker pays nothing, because MOM puts housing and meals on the employer.

```json
"accommodation": {
  "low": 420, "typical": 450, "high": 450, "unit": "month",
  "by_job_type": { "domestic_worker": { "low": 0, "typical": 0, "high": 0 } },
  ...
}
```

The default of each country is the worker group the first figure describes, named in the `notes`: a dormitory Work Permit holder in `SG`, a working-holiday maker in `AU`, an E-9 worker in an employer dormitory in `KR`, a foreign worker in employer housing in `MY`. In `KR`, `accommodation` is a ceiling on the employer's housing deduction, not a market rent; in `MY` it is what the worker pays under the rent cap (see the NF-FC-004 runbook).

## How it is used and refreshed

- The plan records `grounding.baselines.version` (see [coach](coach.md)), so a reviewer can tell which version of the baselines a plan used. A new baseline does not change a plan that already exists: the plan is keyed by the worker's slots, not by the baselines.
- Costs change slowly, so there is no TTL and no cron. Refreshing means re-running the loader with new figures and sources; the version rises on its own. Running it again with nothing changed writes nothing; a new source or curator on the same figures is stored without a new version.
- Currencies other than the six corridor pairs are not converted here: the plan converts with live rates (`rates_cache`) where a pair exists, and otherwise states the figure in the local currency.

**Access:** signed-in users read (reference data, no personal data); only the data script writes.
