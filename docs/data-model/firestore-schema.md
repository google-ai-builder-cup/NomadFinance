# Firestore schema

Status: NF-P1-013, written 2026-09-25; extended for Future Scope by NF-F0-003, 2026-10-06 (eight new collections, the rows marked *Future Scope*); rules and index entries for them added by NF-F0-004, 2026-10-06; reconciled with the code, the rules, the index file and the production project by NF-HR-013, 2026-10-11 (`scam_stats` and the contract `extraction` document added, the live state of indexes and TTL recorded, the Storage table corrected). This is the working contract for every task that reads or writes Firestore. Field-level detail is in [`collections/`](collections/) and version rules are in [`versioning.md`](versioning.md).

How to read it: each collection group says where its shape comes from.

| Tag | Meaning |
|---|---|
| **[D]** | Stated in the original design |
| **[T]** | Needed by a tracker task description |
| **[P]** | Proposed here because nothing else defines it. Owners of the named task may refine it, but should tell the team when they change a field name. |
| **[built]** | Already exists in the repo (code or committed data) |

## Database

| Setting | Value |
|---|---|
| Project | `nomadfinance-prod` |
| Database | `(default)`, Firestore **Native** mode |
| Location | `asia-south1` (Mumbai), same as Cloud Run |
| Storage bucket | `nomadfinance-prod.firebasestorage.app` (`FIREBASE_STORAGE_BUCKET`), see "Cloud Storage paths" |
| Protection | Delete protection and point-in-time recovery are both off (read from the project on 2026-10-11) |
| State | In use. Indexes, single-field settings and TTL policies were read from the project on 2026-10-11: see "Required indexes" and "Time to live" |
| Local development | Firebase Emulator Suite (`FIRESTORE_EMULATOR_HOST`), see `NF-P1-001-local-dev-setup.md` |

## Collection map

Every path below is a valid Firestore path: collections sit at odd positions and documents at even positions (`collection/doc/collection/doc`). "Backend" means the FastAPI service using the Admin SDK, which bypasses security rules.

