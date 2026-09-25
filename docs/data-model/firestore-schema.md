# Firestore schema

Status: NF-P1-013, written 2026-09-25. This is the working contract for every task that reads or writes Firestore. Field-level detail is in [`collections/`](collections/) and version rules are in [`versioning.md`](versioning.md).

How to read it: each collection group says where its shape comes from.

| Tag | Meaning |
|---|---|
| **[D]** | Stated in the design doc (section 4.7 and the pillar pipelines) |
| **[T]** | Needed by a tracker task description |
| **[P]** | Proposed here because nothing else defines it. Owners of the named task may refine it, but should tell the team when they change a field name. |
| **[built]** | Already exists in the repo (code or committed data) |

## Database

| Setting | Value |
|---|---|
| Project | `nomadfinance-prod` |
| Database | `(default)`, Firestore **Native** mode |
| Location | `asia-south1` (Mumbai), same as Cloud Run |
| State on 2026-09-25 | Empty: no collections, no indexes |
| Local development | Firebase Emulator Suite (`FIRESTORE_EMULATOR_HOST`), see `NF-P1-001-local-dev-setup.md` |

## Collection map

Every path below is a valid Firestore path: collections sit at odd positions and documents at even positions (`collection/doc/collection/doc`). "Backend" means the FastAPI service using the Admin SDK, which bypasses security rules.

| Path | Document id | Holds | Pillar | Written by | Detail |
|---|---|---|---|---|---|
| `users/{uid}` | Firebase Auth uid | App profile and preferences | All | Onboarding (NF-P1-022), profile page (NF-P1-023) | [users](collections/users.md) |
| `users/{uid}/notifications/{id}` | auto | Alerts and reminders for this user | Radar | Backend (NF-P3-004) | [users](collections/users.md) |
| `users/{uid}/contracts/{contractId}` | auto | One uploaded contract: metadata, score, status | Contract Shield | Backend | [contracts](collections/contracts.md) |
| `users/{uid}/contracts/{contractId}/reports/{language}` | language code | Full report in one language, including the cache | Contract Shield | Backend | [contracts](collections/contracts.md) |
| `complaint_templates/{country}/types/{type}` | violation type | Complaint letter structure and authority per country | Contract Shield | Data script | [contracts](collections/contracts.md) |
| `users/{uid}/transfers/{id}` | auto | A remittance the user logged | Remittance + FIB | Backend (NF-P2-017) | [fib](collections/fib.md) |
| `users/{uid}/income/{id}` | auto | An income entry | FIB | Backend (NF-P3-010) | [fib](collections/fib.md) |
| `users/{uid}/bills/{id}` | auto | A bill paid | FIB | Backend (NF-P3-010, -011) | [fib](collections/fib.md) |
| `users/{uid}/savings/{id}` | auto | A savings entry. **Added: missing from the design table.** | FIB | Backend (NF-P3-010) | [fib](collections/fib.md) |
| `users/{uid}/financial_profile/current` | `current` | Computed financial identity | FIB | Backend, weekly (NF-P3-013) | [fib](collections/fib.md) |
| `corridors/{corridorId}` | `SG-PH` style | RPW provider prices for one corridor | Remittance | Data script (NF-P1-016) | [corridors](collections/corridors.md) |
| `rates_cache/{pair}` | `SGD_PHP` style | Latest live FX rate | Remittance | Cron (NF-P1-019) | [rates_cache](collections/rates_cache.md) |
| `rates_history/{pair}` and `.../points/{pointId}` | hour or day | FX rate history for trend charts | Remittance | Cron, backfill | [rates_cache](collections/rates_cache.md) |
| `labor_laws/{country}` | ISO-2 country | Country header | Contract Shield | Data script (NF-P1-018) | [labor_laws](collections/labor_laws.md) |
| `labor_laws/{country}/_meta/current` | `current` | Version for cache invalidation | Contract Shield | Data script (NF-P1-018) | [labor_laws](collections/labor_laws.md) |
| `labor_laws/{country}/rules/{category}` | one of 15 category ids | One curated legal rule | Contract Shield | Data script (NF-P1-018) | [labor_laws](collections/labor_laws.md) |
| `radar_reports/{id}` | auto | One community report | Radar | Backend (NF-P3-001) | [radar](collections/radar.md) |
| `report_embeddings/{id}` | same id as the report | Vector for similarity search | Radar | Backend (NF-P3-002) | [radar](collections/radar.md) |
| `radar_entities/{slug}` | slugified name | Aggregated risk profile of one operator, agency or employer | Radar | Backend (NF-P3-003) | [radar](collections/radar.md) |
| `radar_alerts/{corridor}` and `.../current/{alertId}` | auto | Active alerts per corridor | Radar | Cron (NF-P3-004) | [radar](collections/radar.md) |

