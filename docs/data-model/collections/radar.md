# radar

Shape sources: the four paths are **[D]** (`current` needs a document id, see `firestore-schema.md`). The report pipeline and cron are in the design doc's Exploitation Radar diagram and NF-P3-001 to NF-P3-009 **[T]**. Field names, enums and the anonymity rules are **[P]**. The embedding model and size follow ADR-002 and the Firestore vector limit **[built decision]**.

```
radar_reports/{id}                         one community report (backend only)
report_embeddings/{id}                     vector of that report, same id (backend only)
radar_entities/{slug}                      aggregated profile of an operator, agency or employer
radar_alerts/{corridor}                    header
radar_alerts/{corridor}/current/{alertId}  an alert on a corridor
```

## `radar_reports/{id}`

A worker's own report (`source: "user"`) is written only after it passes validation (spam and duplicate checks, NF-P3-001); rejected spam is answered with an error and **not stored**. A `contract_signal` report (NF-P2-021) is written directly: the category is already a checked fact from Contract Shield's own comparison step, not free text that needs checking.

| Field | Type | Required | Description |
|---|---|---|---|
| `entity_type` | string | yes | `money_transfer_operator`, `recruitment_agency`, `employer` |
| `entity_name` | string | yes | Name as written in the report, cleaned up |
| `entity_slug` | string | yes | Slug of the name; the id of the matching `radar_entities` document |
| `violation_type` | string | yes | `hidden_fees`, `exchange_rate_markup`, `illegal_recruitment_fee`, `wage_theft`, `illegal_deduction`, `contract_substitution`, `passport_retention`, `unlicensed_operator`, `other` |
| `corridor_id` | string | no | For operators and agencies, for example `SG-PH` |
| `host_country` | string | no | For employers, and for heatmap grouping. At least one of `corridor_id` and `host_country` is required. |
| `description` | string | yes | What happened, in the reporter's words |
| `language` | string | yes | Language of `description` |
| `cluster_id` | string | yes | Id of the first report in its similarity cluster. Equal to its own id when it starts a new cluster. Counts unique incidents. |
| `source` | string | yes | `user`, `contract_signal` (Contract Shield, NF-P2-021) or `seed` (demo data, NF-P3-005) |
| `reporter_hash` | string | for `user` | HMAC-SHA-256 of the reporter's uid with a secret kept in Secret Manager. **Never the uid.** Absent for `contract_signal` and `seed`. Used to limit repeat reports and abuse. |
| `evidence_paths` | array of string | no | Cloud Storage paths of optional attachments |
| `validation` | map | yes | `{ "spam_score": number, "category_confidence": number, "model": string }` from the classification tier. For `contract_signal` there is no free text to check and no model call: fixed values that say so (`spam_score: 0`, `category_confidence: 1`, `model: "contract_shield"`), never invented Gemini output |
| `created_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

**Example** — `radar_reports/r_01`

```json
{
  "entity_type": "money_transfer_operator",
  "entity_name": "Example Remit",
  "entity_slug": "example-remit",
  "violation_type": "hidden_fees",
  "corridor_id": "SG-IN",
  "description": "They showed one rate and gave me a worse one at the counter.",
  "language": "en",
  "cluster_id": "r_01",
  "source": "user",
  "reporter_hash": "3b5d5c3712955042212316173ccf37be3b5d5c3712955042212316173ccf37be",
  "validation": { "spam_score": 0.02, "category_confidence": 0.91, "model": "gemini-3.1-flash-lite" },
  "created_at": "2026-09-27T05:41:00Z",
  "schema_version": 1
}
```

Values and the entity name are illustrative. Real demo data is created by NF-P3-005.

**Access:** no client access. The backend returns reports through the API and leaves out `reporter_hash`.

## `report_embeddings/{id}`

The vector of a report's description, used to find similar reports (Firestore vector search, NF-P3-002). The id equals the report id.

| Field | Type | Required | Description |
|---|---|---|---|
| `embedding` | vector | yes | **768 numbers**, see below |
| `embedding_model` | string | yes | `gemini-embedding-001` |
| `dimension` | number | yes | `768` |
| `corridor_id` | string | no | Copy from the report, for filtered search |
| `entity_type` | string | yes | Copy from the report |
| `entity_slug` | string | yes | Copy from the report |
| `created_at` | timestamp | yes | |

**Why 768 and `gemini-embedding-001`.** The design doc names `text-embedding-004`, which Google shut down on 2026-01-14. ADR-002 chose `gemini-embedding-001`. That model returns 3072 numbers by default, but Firestore allows at most 2048 per vector, so the request must ask for a smaller size (768 is one of Google's recommended sizes). Vectors shortened this way are not unit length, so **normalize each vector before storing it**. Use the same model and size for every vector: a search only compares vectors of one size.

The vector is written with the SDK's `Vector` type, not as a plain array. The index for it is in the table in `firestore-schema.md`.

**Example** — `report_embeddings/r_01` (the vector is shortened here; the real one has 768 numbers)

```json
{
  "embedding": "Vector of 768 normalized numbers",
  "embedding_model": "gemini-embedding-001",
  "dimension": 768,
  "corridor_id": "SG-IN",
  "entity_type": "money_transfer_operator",
  "entity_slug": "example-remit",
  "created_at": "2026-09-27T05:41:01Z"
}
```

**Access:** no client access; backend only.

## `radar_entities/{slug}`

The running profile of one operator, agency or employer. The id is the slug of the name (lowercase words joined with hyphens, for example `western-union`), made with `python-slugify`.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Display name |
| `slug` | string | yes | Same as the document id |
| `entity_type` | string | yes | Same values as on the report |
| `aliases` | array of string | no | Other spellings that were merged in |
| `corridors` | array of string | no | Corridors with reports |
| `host_countries` | array of string | no | Countries with reports |
| `report_count` | number | yes | Reports in this profile |
| `incident_count` | number | yes | Distinct clusters (unique incidents) |
| `violation_counts` | map | yes | Reports per `violation_type` |
| `first_reported_at`, `last_reported_at` | timestamp | yes | |
| `community_rating` | number or null | yes | 0 to 5, higher is safer. `null` until there are enough reports. The formula belongs to NF-P3-003. |
| `risk_level` | string | yes | `low`, `medium`, `high` |
| `flagged` | boolean | yes | `true` when the entity crosses the warning threshold; drives the "Community flagged" badges (NF-P3-022, NF-P3-023) |
| `updated_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

