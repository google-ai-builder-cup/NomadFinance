# scam

Scam Analyzer (Future Scope, NF-F0-003). Shape sources: paths and purpose are **[T]** (tracker NF-SA-001, -006, -007, -012, -013) and the original Future Scope design. Field names, enums, ids and TTLs are **[P]**. Taxonomy contents (NF-SA-001) and the verdict model (NF-SA-007) may refine them, and should tell the team when they change a field name here.

```
users/{uid}/scam_checks/{checkId}     one analysed message (backend writes, owner reads)
scam_taxonomy/{id}                    scam types and manipulation tactics (data script writes, signed-in users read)
scam_taxonomy/_meta                   version of the taxonomy
scam_patterns/{id}                    canonical scam templates with vectors (backend only)
scam_indicators/{id}                  how often one phone number, address or account was reported (backend only)
scam_stats/{corridor}/weeks/{isoWeek} counts of checks per corridor and ISO week (a scheduled job writes; backend only)
```

How a check reaches Radar (what is stored in `radar_reports`) is in [radar](radar.md), "Scam reports".

## `users/{uid}/scam_checks/{checkId}`

One analysed message. **The id is the first 32 hex characters of `cache_key`** (NF-SA-012), not an auto id: the same message in the same output language is found by one read, and a retried request writes the same document instead of a second one (contract: "a check is written under its hash"). The image of a screenshot is **never stored**, only the text read from it (NF-SA-008).