| Path | Document id | Holds | Pillar | Written by | Detail |
|---|---|---|---|---|---|
| `users/{uid}` | Firebase Auth uid | App profile and preferences | All | Onboarding (NF-P1-022), profile page (NF-P1-023) | [users](collections/users.md) |
| `users/{uid}/notifications/{id}` | auto | Alerts and reminders for this user | Radar | Backend (NF-P3-004) | [users](collections/users.md) |
| `users/{uid}/contracts/{contractId}` | auto | One uploaded contract: metadata, score, status | Contract Shield | Backend | [contracts](collections/contracts.md) |
| `users/{uid}/contracts/{contractId}/extraction/current` | `current` | The text blocks step 1 read from the file, kept so the analysis runs without the file | Contract Shield | Backend (NF-P2-007) | [contracts](collections/contracts.md) |
| `users/{uid}/contracts/{contractId}/reports/{language}` | language code | Full report in one language, including the cache | Contract Shield | Backend | [contracts](collections/contracts.md) |
| `complaint_templates/{country}/types/{type}` | violation type | Complaint letter structure and authority per country | Contract Shield | Data script | [contracts](collections/contracts.md) |
| `users/{uid}/transfers/{id}` | auto | A remittance the user logged | Remittance + FIB | Backend (NF-P2-017) | [fib](collections/fib.md) |
| `users/{uid}/income/{id}` | auto | An income entry | FIB | Backend (NF-P3-010) | [fib](collections/fib.md) |
| `users/{uid}/bills/{id}` | auto | A bill paid | FIB | Backend (NF-P3-010, -011) | [fib](collections/fib.md) |
| `users/{uid}/savings/{id}` | auto | A savings entry. **Added: missing from the design table.** | FIB | Backend (NF-P3-010) | [fib](collections/fib.md) |
| `users/{uid}/financial_profile/current` | `current` | Computed financial identity | FIB | Backend, weekly (NF-P3-013) | [fib](collections/fib.md) |
| `corridors/{corridorId}` | `SG-PH` style | RPW provider prices for one corridor | Remittance | Data script (NF-P1-016) | [corridors](collections/corridors.md) |
| `rates_cache/{pair}` | `SGD_PHP` style | Latest live FX rate | Remittance | Cron (NF-P1-019) | [rates_cache](collections/rates_cache.md) |
| `rates_history/{pair}` and `.../points/{pointId}` | pair; hour | FX rate history: the daily series on the header (trends, savings), hourly cron points below | Remittance | Cron, backfill (header only) | [rates_cache](collections/rates_cache.md) |
| `labor_laws/{country}` | ISO-2 country | Country header | Contract Shield | Data script (NF-P1-018) | [labor_laws](collections/labor_laws.md) |
| `labor_laws/{country}/_meta/current` | `current` | Version for cache invalidation | Contract Shield | Data script (NF-P1-018) | [labor_laws](collections/labor_laws.md) |
| `labor_laws/{country}/rules/{category}` | one of 15 category ids | One curated legal rule | Contract Shield | Data script (NF-P1-018) | [labor_laws](collections/labor_laws.md) |
| `radar_reports/{id}` | auto | One community report | Radar | Backend (NF-P3-001) | [radar](collections/radar.md) |
| `report_embeddings/{id}` | same id as the report | Vector for similarity search | Radar | Backend (NF-P3-002) | [radar](collections/radar.md) |
| `radar_entities/{slug}` | slugified name | Aggregated risk profile of one operator, agency or employer | Radar | Backend (NF-P3-003) | [radar](collections/radar.md) |
| `radar_alerts/{corridor}` and `.../current/{alertId}` | auto | Active alerts per corridor | Radar | Cron (NF-P3-004) | [radar](collections/radar.md) |
| `users/{uid}/coach_sessions/{sessionId}` | auto | One Financial Coach interview: stage, slots, transcript. *Future Scope* | Coach | Backend (NF-FC-008) | [coach](collections/coach.md) |
| `users/{uid}/coach_plans/{planId}` | first 20 hex of the slot hash | Preparedness score and 90-day plan in English, check-in markers. *Future Scope* | Coach | Backend (NF-FC-012) | [coach](collections/coach.md) |
| `users/{uid}/coach_plans/{planId}/translations/{language}` | language code | The plan in one other language. *Future Scope* | Coach | Backend (NF-FC-014) | [coach](collections/coach.md) |
| `users/{uid}/scam_checks/{checkId}` | auto | One analysed message: redacted text, verdict, indicators, explainer. *Future Scope* | Scam Analyzer | Backend (NF-SA-012) | [scam](collections/scam.md) |
| `scam_taxonomy/{id}` and `scam_taxonomy/_meta` | slug; `_meta` | Scam types and manipulation tactics; taxonomy version. *Future Scope* | Scam Analyzer | Data script (NF-SA-001) | [scam](collections/scam.md) |
| `scam_patterns/{id}` | `<type>-<lang>-<nnn>` | Canonical scam templates with 768-number vectors. *Future Scope* | Scam Analyzer | Data script (NF-SA-006) | [scam](collections/scam.md) |
| `scam_indicators/{id}` | first 32 hex of the indicator key | How often one phone number, address or account was reported, for "reported N times". *Future Scope* | Scam Analyzer | Backend (NF-SA-013) | [scam](collections/scam.md) |
| `scam_stats/{corridor}` and `.../weeks/{isoWeek}` | corridor id or `none`; ISO week such as `2026-W45` | Weekly counts of the Scam Analyzer's checks per corridor, counts only. *Future Scope* | Scam Analyzer | Cron job `scam-stats` through the backend (NF-SA-022) | [scam](collections/scam.md) |
| `cost_baselines/{host}` | ISO-2 host country | Monthly cost-of-living figures for the Coach. *Future Scope* | Coach | Data script (NF-FC-003 to -005) | [cost_baselines](collections/cost_baselines.md) |
| `gemini_usage/{day}` | `YYYY-MM-DD` (US Pacific) | Gemini requests sent today per feature and model tier, and the tiers Google has run dry; the daily budget reads it. *NF-HR-010* | All | Backend | [gemini_usage](collections/gemini_usage.md) |
| `config/feature_flags` | `feature_flags` | Flags `coach` and `scam`: global value and uid allow-list. *Future Scope* | Both | Operator | [config](collections/config.md) |