**The slug is the join key for the cross-pillar badges.** To warn about a provider, or an employer named in a contract, the app slugifies that name and looks the slug up here. Two consequences: businesses with the same name merge into one profile, and small spelling differences (for example RPW writes `PNB (Philippines National Bank)`) miss unless the alias is added. That is acceptable for the prototype; `aliases` is the place to fix a miss.

**Example** — `radar_entities/example-remit`

```json
{
  "name": "Example Remit",
  "slug": "example-remit",
  "entity_type": "money_transfer_operator",
  "aliases": [],
  "corridors": ["SG-IN"],
  "host_countries": ["SG"],
  "report_count": 3,
  "incident_count": 2,
  "violation_counts": { "hidden_fees": 3 },
  "first_reported_at": "2026-09-20T09:00:00Z",
  "last_reported_at": "2026-09-27T05:41:00Z",
  "community_rating": 2.5,
  "risk_level": "medium",
  "flagged": true,
  "updated_at": "2026-09-27T05:41:02Z",
  "schema_version": 1
}
```

**Access:** signed-in users read (no personal data here); only the backend writes.

## `radar_alerts/{corridor}` and `radar_alerts/{corridor}/current/{alertId}`

The header document is `{ "corridor_id": "SG-IN", "active_count": 1, "updated_at": ... }`. It is what a corridor list reads to show a badge without loading the alerts.

Each alert is language-neutral. The text a user sees is written into their own `notifications` document (see [users](users.md)), in their language.

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | yes | `report_surge` |
| `corridor_id` | string | yes | Same as the parent |
| `entity_slug`, `entity_name` | string | yes | Who the alert is about |
| `violation_type` | string | yes | Most reported type in the window |
| `window_days` | number | yes | Look-back period, for example 7 |
| `report_count` | number | yes | Reports in the window |
| `baseline_count` | number | yes | Reports in the previous window of the same length |
| `severity` | string | yes | `info`, `warning`, `critical` |
| `status` | string | yes | `active`, `expired` |
| `created_at` | timestamp | yes | |
| `expires_at` | timestamp | yes | The cron marks the alert `expired` after this time. A Firestore TTL policy on this field can delete old ones. |
| `notified_at` | timestamp | no | When the FCM push went out |
| `schema_version` | number | yes | `1` |

**Example** — `radar_alerts/SG-IN/current/a_01`

```json
{
  "type": "report_surge",
  "corridor_id": "SG-IN",
  "entity_slug": "example-remit",
  "entity_name": "Example Remit",
  "violation_type": "hidden_fees",
  "window_days": 7,
  "report_count": 3,
  "baseline_count": 0,
  "severity": "warning",
  "status": "active",
  "created_at": "2026-09-27T06:00:00Z",
  "expires_at": "2026-10-04T06:00:00Z",
  "notified_at": "2026-09-27T06:00:04Z",
  "schema_version": 1
}
```

**Access:** signed-in users read; only the backend writes.

## Tasks that use it

NF-P3-001 (submit), NF-P3-002 (embeddings and clustering), NF-P3-003 (entity aggregation), NF-P3-004 (alert cron), NF-P3-005 (demo seed), NF-P3-007 to NF-P3-009 (UI), NF-P3-025 (App Check on submit), NF-P2-021 (contract signal), NF-P3-022 and NF-P3-023 (badges).