| Field | Type | Required | Description |
|---|---|---|---|
| `input_type` | string | yes | `text` or `screenshot` |
| `language` | string | yes | The worker's output language (`en`, `hi`, `tl`, `id`, `ne`, `bn`): the language of `explainer` |
| `message_language` | string | no | Language of the message itself: the six codes, or `other` |
| `redacted_text` | string | yes | The message with phone numbers, emails, ID and account numbers and URLs masked (`app/core/redact.py`, NF-F0-008). At most 4,000 characters. **No raw text is stored anywhere.** |
| `cache_key` | string | yes | SHA-256, 64 hex, of the normalised `redacted_text`, a newline, then `language`. A repeat of the same message in the same output language finds its check by this field (`cache_key ==`, automatic index) and, **on the same route (`corridor_id`)**, costs no Gemini call (NF-SA-012); on a different route the check is made again and replaces the stored one, because what depends on the route (the country flags, the route's report count, the explainer) would be the old route's. A hit is used only if its `prompt_versions` and `taxonomy_version` still match the code's. The cache is **per user**: a second worker's identical message is a miss (design question 3). |
| `corridor_id` | string | no | The worker's route when they checked, for "reported N times on your corridor" |
| `verdict` | map | yes | `{ "is_scam": bool, "scam_type": taxonomy id or null, "tactics": [taxonomy ids], "risk_level": "low", "medium" or "high", "confidence": 0 to 1, "trigger_phrases": [string] }`. At most 5 trigger phrases, each a substring of `redacted_text`, at most 80 characters. `scam_type` is `null` when `is_scam` is `false`. |
| `details` | map | no | What the message asks for, when it says: `{ "claimed_identity": string, "contact_channel": "sms", "whatsapp", "call", "email" or "other", "payment_requested": string, "amount_requested": { "amount", "currency" }, "deadline_stated": bool }`. Every key is optional. NF-SA-002/-007 decide which of these the classifier fills; absent means unknown. |
| `indicators` | array of map | yes | Deterministic signals found in the message (NF-SA-011): `{ "id", "kind", "value", "flags", "imitates" }`. See below. May be empty. |
| `explainer` | map | yes | For a scam: `{ "kind": "scam", "why_it_works": [ { "tactic": id, "text": string } ], "scammer_wants": string, "next_steps": [string, string, string], "language": ..., "model": ... }`. For a benign message (no reasoning-tier call): `{ "kind": "benign", "reassurance": string, "tip": string, "language": ... }`. Written at a grade-6 reading level (NF-SA-009). |
| `similar` | array of map | no | Up to 3 neighbours: `{ "source": "scam_pattern" or "radar_report", "id", "scam_type", "score" }` |
| `corridor_report_count` | number | no | How many Radar reports were found on the worker's corridor when the check ran: of the 10 reports on it whose vector is nearest to the message, those at or above the similarity cutoff, so 0 to 10. Absent when the check has no corridor or the search failed. A snapshot, not kept up to date. |
| `reported_report_id` | string | no | Id of the `radar_reports` document made from this check. **Set once**: it is what makes a second tap on "Warn other workers" return the same report (NF-SA-013). |
| `reported_at` | timestamp | no | |
| `check_count` | number | yes | `1` on creation; +1 when the same message is checked again |
| `last_checked_at` | timestamp | yes | |
| `taxonomy_version` | number | yes | `scam_taxonomy/_meta.version` used |
| `models` | map | yes | `{ "classifier": "...", "explainer": "...", "vision": "..." }`; `vision` only for a screenshot |
| `prompt_versions` | map | yes | `{ "scam.classify": 1, "scam.explain": 1 }` |
| `created_at` | timestamp | yes | |
| `expires_at` | timestamp | yes | TTL field. `last_checked_at` + 90 days |
| `schema_version` | number | yes | `1` |

### `indicators`

| Key | Description |
|---|---|
| `id` | 8 hex characters: the first 8 of the indicator's key (below). Stable, so the report flow can name which indicators the worker confirmed. The first 32 hex of the same key are the id of its `scam_indicators` document. |
| `kind` | `url`, `phone`, `email`, `handle` (a messaging or social account) or `sender` (the number or name a screenshot shows as the sender) |
| `value` | `url`: **the host only** (lowercase; no path, query or fragment, which can carry tokens and personal ids). `phone`: digits with the country code. `email`, `handle`, `sender`: as written. |
| `flags` | Array of `shortener`, `punycode`, `lookalike`, `premium_rate`, `unexpected_country`. May be empty. Set by fixed rules at check time (NF-SA-011; the rules are in `docs/api/v2-scam.md`, "How the rules read the values"). |
| `imitates` | When `flags` has `lookalike`: the real domain or brand it copies, for example `dbs.com.sg` |

**The key of an indicator** is the SHA-256 (hex) of `kind`, a colon, and the value in normal form: a phone as digits with the country code; a URL as the lowercase host without a leading `www.`; an email lowercase; a handle lowercase without a leading `@`; a sender lowercase and trimmed. The same number written two ways gives the same key. The key is not a protection (the value is stored next to it); it only makes the lookup in `scam_indicators` a direct read.

**How many times an indicator was reported is not stored on the check.** It changes, so it is read from `scam_indicators` whenever a check is shown (up to 10 reads, one per indicator).

**This is a deliberate exception to "no URLs or phone numbers stored from a submitted message"** (design 2.5). The values are the scam's own contact points, which the worker pasted, and they are what lets a worker warn others with something specific (see [radar](radar.md)). The limits that go with it:
- Only the owner can read them, only for 90 days, and they leave with the account.
- They are never written to logs or analytics: those get `kind` and `flags` only.
- A phone number or address in a message may be the worker's own, not the scammer's. So **nothing leaves this collection until the worker confirms each indicator** in the report confirmation sheet (NF-SA-018), and the report names the confirmed ones.
- Nothing ever fetches, expands or previews a URL (design 5.4).

**Example** — `users/uid_priya_demo/scam_checks/k_01`

```json
{
  "input_type": "text",
  "language": "hi",
  "message_language": "en",
  "redacted_text": "Congratulations! You are selected for a caregiver job in Singapore. Pay 800 SGD processing fee to [ACCOUNT] today or the visa slot is cancelled. WhatsApp [PHONE] or apply at [URL].",
  "cache_key": "4e1d7a9c3b5f20e8d6c4a2b0f8e6d4c2a0b8f6e4d2c0a8b6f4e2d0c8a6b4f2e0",
  "corridor_id": "SG-IN",
  "verdict": {
    "is_scam": true,
    "scam_type": "illegal_recruitment_fee",
    "tactics": ["urgency", "scarcity"],
    "risk_level": "high",
    "confidence": 0.94,
    "trigger_phrases": ["processing fee", "visa slot is cancelled"]
  },
  "details": {
    "contact_channel": "whatsapp",
    "payment_requested": "bank transfer",
    "deadline_stated": true
  },
  "indicators": [
    { "id": "8c83cb97", "kind": "phone", "value": "6590000001", "flags": [] },
    { "id": "f2c46aad", "kind": "url", "value": "sg-careers-visa.example", "flags": ["lookalike"], "imitates": "mom.gov.sg" }
  ],
  "explainer": {
    "kind": "scam",
    "why_it_works": [ { "tactic": "urgency", "text": "..." } ],
    "scammer_wants": "...",
    "next_steps": ["...", "...", "..."],
    "language": "hi",
    "model": "gemini-3.5-flash"
  },
  "similar": [ { "source": "scam_pattern", "id": "illegal_recruitment_fee-en-004", "scam_type": "illegal_recruitment_fee", "score": 0.91 } ],
  "corridor_report_count": 7,
  "check_count": 1,
  "last_checked_at": "2026-11-02T10:15:00Z",
  "taxonomy_version": 1,
  "models": { "classifier": "gemini-3.1-flash-lite", "explainer": "gemini-3.5-flash" },
  "prompt_versions": { "scam.classify": 1, "scam.explain": 1 },
  "created_at": "2026-11-02T10:15:00Z",
  "expires_at": "2027-01-31T10:15:00Z",
  "schema_version": 1
}
```

The message, the number and the address in the example are invented (`.example` is a reserved name that never resolves).

**Access:** the owner reads; **no client writes**. Every check is made through the API, which applies the rate limit (20 an hour) and the redaction.

## `scam_taxonomy/{id}`

The grounding the classifier and the explainer use (design 5.2), and the labels the report to Radar uses. One collection holds both kinds. The id is a lowercase snake_case slug and is **unique across both kinds**. Written by the NF-SA-001 loader, which overwrites by id, so re-running is safe.

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | string | yes | `type` or `tactic` |
| `label` | string | yes | English name, for example `Fake job offer`. It becomes the `entity_name` of a Radar report. |
| `definition` | string | yes | One or two plain sentences |
| `signs` | array of string | yes | Tell-tale signs, 3 to 6 |
| `safe_response` | string | yes | For a `type`: what to do. For a `tactic`: how to resist the pressure. |
| `how_it_works` | string | for `tactic` | Why it works on people. Not on a type. |
| `related_tactics` | array of string | for `type` | Ids of the tactics the type usually uses. Not on a tactic. |
| `default_risk` | string | for `type` | `low`, `medium`, `high`: the starting point for `risk_level` |
| `order` | number | yes | Position in lists |
| `sources` | array of map | yes | `{ "url", "publisher", "retrieved_on" }`, at least one. Every claim traces to a source. |
| `curator` | string | yes | Initials of the person who curated it |
| `schema_version` | number | yes | `1` |

Ids (confirmed by NF-SA-001, which added `other_scam` so a real scam outside the list is not forced into a wrong type): types `fake_job_offer`, `illegal_recruitment_fee`, `remittance_otp_phishing`, `loan_app_trap`, `authority_impersonation`, `investment_romance`, `lottery`, `other_scam`; tactics `urgency`, `authority`, `scarcity`, `fear`, `reciprocity`, `social_proof`.

**Labels in other languages are not stored here.** The screens translate by id through the `scam` i18n namespace (`scam.types.<id>`, `scam.tactics.<id>`, NF-F0-013); the explainer text is written by the model in the worker's language.

**`scam_taxonomy/_meta`** holds `{ "version": number, "content_hash": string, "updated_at": timestamp }`. The loader hashes the validated documents (without `sources` and `curator`, which do not change what a check says), and raises `version` by 1 only when the hash changes (the rule `labor_laws/{country}/_meta/current` follows). A stored check records `taxonomy_version`, and the cache ignores checks made under another version. Code that lists the taxonomy reads `where kind in ["type", "tactic"]`, which leaves `_meta` out.

**Example** — `scam_taxonomy/illegal_recruitment_fee`

```json
{
  "kind": "type",
  "label": "Illegal recruitment fee",
  "definition": "A recruiter asks the worker to pay a fee that the law of the host country or the worker's home country does not allow.",
  "signs": [
    "Asks for money before any signed contract",
    "Fee is called a processing, medical or visa slot charge",
    "Payment to a personal account or by gift card"
  ],
  "safe_response": "Do not pay. Ask for a written contract and check the agency with your government's licensing office.",
  "related_tactics": ["urgency", "scarcity"],
  "default_risk": "high",
  "order": 2,
  "sources": [ { "url": "https://example.org/placeholder", "publisher": "Placeholder", "retrieved_on": "2026-10-28" } ],
  "curator": "XX",
  "schema_version": 1
}
```

The text and the source in this example are placeholders. The curated content is in `data-scripts/data/source/scam-taxonomy/` (NF-SA-001); the `curator` there is the initials of the person who curated it.

**Access:** signed-in users read (reference data, no personal data); only the data script writes.

## `scam_patterns/{id}`

Canonical scam templates, each with a vector. The analyzer embeds an incoming message and searches here for the nearest ones (NF-SA-010). Written by the NF-SA-006 script (`python -m src.loaders.scam_patterns`, in `data-scripts/`), idempotently by id. Loaded: 480 templates, **60 per scam type and 10 per language in each type**, and every corridor in at least 3 per type. A template spells contact points the way the redactor does (`[PHONE]`, `[EMAIL]`, `[ID]`, `[ACCOUNT]`, `[URL]`) because the analyzer embeds the redacted message.

| Field | Type | Required | Description |
|---|---|---|---|
| `scam_type` | string | yes | Taxonomy `type` id |
| `tactics` | array of string | no | Taxonomy `tactic` ids |
| `language` | string | yes | `en`, `hi`, `tl`, `id`, `ne`, `bn` |
| `corridor_id` | string | no | The route the template is written for (one of the six corridors); absent for a worker whose route is not one of them. Kept for coverage and later analysis; a search does not filter on it. |
| `text` | string | yes | The template. Synthetic, with placeholders such as `[AGENCY]`, `[AMOUNT]`. **Never a real message or a real number.** |
| `embedding` | vector | yes | **768 numbers**, normalised, stored with the SDK's `Vector` type |
| `embedding_model` | string | yes | `gemini-embedding-001` |
| `dimension` | number | yes | `768` |
| `source` | string | yes | `curated` |
| `curator` | string | yes | Initials |
| `content_hash` | string | yes | SHA-256 of the text, labels, model and size the vector depends on. The loader skips a template whose hash is unchanged, so a second run makes no Gemini call and no write. |
| `created_at` | timestamp | yes | Set when the template is first loaded and kept when it is re-embedded |
| `schema_version` | number | yes | `1` |

The id is `<scam_type>-<language>-<nnn>`, for example `illegal_recruitment_fee-en-004`. The vector size and model are the same as `report_embeddings` (see [radar](radar.md), why 768), because a search only compares vectors of one size. The search takes the nearest 3 of any type and language: no filter, so no composite vector index is needed, only the plain one in `firestore-schema.md`. If NF-SA-006 finds a filter by language helps, it adds the composite index at that point.

**Access:** no client access; backend only. Neighbours are returned through the API as ids and scores, never as template text.

## `scam_indicators/{id}`

One document per phone number, address, account or handle that a worker has reported, so a check can say **"this number was reported N times"** (D-104). The id is the **first 32 hex characters of the indicator's key** (see `scam_checks`, "The key of an indicator"), so a lookup is a direct read and never a query. Written only by the report endpoint (NF-SA-013).

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | string | yes | `url`, `phone`, `email`, `handle` or `sender` |
| `value` | string | yes | The value in normal form (a URL is its host only) |
| `flags` | array of string | no | As on a check: `shortener`, `punycode`, `lookalike`, `premium_rate`, `unexpected_country` |
| `imitates` | string | no | The real domain or brand a lookalike copies |
| `report_count` | number | yes | Reports that named it. Counts every report. |
| `incident_count` | number | yes | Reports that began a new similarity cluster (`radar_reports.cluster_id` equal to the report's own id). Many near-identical reports of one message are one incident, so one worker repeating a report does not make an indicator look widespread. |
| `scam_type_counts` | map | yes | Taxonomy type id to reports, for example `{ "illegal_recruitment_fee": 3 }` |
| `corridors` | array of string | no | Corridors with reports |
| `host_countries` | array of string | no | Countries with reports |
| `first_reported_at`, `last_reported_at` | timestamp | yes | |
| `flagged` | boolean | yes | `true` at 2 or more incidents: the same rule as `radar_entities` (a pattern, not one unverified report). Below that the count is still shown, worded as "reported once". |
| `hidden` | boolean | yes | `false`. An operator sets `true` to take an indicator out of every lookup, for example after a complaint that a legitimate person was named (D-107). The counts stay for the record. |
| `expires_at` | timestamp | yes | TTL field. `last_reported_at` + 365 days. A phone number is reissued to someone else after a while; a number nobody has reported for a year stops being flagged. |
| `updated_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

**How it is written.** The report endpoint writes the `radar_reports` document, adds one to each confirmed indicator's counters here (creating the document the first time), and sets `scam_checks.reported_report_id`, **all in one transaction**. A check can be reported only once, so a count never rises twice for one check, and the counts cannot drift from the reports. They can still be rebuilt: every counter is derivable from the `radar_reports` documents with `source: "scam_check"`, so the Radar aggregation job (NF-P3-003) may recompute them as a reconciliation if NF-SA-013 wants one.

**How it is read.** When a check is shown (analyze response, history detail), the API looks up each of its indicators here and adds `seen: { "reports", "incidents", "last_reported_at", "flagged" }` to the response, except for a `hidden` indicator, which is treated as never reported. A worker therefore learns that an indicator was reported only for indicators in a message they have themselves, and the analyzer's rate limit (20 an hour) bounds guessing. The "most reported indicators" list for the Radar screens is `order by report_count desc`, one field, automatic index.

**Example** — `scam_indicators/8c83cb97151fd86a6c73ff5fa296244e`

```json
{
  "kind": "phone",
  "value": "6590000001",
  "flags": [],
  "report_count": 5,
  "incident_count": 3,
  "scam_type_counts": { "illegal_recruitment_fee": 4, "fake_job_offer": 1 },
  "corridors": ["SG-IN", "SG-PH"],
  "host_countries": ["SG"],
  "first_reported_at": "2026-11-02T10:20:00Z",
  "last_reported_at": "2026-11-20T07:05:00Z",
  "flagged": true,
  "hidden": false,
  "expires_at": "2027-11-20T07:05:00Z",
  "updated_at": "2026-11-20T07:05:00Z",
  "schema_version": 1
}
```

The number is invented; the id is the real key of that invented number, so the first 8 characters match the `id` of the same indicator in the `scam_checks` example above.

**Access:** no client access; backend only. The values reach a browser only through the API, for the indicators of a check the worker owns, and inside Radar reports.

## `scam_stats/{corridor}/weeks/{isoWeek}`

Counts of the week's checks for one corridor, for dashboards and the Partner API later (NF-SA-022). **Counts only**: no message, no link or number, no worker, no check id. Written by `POST /api/v1/internal/aggregate-scam-stats` (Cloud Scheduler job `scam-stats`, daily at 01:30 UTC).

`{corridor}` is one of the six corridor ids (`SG-PH`, `SG-IN`, `AU-IN`, `MY-ID`, `JP-PH`, `AU-PH`) or `none` for a worker whose route is none of them. `{isoWeek}` is the ISO 8601 week in UTC, `2026-W45`: Monday 00:00 up to the next Monday. The corridor's own document `scam_stats/{corridor}` holds `corridor_id` and `updated_at` only, so the collection can be listed.

| Field | Type | Required | Description |
|---|---|---|---|
| `corridor_id` | string | yes | The corridor, or `none` |
| `iso_week` | string | yes | `2026-W45` |
| `week_start`, `week_end` | timestamp | yes | The week's bounds, `week_end` not included |
| `checks` | number | yes | Stored checks created in the week for this corridor |
| `scams`, `benign` | number | yes | `checks` split by the verdict; they add up to `checks` |
| `by_type` | map | yes | Scams by taxonomy type id, for example `{ "lottery": 2, "loan_app_trap": 1 }`. Only types that occurred; a scam with no type counts as `other_scam`. Adds up to `scams` |
| `by_input` | map | yes | `{ "text": n, "screenshot": n }` |
| `reported` | number | yes | Of the week's checks, how many the worker has since warned others about |
| `computed_at` | timestamp | yes | When the job wrote it |
| `schema_version` | number | yes | `1` |

**How it is written.** Every run counts the current and the previous ISO week (a collection-group query on `scam_checks.created_at`, with a field mask so only `corridor_id`, `verdict.is_scam`, `verdict.scam_type`, `input_type` and `reported_at` are read) and **replaces** the 7 corridor documents of each week. Because it recounts and replaces, a run can be repeated or retried and never counts a check twice. Older weeks are not touched again: checks are deleted 90 days after they were made, and recounting would make a week shrink.

**What a count means.** One stored check is one message of one worker in that language: checking the same message again increments `check_count` on the stored check but is not a new count. A check replaced because it was stale (an older prompt version) is counted in the week it was replaced. A worker who closes their account takes their checks with them, so the current and previous week can go down by that much.

**Small groups.** A week with one check on one corridor describes one person. The collection is backend-only and holds exact counts. **The Partner API must not return a cell below 5** (D-165).

**Index.** A collection-group query on `created_at` needs `scam_checks.created_at` ascending at collection-group scope (`fieldOverrides` in `frontend/firestore.indexes.json`). It exists in production, `READY`, together with the collection-scope ascending and descending ones the history screen uses (read on 2026-10-11, `firestore-schema.md`, "What production holds").

**Access:** no client access (no rule matches `scam_stats`); backend only.

**Example** — `scam_stats/SG-IN/weeks/2026-W45`

```json
{
  "corridor_id": "SG-IN",
  "iso_week": "2026-W45",
  "week_start": "2026-11-02T00:00:00Z",
  "week_end": "2026-11-09T00:00:00Z",
  "checks": 4,
  "scams": 3,
  "benign": 1,
  "by_type": { "illegal_recruitment_fee": 1, "loan_app_trap": 2 },
  "by_input": { "text": 3, "screenshot": 1 },
  "reported": 1,
  "computed_at": "2026-11-04T01:30:02Z",
  "schema_version": 1
}
```

## Analytics events

Three Firebase Analytics events (NF-SA-022, `frontend/src/lib/analytics.ts`). Only coarse values, never a message or anything from it, and none is sent in emulator mode or without a measurement id.

| Event | When | Parameters |
|---|---|---|
| `scam_check_submitted` | The worker taps **Check this message** (once; a retry after a failure is not a new submission) | `input_type` (`text`, `screenshot`), `corridor_id` (a corridor id or `none`), `ui_language` |
| `scam_verdict_viewed` | A verdict is put on the screen, once per check | `is_scam`, `risk_level`, `scam_type` (taxonomy id or `none`), `cached`, `source` (`check` for one that has just finished, `history` for a stored one) |
| `scam_reported` | A new warning was sent (not a second tap that found the first report) | `scam_type` |

**Two names Google owns.** The language parameter is `ui_language`, not `language`: a web stream already attaches the browser's `language` to every event, and a custom parameter of that name never showed in DebugView. Every event also sends `page_location` itself, because Google's own copy is the full address and the address can hold more than the app promises to send: the id of a stored check (`/scam-check/history/{id}`) and, for a message shared into the app, the message (`/scam-check?text=...`). The address sent has no query, no fragment and no id: `/scam-check/history/:id`. The same cleaning applies to `page_path`, to the page before this one when it is one of ours, and to the crash report. Register `ui_language` (not `language`) as the custom dimension.

## Tasks that use it

NF-SA-001 (taxonomy), NF-SA-006 (patterns), NF-SA-007 (verdict), NF-SA-008 (screenshot), NF-SA-009 (explainer), NF-SA-010 (similar), NF-SA-011 (indicators), NF-SA-012 (history, cache), NF-SA-022 (stats and events), NF-SA-013 (report to Radar, writes `scam_indicators`), NF-SA-010 and NF-SA-016 (show "reported N times"), NF-SA-015 to -019 (screens), NF-HR-001 (Financial Identity signal).

## Demo data

The demo workers' five stored checks each (NF-HR-003, `data-scripts/data/seed/scam-checks/`) are ordinary checks plus one extra field, `demo_seed: true`, which only the demo loader reads. They carry the backend's cache key and prompt versions, so the same message in the same language is answered from the check while the taxonomy version and the prompts still match.