## Differences from the original design table

The original design lists some paths that Firestore cannot hold and misses one collection. These are the changes, all marked [P]:

| Original design | Problem | Used here |
|---|---|---|
| `users/{uid}/financial_profile` | Three segments make a collection, not a document | `users/{uid}/financial_profile/current` |
| `labor_laws/{country}/_meta` | Same | `labor_laws/{country}/_meta/current` |
| `radar_alerts/{corridor}/current` | Same | `radar_alerts/{corridor}/current/{alertId}` |
| `complaint_templates/{country}/{type}` | A variable in the collection position | `complaint_templates/{country}/types/{type}` |
| `rates_history/{pair}/points` | Same as the first row | `rates_history/{pair}/points/{pointId}` |
| (missing) | NF-P3-010 needs `POST /fib/savings` | `users/{uid}/savings/{id}` |

Future Scope paths are not in the original design (it lists the 17 collections of v1.0). They follow its naming: plural snake_case collections, `users/{uid}/...` for anything one worker owns, natural keys for reference data. `config/feature_flags` and `scam_taxonomy/_meta` are single documents named by a fixed id, like `financial_profile/current`.

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
| `users/{uid}/contracts/{id}/extraction` | None: no rule names it, so even the owner is refused (a rules test checks this); the owner sees the same text in each report | None | None |
| `users/{uid}/transfers`, `income`, `bills`, `savings` | Read | None | None |
| `users/{uid}/financial_profile` | Read | None | None |
| `corridors`, `rates_cache`, `rates_history`, `labor_laws` (all subcollections), `complaint_templates` | Read (reference data) | Read | None |
| `radar_entities`, `radar_alerts` | Read (aggregated, no personal data) | Read | None |
| `radar_reports`, `report_embeddings` | None (the backend serves reports through the API and hides `reporter_hash`) | None | None |
| `users/{uid}/coach_sessions`, `coach_plans` and its `translations`, `scam_checks` (*Future Scope*) | Read; **no client write**, every change goes through the API | None | None |
| `scam_taxonomy`, `cost_baselines` (*Future Scope*) | Read (reference data) | Read | None |
| `scam_patterns`, `scam_indicators`, `scam_stats`, `config` (*Future Scope*) | None | None | None |
| `gemini_usage` (*NF-HR-010*) | None | None | None |

Future Scope adds one client-writable field: `users/{uid}.signal_sharing` (a map of two booleans, set from the profile page), which the rules accept alongside the other profile fields (`signal_sharing` may hold only the keys `coach` and `scam`, each a boolean; NF-F0-004). The rules for every collection above are in `frontend/firestore.rules` with an allow and a deny test each. A worker cannot delete a scam check or a Coach session from the browser: that stays an API matter (D-109).

Entries created by the user (transfers, income, bills, savings) are written by the backend so the values can be validated and categorized. If a task needs the browser to write directly, that task must add the matching rule.

## Required indexes

Single-field indexes are automatic. These two composite indexes are the only ones a query needs; they are listed in `frontend/firestore.indexes.json` (2026-10-01).

| Collection | Fields | Used by |
|---|---|---|
| `radar_reports` | `entity_slug` asc, `created_at` desc | Entity profile page (NF-P3-008, `RadarRepository.list_by_entity`) |
| `report_embeddings` | `corridor_id` asc, `embedding` vector (dimension 768, flat) | Similar-report search (NF-P3-002, `find_similar`) |