## Differences from the design doc table (section 4.7)

The design doc lists some paths that Firestore cannot hold and misses one collection. These are the changes, all marked [P]:

| Design doc | Problem | Used here |
|---|---|---|
| `users/{uid}/financial_profile` | Three segments make a collection, not a document | `users/{uid}/financial_profile/current` |
| `labor_laws/{country}/_meta` | Same | `labor_laws/{country}/_meta/current` |
| `radar_alerts/{corridor}/current` | Same | `radar_alerts/{corridor}/current/{alertId}` |
| `complaint_templates/{country}/{type}` | A variable in the collection position | `complaint_templates/{country}/types/{type}` |
| `rates_history/{pair}/points` | Same as the first row | `rates_history/{pair}/points/{pointId}` |
| (missing) | NF-P3-010 needs `POST /fib/savings` | `users/{uid}/savings/{id}` |

Each parent document (`labor_laws/{country}`, `rates_history/{pair}`, `radar_alerts/{corridor}`, `complaint_templates/{country}`) is created as a real small document. Firestore lets a subcollection exist under a missing parent, but a missing parent does not show up when listing the parent collection.

## Conventions

| Topic | Rule |
|---|---|
| Field names | `snake_case`, the same names in Firestore, Pydantic models and the TypeScript types |
| Enum values | lowercase `snake_case` strings |
| Countries | ISO 3166-1 alpha-2, uppercase (`SG`, `PH`) |
| Currencies | ISO 4217, uppercase (`SGD`, `PHP`) |
| Languages | `en`, `hi`, `tl`, `id`, `ne`, `bn` (the 6 supported UI languages) |
| Corridor id | `<from>-<to>` in ISO-2: `SG-PH`, `SG-IN`, `AU-IN`, `MY-ID`, `JP-PH`, `AU-PH` |
| Currency pair id | `<from>_<to>` in ISO-4217: `SGD_PHP`, `SGD_INR`, `AUD_INR`, `MYR_IDR`, `JPY_PHP`, `AUD_PHP` |
| Instants | Firestore `timestamp`: `created_at`, `updated_at`, `fetched_at` |
| Calendar dates | `string` `YYYY-MM-DD`: `entry_date`, `surveyed_on`. A date is not an instant, so no time zone. |
| Money | `number` in major units (12.50 means 12 dollars 50 cents) plus a separate `currency` field. Money is never a bare number. |
| Rates and percentages | `number`; percentages are plain (2.54 means 2.54%) |
| Missing values | Leave the field out when unknown, except where a table says `null` on purpose. Readers must treat "absent" and `null` the same. |
| Document ids | Auto ids for user-created records; natural keys (corridor, pair, country, category, slug) for reference data, so re-running a loader overwrites instead of duplicating |
| Reserved ids | Ids may not start and end with `__`, and may not contain `/`. `_meta` is allowed. |
| Versioning | User-owned and AI-written documents carry `schema_version` (integer, starts at 1). See `versioning.md`. |
| AI-written documents | Store the `model` ids and prompt versions used, so a result can be traced. |

Firestore limits that matter here: a document is at most 1 MiB (the biggest planned one, `corridors/JP-PH`, is about 26 KB), a single document should not be written more than about once a second for long periods, and a vector field can have at most 2048 dimensions.

## Access matrix

Input for the security rules task (NF-P1-014). It states intent. Backend access always works, because the Admin SDK skips the rules.

