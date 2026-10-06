# cost_baselines

Monthly cost-of-living figures for a migrant worker in each host country, used by the Financial Coach to ground the 90-day plan (design 4.4). Shape sources: the path and purpose are **[T]** (tracker NF-FC-003 to -005, design addendum section 7); field names, categories and ids are **[P]**. The curators of NF-FC-003 (SG, AU), NF-FC-004 (KR, MY) and NF-FC-005 (JP, HK) refine the categories, and should tell the team when they change a field name here.

**Six documents, one per host country: `SG`, `KR`, `MY`, `JP`, `HK`, `AU`.** NF-FC-003 covers Singapore and **Australia** (decision of 2026-10-06; the tracker row still lists a different second country, see D-102).

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
| `content_hash` | string | yes | SHA-256 of the content in canonical form |
| `updated_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

### A figure

| Key | Description |
|---|---|
| `low`, `typical`, `high` | Numbers, `low <= typical <= high`. In the document's `currency` for `unit` `month` or `one_off`; a percentage of wages (2.5 means 2.5%) for `pct_of_wage`. |
| `unit` | `month`, `one_off` or `pct_of_wage` (use the last for deductions that are a share of pay) |
| `by_job_type` | Optional. Job type (as in `users`: `domestic_worker`, `care_worker`, and so on) to `{ "low", "typical", "high" }`, replacing the three numbers above for that job, for example accommodation that the employer provides. A job with no entry uses the top-level numbers. |
| `notes` | Optional. What the figure covers, in one line |
| `source` | `{ "url", "publisher", "retrieved_on" }`. **Required on every figure.** `retrieved_on` is `YYYY-MM-DD`. |
| `curator` | Initials of the person who curated it. Required. |

`mandatory_deductions` is the figure the plan most easily gets wrong, so a curator who finds none for a country records a figure of `0` with a note, not an empty field.

**Example** — `cost_baselines/AU` (the numbers and the source are placeholders; NF-FC-003 curates the real ones)

```json
{
  "host_country": "AU",
  "currency": "AUD",
  "categories": {
    "accommodation": {
      "low": 800, "typical": 1100, "high": 1600, "unit": "month",
      "by_job_type": { "care_worker": { "low": 700, "typical": 950, "high": 1400 } },
      "notes": "Shared room, outside the city centre",
      "source": { "url": "https://example.org/placeholder", "publisher": "Placeholder", "retrieved_on": "2026-10-28" },
      "curator": "XX"
    },
    "mandatory_deductions": {
      "low": 0, "typical": 0, "high": 0, "unit": "pct_of_wage",
      "notes": "Placeholder: the curator records what is actually withheld",
      "source": { "url": "https://example.org/placeholder", "publisher": "Placeholder", "retrieved_on": "2026-10-28" },
      "curator": "XX"
    }
  },
  "setup_costs": {
    "transport_card": {
      "low": 10, "typical": 20, "high": 40, "unit": "one_off",
      "source": { "url": "https://example.org/placeholder", "publisher": "Placeholder", "retrieved_on": "2026-10-28" },
      "curator": "XX"
    }
  },
  "version": 1,
  "content_hash": "2c4e6a8b0d1f3a5c7e9b1d3f5a7c9e0b2d4f6a8c0e1b3d5f7a9c1e3b5d7f9a0c",
  "updated_at": "2026-10-28T09:00:00Z",
  "schema_version": 1
}
```

## How it is used and refreshed

- The plan records `grounding.baselines.version` (see [coach](coach.md)), so a reviewer can tell which version of the baselines a plan used. A new baseline does not change a plan that already exists: the plan is keyed by the worker's slots, not by the baselines.
- Costs change slowly, so there is no TTL and no cron. Refreshing means re-running the loader with new figures and sources; the version rises on its own.
- Currencies other than the six corridor pairs are not converted here: the plan converts with live rates (`rates_cache`) where a pair exists, and otherwise states the figure in the local currency.

**Access:** signed-in users read (reference data, no personal data); only the data script writes.