Not needed, although earlier versions of this page listed them (2026-10-01 bug fix):
- `radar_reports` `corridor_id` + `created_at`: the alert job (NF-P3-004) now reads two weeks of reports with one `created_at` range, which the automatic index serves. Its old per-corridor query needed `created_at` **ascending**; this page said descending, so the index created from it never matched and the job failed on every corridor.
- `radar_entities` `corridors` + `report_count`, and `notifications` `read` + `created_at`: no query uses them. The heatmap reads every entity; the alert feed sorts by `created_at` alone.

Existing copies of these three in a project do no harm.

### Added by Future Scope (NF-F0-003; written into `frontend/firestore.indexes.json` by NF-F0-004)

Three more indexes are needed:

| Index | Used by | Why it is not automatic |
|---|---|---|
| `scam_patterns`: vector, dimension 768, flat, on `embedding` | The nearest-3 search of NF-SA-010 | Vector fields are never indexed by default |
| `coach_plans`: single field `departure_date`, ascending, **collection-group scope** | The daily check-in job (NF-FC-016) finds plans reaching day 30, 60 and 90 across all users: a range on `departure_date` on the group `coach_plans` (the day itself and the 3 days before it, so a run that was missed delays a reminder instead of losing it) | Single-field indexes are created for one collection at a time; a query over a collection group needs the group scope on purpose |
| `scam_checks`: single field `created_at`, **collection-group scope** added (ascending), with the collection-scope ascending and descending ones kept (NF-SA-022) | The weekly stats job counts the checks of two ISO weeks across all workers: a range on `created_at` on the group `scam_checks` | Same reason as `coach_plans`; the history screen's `order by created_at desc` for one worker needs the collection-scope descending one, which an exemption must therefore keep |

Every other query the new collections need is served by automatic indexes, so no later task has to add one by hand: the active session (`status ==` in one user's `coach_sessions`), newest plans and newest checks (`order by created_at desc`, one user), a cached verdict (`cache_key ==` in one user's `scam_checks`), the taxonomy (`kind in [...]`), a flag read (one document), an indicator's count (a read by id) and the most reported indicators (`order by report_count desc`, one field). All three are entries in `frontend/firestore.indexes.json` (`indexes` for the vector index, `fieldOverrides` for the group-scope fields), and `frontend/firebase.json` points at that file, so `firebase deploy --only firestore:indexes` would create them. **No workflow runs that command** (`firestore-rules-deploy.yml` deploys `firestore:rules,storage` only, D-33, D-68), so the file is the record and the project was set up by hand; the file inside `frontend/` is the only one the CLI reads (the empty copy in `infra/firebase/` was removed in NF-HR-013).

The vector index as a `gcloud` command (syntax from `--help` on 2026-10-06; not run):

```bash
gcloud firestore indexes composite create --project nomadfinance-prod \
  --collection-group=scam_patterns --query-scope=COLLECTION \
  --field-config=field-path=embedding,vector-config='{"dimension":768,"flat":{}}'
```

The vector index of `report_embeddings` as a `gcloud` command (check `gcloud firestore indexes composite create --help` for the current syntax):

```bash
gcloud firestore indexes composite create --project nomadfinance-prod \
  --collection-group=report_embeddings --query-scope=COLLECTION \
  --field-config=field-path=corridor_id,order=ascending \
  --field-config=field-path=embedding,vector-config='{"dimension":768,"flat":{}}'
```

**The group-scope indexes (`coach_plans.departure_date`, `scam_checks.created_at`) cannot be made with `gcloud`.** `gcloud firestore indexes fields update` accepts only `order` and `array-config` in `--index`, with no way to say "collection group", so an earlier version of this page that showed such a command was wrong (corrected in NF-F0-006). Two ways that do work:

1. **From the file (preferred):** `firebase deploy --only firestore:indexes --project <project-id>` creates the `fieldOverrides` entry above. The CLI lists any index that exists in the project but not in the file and **offers to delete it: decline** (production has three unused ones, D-69), and never add `--force`.
2. **In the console:** Firestore, Indexes, Single field, Add exemption: collection ID `coach_plans`, field path `departure_date`, then add an Ascending index with **Collection group** scope as well as the Collection one (an exemption replaces the defaults, so keep both).

In production these exemptions were made by hand in the console (D-114, D-164). The deploy path from the file has never been run.

### What production holds (read with `gcloud` on 2026-10-11, NF-HR-013)

`gcloud firestore indexes composite list`, `gcloud firestore indexes fields list` and `gcloud firestore fields ttls list`, project `nomadfinance-prod`, database `(default)`. Every index is `READY`.

| Kind | Collection | Fields | In the file? | Used? |
|---|---|---|---|---|
| Composite | `radar_reports` | `entity_slug` asc, `created_at` desc | yes | yes |
| Vector | `report_embeddings` | `corridor_id` asc, `embedding` (768, flat) | yes | yes |
| Vector | `scam_patterns` | `embedding` (768, flat) | yes | yes |
| Single-field exemption | `coach_plans` | `departure_date` asc, collection and collection-group scope | yes | yes |
| Single-field exemption | `scam_checks` | `created_at` asc and desc at collection scope, asc at collection-group scope | yes | yes |
| Composite | `radar_reports` | `corridor_id` asc, `created_at` desc | no | no (D-69) |
| Composite | `radar_entities` | `corridors` asc, `report_count` desc | no | no (D-69) |
| Composite | `notifications` | `read` asc, `created_at` desc | no | no (D-69) |

So production has every index the file lists, plus the three unused ones the page above says to leave alone. Deploying the file would offer to delete those three: decline.

## Time to live

Three collection groups delete their own documents. A TTL policy is a setting on the field, not code and not an index, so it needs a person with project access, once per project.

| Collection group | TTL field | Value of the field | Why this long |
|---|---|---|---|
| `coach_sessions` | `expires_at` | `last_active` + 30 days, moved on every turn | The plan keeps a copy of the slots; the session is only for resuming and looking back |
| `scam_checks` | `expires_at` | `last_checked_at` + 90 days | Enough for "did I see this before"; the stored text and the scam's phone numbers and addresses should not live longer |
| `scam_indicators` | `expires_at` | `last_reported_at` + 365 days | Phone numbers are reissued; one nobody has reported for a year stops being flagged |

`coach_plans`, `scam_taxonomy`, `scam_patterns`, `cost_baselines` and `config` have no TTL (the reports in `radar_reports` have none either, see D-110): plans are kept until the worker deletes the account (the account deletion removes them), and the rest is reference data.

```bash
gcloud firestore fields ttls update expires_at --project nomadfinance-prod \
  --collection-group=coach_sessions --enable-ttl --async
gcloud firestore fields ttls update expires_at --project nomadfinance-prod \
  --collection-group=scam_checks --enable-ttl --async
gcloud firestore fields ttls update expires_at --project nomadfinance-prod \
  --collection-group=scam_indicators --enable-ttl --async
```

Things to know: deletion is not instant, it usually happens within a day of the time in the field and can take longer, so code must not rely on a document being gone at `expires_at` (a read after expiry may still succeed, and the backend should treat `expires_at < now` as absent). A TTL policy applies to the whole collection group, so it covers every user at once. It does not delete subcollections of a document it removes; neither collection has any. If `expires_at` is missing or is not a timestamp, the document never expires, so the backend always writes it.

**State in production (read with `gcloud firestore fields ttls list` on 2026-10-11):** the three policies, on `expires_at` of `coach_sessions`, `scam_checks` and `scam_indicators`, are `ACTIVE` (D-103). There is no staging project to repeat them in (D-121). The commands above stay as the record for creating them again in a new project.

## Cloud Storage paths (not Firestore, referenced by it) [P]