| Collection | Signed-in owner | Other signed-in users | Anonymous |
|---|---|---|---|
| `users/{uid}` | Read; write only the profile fields (not `created_at`, `schema_version`) | None | None |
| `users/{uid}/notifications` | Read; update only `read` and `read_at` | None | None |
| `users/{uid}/contracts` and `.../reports` | Read | None | None |
| `users/{uid}/transfers`, `income`, `bills`, `savings` | Read | None | None |
| `users/{uid}/financial_profile` | Read | None | None |
| `corridors`, `rates_cache`, `rates_history`, `labor_laws` (all subcollections), `complaint_templates` | Read (reference data) | Read | None |
| `radar_entities`, `radar_alerts` | Read (aggregated, no personal data) | Read | None |
| `radar_reports`, `report_embeddings` | None (the backend serves reports through the API and hides `reporter_hash`) | None | None |

Entries created by the user (transfers, income, bills, savings) are written by the backend so the values can be validated and categorized. If a task needs the browser to write directly, that task must add the matching rule.

## Required indexes

Single-field indexes are automatic. These need to be created; the file `firestore.indexes.json` is currently empty and is out of scope for this task.

| Collection | Fields | Used by |
|---|---|---|
| `radar_reports` | `entity_slug` asc, `created_at` desc | Entity profile page (NF-P3-008) |
| `radar_reports` | `corridor_id` asc, `created_at` desc | Surge detection cron (NF-P3-004) |
| `radar_entities` | `corridors` array-contains, `report_count` desc | Heatmap and corridor lists (NF-P3-007) |
| `users/*/notifications` (collection group `notifications`, scope: collection) | `read` asc, `created_at` desc | Unread alert feed (NF-P3-009) |
| `report_embeddings` | `corridor_id` asc, `embedding` vector (dimension 768, flat) | Similar-report search (NF-P3-002) |

The vector index is created with `gcloud` (check `gcloud firestore indexes composite create --help` for the current syntax):

```bash
gcloud firestore indexes composite create --project nomadfinance-prod \
  --collection-group=report_embeddings --query-scope=COLLECTION \
  --field-config=field-path=corridor_id,order=ascending \
  --field-config=field-path=embedding,vector-config='{"dimension":768,"flat":{}}'
```

## Cloud Storage paths (not Firestore, referenced by it) [P]

`storage.rules` is a separate shared file owned by NF-P1-014.

| Path | Holds | Referenced by |
|---|---|---|
| `contracts/{uid}/{contractId}/{filename}` | Uploaded contract file | `users/{uid}/contracts/{id}.storage_path` |
| `bills/{uid}/{billId}/{filename}` | Bill or payslip photo | `users/{uid}/bills/{id}.image_path` |
| `radar-evidence/{reportId}/{filename}` | Optional report attachment | `radar_reports/{id}.evidence_paths` |
| `exports/{uid}/financial-identity-{timestamp}.pdf` | Exported Financial Identity PDF | `financial_profile/current.latest_export` |

## How the pillars share data

```
Remittance X-Ray ──log transfer──────────► users/{uid}/transfers ──► Financial Identity
Contract Shield ──anonymised signal──────► radar_reports  (source: contract_signal)
Contract Shield ──verified employment────► users/{uid}/income      (source: contract)
Radar ──flagged entity────────────────────► shown in Remittance (provider slug) and Contract Shield (employer or agency slug)
```

The join key for the two "shown in" links is the entity `slug` (a slugified name), see [radar](collections/radar.md).

## Questions the team still needs to settle

| # | Question | Default used here | Decide before |
|---|---|---|---|
| 1 | Are the 15 labor-law categories in [labor_laws](collections/labor_laws.md) right? | The list in that file | NF-P1-017 (curation) |
| 2 | Push notifications: store FCM tokens per user, or use FCM topics per corridor? | Tokens in `users/{uid}.fcm_tokens` | NF-P3-004 |
| 3 | Contract text is stored in Firestore in the report documents. Is that acceptable for real users? | Yes for the prototype with demo data (ADR-002: free-tier Gemini content may be used by Google); real data needs the paid tier and a retention rule | Public demo |
| 4 | Should signed-in users read `radar_reports` directly? | No, the backend serves them | NF-P1-014 |
