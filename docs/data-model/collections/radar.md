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
| `entity_type` | string | yes | `money_transfer_operator`, `recruitment_agency`, `employer`, and `scam_type` (scam reports, Future Scope: the entity is the kind of scam, see below) |
| `entity_name` | string | yes | Name as written in the report, cleaned up |
| `entity_slug` | string | yes | Slug of the name; the id of the matching `radar_entities` document |
| `violation_type` | string | yes | `hidden_fees`, `exchange_rate_markup`, `illegal_recruitment_fee`, `wage_theft`, `illegal_deduction`, `contract_substitution`, `passport_retention`, `unlicensed_operator`, `other`, and `scam_message` (scam reports) |
| `corridor_id` | string | no | For operators and agencies, for example `SG-PH` |
| `host_country` | string | no | For employers, and for heatmap grouping. At least one of `corridor_id` and `host_country` is required. |
| `description` | string | yes | What happened, in the reporter's words |
| `language` | string | yes | Language of `description` |
| `cluster_id` | string | yes | Id of the first report in its similarity cluster. Equal to its own id when it starts a new cluster. Counts unique incidents. |
| `source` | string | yes | `user`, `contract_signal` (Contract Shield, NF-P2-021), `seed` (demo data, NF-P3-005) or `scam_check` (a Scam Analyzer check the worker chose to share, NF-SA-013) |
| `reporter_hash` | string | for `user` | HMAC-SHA-256 of the reporter's uid with a secret kept in Secret Manager. **Never the uid.** Absent for `contract_signal`, `seed` and `scam_check`. Used to limit repeat reports and abuse. |
| `evidence_paths` | array of string | no | Cloud Storage paths of optional attachments (`radar-evidence/{id}/`), added after the report itself via `POST /radar/report/{report_id}/evidence` (NF-P3-004). At most 5. |
| `validation` | map | yes | `{ "spam_score": number, "category_confidence": number, "model": string }` from the classification tier. For `contract_signal` there is no free text to check and no model call: fixed values that say so (`spam_score: 0`, `category_confidence: 1`, `model: "contract_shield"`), never invented Gemini output |
| `summary` | string | for `user` | One neutral English sentence from step 4's classification (NF-P3-001). Absent for `contract_signal` and `seed` (no free text to summarize). Not what NF-P3-004's alert cron shows — that's a separate, alert-level summary generated from facts aggregated across multiple reports, never this per-report one |
| `scam` | map | for `scam_check` | The details of the scam. See "Scam reports" below. Absent on every other source. |
| `hidden` | boolean | no | **Future Scope.** An operator sets `true` to take a report out of every list and count, for example after a complaint that a legitimate person was named (D-107). Absent means visible. The API leaves a hidden report out and the aggregation job does not count it. Any source may use it. |
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
  "summary": "Operator showed one rate and charged a worse one at the counter.",
  "created_at": "2026-09-27T05:41:00Z",
  "schema_version": 1
}
```

Values and the entity name are illustrative. Real demo data is created by NF-P3-005.

**Access:** no client access. The backend returns reports through the API and leaves out `reporter_hash`.

### Scam reports (Future Scope, NF-F0-003)

A worker who has checked a message in the Scam Analyzer and the analyzer found a scam can share it (one tap, behind a confirmation sheet, NF-SA-013). The report carries **the full picture of the scam, so other workers can recognise it**, and nothing that says who sent it in: no uid, no reporter hash, no raw message, no screenshot. A report can be made only from a check the analyzer itself marked as a scam, and only once per check (`scam_checks.reported_report_id`).

How the common fields are filled:

| Field | Value |
|---|---|
| `source` | `scam_check` |
| `entity_type`, `entity_name`, `entity_slug` | `scam_type`; the taxonomy `label` (for example `Illegal recruitment fee`); `scam-` plus the type id with hyphens (`scam-illegal-recruitment-fee`). So the Radar profile page is "this kind of scam", and it lists every report of it with its details. The slug cannot clash with a provider or an employer: those slugs never start with `scam-` unless a business is called that. |
| `violation_type` | `scam_message` |
| `corridor_id`, `host_country` | The check's `corridor_id` if it has one; `host_country` from the worker's profile (a country, not an identity), else the corridor's host country. A check with neither is still reported: the alert job and the heatmap, which group by corridor or country, skip it |
| `description` | The redacted message text **as the worker confirmed it** (they can edit it in the confirmation sheet; at most 1,000 characters). This is also the text that is embedded for similarity. |
| `language` | `scam.message_language`, or the worker's language when that is `other` |
| `validation` | `{ "spam_score": 0, "category_confidence": <the verdict's confidence>, "model": <the classifier model id> }`. There is no spam check, because the analyzer already classified the message; the confidence and model are the analyzer's real values, not invented ones. |
| `summary` | Absent (no free text to summarise) |
| `reporter_hash` | Absent, on purpose: nothing that links a report to a worker is kept. Abuse is limited instead by the analyzer's rate limit and by the rule that only a check marked as a scam can be reported. |

The `scam` map:

| Key | Description |
|---|---|
| `scam_type` | Taxonomy `type` id |
| `tactics` | Taxonomy `tactic` ids |
| `risk_level`, `confidence` | From the check's verdict |
| `trigger_phrases` | From the verdict (substrings of the redacted text) |
| `details` | Same keys as `scam_checks.details`: `claimed_identity`, `contact_channel`, `payment_requested`, `amount_requested`, `deadline_stated`. Only the ones the check has. |
| `indicators` | Array of `{ "kind", "value", "flags", "imitates" }` (same as in `scam_checks`, without `id`). **Only the indicators the worker left ticked** in the confirmation sheet: a phone number or an address in the message may be the worker's own. Creating the report also adds one to the counters of each of these in `scam_indicators` (see [scam](scam.md)), in the same transaction, which is what lets a later check say "this number was reported N times". |
| `message_language`, `input_type` | `en`...`bn` or `other`; `text` or `screenshot` |

**What the confirmation sheet must show** (NF-SA-018): exactly what will be public to other workers: the type, the text (editable), each indicator with a tick, and a line that the report is anonymous and unverified. Nothing that is not on the sheet is sent. The text is redacted for phone numbers, emails, IDs, accounts and URLs but **not for personal names**, so the sheet is also where the worker removes a name that appears in the message (D-108).

**Example** — `radar_reports/r_02` (scam report)

```json
{
  "entity_type": "scam_type",
  "entity_name": "Illegal recruitment fee",
  "entity_slug": "scam-illegal-recruitment-fee",
  "violation_type": "scam_message",
  "corridor_id": "SG-IN",
  "host_country": "SG",
  "description": "Congratulations! You are selected for a caregiver job in Singapore. Pay 800 SGD processing fee to [ACCOUNT] today or the visa slot is cancelled. WhatsApp [PHONE] or apply at [URL].",
  "language": "en",
  "cluster_id": "r_02",
  "source": "scam_check",
  "validation": { "spam_score": 0, "category_confidence": 0.94, "model": "gemini-3.1-flash-lite" },
  "scam": {
    "scam_type": "illegal_recruitment_fee",
    "tactics": ["urgency", "scarcity"],
    "risk_level": "high",
    "confidence": 0.94,
    "trigger_phrases": ["processing fee", "visa slot is cancelled"],
    "details": { "contact_channel": "whatsapp", "payment_requested": "bank transfer", "deadline_stated": true },
    "indicators": [
      { "kind": "phone", "value": "6590000001", "flags": [] },
      { "kind": "url", "value": "sg-careers-visa.example", "flags": ["lookalike"], "imitates": "mom.gov.sg" }
    ],
    "message_language": "en",
    "input_type": "text"
  },
  "created_at": "2026-11-02T10:20:00Z",
  "schema_version": 1
}
```

**Code that reads `radar_reports` must tolerate these values** (adding values and an optional map needs no `schema_version` bump, see `versioning.md`): the entity page and its report list (labels for the new `entity_type` and `violation_type`, and a layout for `scam`), the alert job (counts reports by corridor and violation type; a scam type can raise a surge alert like any entity), the aggregation (`radar_entities` for a `scam-...` slug works as for any entity and is `flagged` at 2 incidents), and the cross-pillar badges (they look up provider and employer slugs and never meet a `scam-` slug). The API that serves reports must keep leaving out `reporter_hash` and must return `scam` for these reports.

**Known risk, for the walkthrough.** A scam report names phone numbers and addresses that other people will see, from one unverified worker. A wrongly flagged number could harm a legitimate person. What limits it: the worker confirms each indicator, the analyzer must have judged the message a scam, the page labels such reports "reported by a worker, not verified", and the profile is "flagged" only at 2 or more incidents. A report can be hidden by an operator (`hidden`), and so can an indicator (`scam_indicators.hidden`); who reviews complaints and how fast is a process decision for NF-HR-008 (security review), D-107. Indicators also stop being flagged a year after their last report (`scam_indicators.expires_at`), because phone numbers are reissued; the values inside old reports are not removed (D-110).

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
| `community_rating` | number or null | yes | 0 to 5, higher is safer. `null` below 2 incidents (not enough signal for a number); otherwise `max(0, 5 − 0.5 × incident_count)`, rounded to 1 decimal (NF-P3-003, `services/radar/aggregation.py`) |
| `risk_level` | string | yes | `low` below 2 incidents, `medium` at 2 to 4, `high` at 5 or more (NF-P3-003) |
| `flagged` | boolean | yes | `true` at 2 or more incidents — a pattern, not a single unverified report; drives the "Community flagged" badges (NF-P3-022, NF-P3-023) |
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
  "community_rating": 4.0,
  "risk_level": "medium",
  "flagged": true,
  "updated_at": "2026-09-27T05:41:02Z",
  "schema_version": 1
}
```

**Access:** signed-in users read (no personal data here); only the backend writes.

## `radar_alerts/{corridor}` and `radar_alerts/{corridor}/current/{alertId}`

The header document is `{ "corridor_id": "SG-IN", "active_count": 1, "updated_at": ... }`. It is what a corridor list reads to show a badge without loading the alerts.

Each alert is language-neutral. The text a user sees is written into their own `notifications` document (see [users](users.md)), in their language, once, when the alert is created. The Alerts page also reads the active alerts of the worker's routes directly (signed-in users may read `radar_alerts`), so a worker who joins or picks a route later still sees them.

**What counts on a corridor** (alert job, NF-P3-004, changed 2026-10-01): a report with a `corridor_id` counts on that route; a report with only a `host_country` (an employer, or a Contract Shield signal) counts on every corridor from that country, for example an SG employer on SG-PH and SG-IN.

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

NF-P3-001 (submit), NF-P3-002 (embeddings and clustering), NF-P3-003 (entity aggregation), NF-P3-004 (alert cron), NF-P3-005 (demo seed), NF-P3-007 to NF-P3-009 (UI), NF-P3-025 (App Check on submit), NF-P2-021 (contract signal), NF-P3-022 and NF-P3-023 (badges); from Future Scope NF-SA-010 (similar scams), NF-SA-013 (report from a scam check), NF-SA-018 (confirmation sheet).