`storage.rules` is a separate shared file owned by NF-P1-014. Bucket: `nomadfinance-prod.firebasestorage.app`. The table lists what the backend writes (`app/integrations/cloud_storage.py`, `app/services/coach/plan_files.py`); NF-HR-013 checked it against the code.

| Path | Holds | Referenced by |
|---|---|---|
| `bills/{uid}/{billId}/bill.{extension}` | Bill or payslip photo, kept when a photo is scanned (NF-P3-011) | `users/{uid}/bills/{id}.image_path` |
| `radar-evidence/{reportId}/{filename}` | Optional report attachment | `radar_reports/{id}.evidence_paths` |
| `exports/{uid}/financial-identity-{yyyymmddThhmmssZ}.pdf` | Exported Financial Identity PDF | `financial_profile/current.latest_export` |
| `exports/{uid}/coach-plan-{planId}-{language}.pdf` | Coach plan PDF (*Future Scope*), under `exports/` so account deletion already covers it | `coach_plans/{id}.pdf.{language}.storage_path` |

**Not written: `contracts/{uid}/...`.** An earlier version of this page listed an uploaded contract file there. The backend reads the file in memory, keeps only the text blocks (`users/{uid}/contracts/{id}/extraction/current`) and never stores the file, so `contracts/{id}.storage_path` stays empty (see [contracts](collections/contracts.md)). `storage.rules` still lets an owner read a `contracts/` folder and account deletion still clears it; both are harmless and stay as a safeguard if a later task keeps the file.

## How the pillars share data

```
Remittance X-Ray ──log transfer──────────► users/{uid}/transfers ──► Financial Identity
Contract Shield ──anonymised signal──────► radar_reports  (source: contract_signal)
Contract Shield ──verified employment────► users/{uid}/income      (source: contract)
Radar ──flagged entity────────────────────► shown in Remittance (provider slug) and Contract Shield (employer or agency slug)
```

Future Scope adds:

```
Coach ──goals──────────────────────────────► users/{uid}/financial_profile/current.goals
Coach, Scam ──counts only, opt-in──────────► financial_profile (coach_signal, scam_signal)
Scam Analyzer ──worker-confirmed scam report► radar_reports  (source: scam_check)
Scam Analyzer ──same transaction───────────► scam_indicators (counts per number or address)
Contract Shield ──salary, employer, confirmed► coach session slots (source: contract_prefill)
```

The join key for the two "shown in" links is the entity `slug` (a slugified name), see [radar](collections/radar.md).

## Questions the team still needs to settle

| # | Question | Default used here | Decide before |
|---|---|---|---|
| 1 | Are the 15 labor-law categories in [labor_laws](collections/labor_laws.md) right? | The list in that file | NF-P1-017 (curation) |
| 2 | Push notifications: store FCM tokens per user, or use FCM topics per corridor? | Tokens in `users/{uid}.fcm_tokens` | NF-P3-004 |
| 3 | Contract text is stored in Firestore in the report documents. Is that acceptable for real users? | Yes for the prototype with demo data (ADR-002: free-tier Gemini content may be used by Google); real data needs the paid tier and a retention rule | Public demo |
| 4 | Should signed-in users read `radar_reports` directly? | No, the backend serves them | NF-P1-014 |
| 5 | *Future Scope.* Scam cache per user or shared? | Per user (`cache_key` on `scam_checks`); a shared cache would need a new collection and a retention rule | Decided in NF-F0-003; NF-SA-012 may revisit |
| 6 | *Future Scope.* How does a scam report look in Radar? | `source: scam_check`, `entity_type: scam_type`, `violation_type: scam_message`, with the full scam details and the worker-confirmed indicators in `scam` (see [radar](collections/radar.md)) | Decided in NF-F0-003 |
| 7 | *Future Scope.* Can a worker delete their own scam checks or a Coach session before the TTL? | No: the rules deny every browser write and delete on these collections. NF-SA-012 may add a delete route to the API (D-109) | NF-SA-012 |
