# coach

Financial Coach (Future Scope, NF-F0-003). Shape sources: the paths and what each holds are **[T]** (tracker NF-FC-008, NF-FC-012, NF-FC-014, NF-FC-016) and design addendum `docs/future-scope/design.md` sections 4 and 7. Field names, enums, TTLs and ids are **[P]**: owners of NF-FC-006 (score) and NF-FC-011/-012 (plan) fill in what is marked "defined by", and should tell the team when they change a field name here. The slots are fixed by NF-FC-001 (next section).

```
users/{uid}/coach_sessions/{sessionId}                  one interview (backend writes, owner reads)
users/{uid}/coach_plans/{planId}                        one score + 90-day plan, in English (backend only)
users/{uid}/coach_plans/{planId}/translations/{lang}    the same plan in another language (backend only)
```

All three sit under `users/{uid}`, so `DELETE /api/v1/users/me` removes them with the account (design 2.5). Nothing here is read or written before the `coach` flag is on.

## The slots (NF-FC-001)

Eleven answers the interview collects. The model is `CoachProfile` in `backend/app/schemas/coach_profile.py`; the questions, expected ranges, follow-ups and skip rules are in `backend/app/services/coach/question_bank.json`. `coach_sessions.slots` keeps each one in a `SlotRecord` (below); `coach_plans.slots` keeps the bare values. An unknown slot name is refused.

| Slot | Value | Stage | Asked |
|---|---|---|---|
| `destination_country` | `SG`, `KR`, `MY`, `JP`, `HK`, `AU` | intro | always |
| `job_type` | the seven job types of `users` (`domestic_worker` ... `other`) | intro | always |
| `departure_date` | text `YYYY-MM-DD`, a real date in 2000 to 2100 | intro | always; **may stay empty** (no check-ins without it) |
| `monthly_salary` | money, per `month`, `week` or `year`; more than 0 | income | always |
| `dependents` | whole number, 0 to 20 | obligations | always |
| `remittance_target` | money, per `month`, `week` or `year`; 0 is allowed | obligations | always |
| `recruitment_fee_paid` | money, `once`; 0 is allowed | debt | always |
| `debt_outstanding` | money, `once`; **0 means no debt** | debt | always |
| `debt_interest` | `{ "rate_percent": 0 to 1000, "period": "month" or "year" }` | debt | **skipped when `debt_outstanding.amount` is 0** |
| `savings` | money, `once`; 0 is allowed | savings | always |
| `bank_or_wallet` | `bank_account`, `mobile_wallet`, `both`, `none` | savings | always |

**Money** is always `{ "amount", "currency", "period" }` (never a bare number). Currencies: `SGD`, `KRW`, `MYR`, `JPY`, `HKD`, `AUD` (the hosts), `PHP`, `INR`, `IDR` (the corridors' homes), `NPR`, `BDT` (onboarding also offers Nepal and Bangladesh). `period` is `once` for a total and never `day` or `hour`: a worker paid by the day is asked for a normal month, the coach does not guess the working days. A value is **stored as the worker stated it**: a yearly figure stays `year`, and `Money.per_month()` converts it when a reader needs a month (a week is 52/12, a year 12).

**Two kinds of limit.** The model refuses what cannot be true (a negative amount, 21 dependents, 13th month). The bank holds the *expected* range: outside it the coach asks again before keeping the value, and keeps it only when the worker confirms (`range_issue`). Money ranges are multiples of one rough "monthly pay" number per currency in the bank, to catch an extra zero or a yearly figure called monthly. They are not wage data.

**One stored slot** (`SlotRecord`) has `value`, `confidence` (0 to 1), `source` (`user` or `contract_prefill`), `confirmed`, `updated_at` and `turn`. A slot that was not answered is not stored.

## `users/{uid}/coach_sessions/{sessionId}`

One interview. Auto id. **One active session per user** (NF-FC-008): Firestore has no uniqueness rule, so the backend checks and creates inside one transaction (`status == "active"`, at most one result).

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | string | yes | `active`, `completed` (a plan was created), `abandoned` (idle past 14 days; set by the backend when it next reads the session, so a new one can start) |
| `stage` | string | yes | `intro`, `income`, `obligations`, `debt`, `savings`, `review`, `plan`. Only the transitions of design 4.3 are allowed. |
| `language` | string | yes | Language the coach replies in now. Changes when the worker switches language (NF-FC-018); slots are kept. |
| `slots` | map | yes | Slot name to `{ "value", "confidence", "source", "confirmed", "updated_at", "turn" }`. `confidence` 0 to 1; `source` is `user` or `contract_prefill`; `confirmed` is `true` once the worker has confirmed it (always, for a prefill). Slot names, units and limits: "The slots" above. A money slot holds `{ "amount", "currency", "period" }`, never a bare number. |
| `messages` | array of map | yes | The transcript: `{ "id", "role", "text", "language", "at" }`, `role` is `user` or `coach`. **Text is stored with phone numbers, emails, ID and account numbers and URLs masked** (`app/core/redact.py`, NF-F0-008); amounts are left as written. At most 200 entries (an interview is about 25 turns); a longer session is refused. A turn is appended only after it completes. |
| `last_turn` | map | no | `{ "key", "body_hash", "state", "started_at", "turn", "message_id", "slots" }`: the `Idempotency-Key` of the latest turn, the SHA-256 of its body, `running`, `done` or `failed`, when it started, and its number. `message_id` (the coach message the turn stored) and `slots` (the names of the answers it stored) are set when the turn is done, so a replay can be rebuilt from the transcript (NF-FC-009). It lets a retry after a dropped connection get the stored reply instead of a second turn, and keeps a second turn from starting while one runs (`docs/api/v2-coach.md`, "How the key is kept"). A `running` turn older than 90 seconds counts as failed; a key older than 24 hours is forgotten. Only the latest turn is kept, and the reply is rebuilt from `messages` and the slots stamped with that `turn`, so nothing is stored twice. Optional, so no schema bump (`versioning.md`, rule 1); NF-FC-008 and -009 write it. |
| `summary` | string | no | Short English summary of turns older than the history window (Flash-Lite), so a long session fits the model's budget (NF-FC-009) |
| `summarised_turns` | number | no | How many transcript entries the summary covers |
| `turn_count` | number | yes | Completed user turns |
| `revision` | number | yes | Starts at 1, +1 on every write. The backend writes with "revision must still be N", so two tabs sending a turn at once cannot overwrite each other. |
| `prefill` | map | no | The salary offered from the worker's latest analysed employment contract (NF-FC-015): `{ "contract_id", "fields": ["salary", "employer"], "confirmed": false, "state", "salary": { "amount", "currency", "period" }, "employer" }`. `state` is `offered` (kept until the interview reaches the income stage), `asked` (stored as an **unconfirmed** `monthly_salary` slot with `source: contract_prefill` and the coach has asked) or `resolved` (`confirmed` says whether the worker agreed). The slot counts as an answer only once `confirmed` is true. `employer` is shown in the question only if it looks like a name (short, no markup, no orders) and is not a slot. Absent when the worker has no usable contract |
| `plan_id` | string | when completed | Id of the plan created from this session |
| `plan_lock` | map or null | no | `{ "hash", "started_at" }`: set while the plan for these answers is being made, so a second request gets `409 request_in_progress`; cleared when the plan is stored or fails. A lock older than 150 seconds counts as left by a dead request (NF-FC-012) |
| `last_active` | timestamp | yes | Time of the last completed turn |
| `expires_at` | timestamp | yes | TTL field. `last_active` + 30 days, moved forward on every turn; on completion, `completed_at` + 30 days |
| `completed_at` | timestamp | when completed | |
| `declined_slots` | array of string | yes | Optional slots the worker was asked and chose not to answer (today only `departure_date`: "I do not know yet"). It tells "not sure" from "not asked yet", so the stage can advance without the slot (closes D-171, part 1). Removed from the list when the slot is answered later |
| `question_bank_version` | number | yes | `version` of `question_bank.json` the session was created with (D-171, part 2) |
| `models` | map | yes | `{ "extraction": "...", "reply": "..." }` as of the last turn (ADR-002) |
| `prompt_versions` | map | yes | `{ "coach.extract_slots": 1, "coach.reply": 1 }` |
| `created_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

**Retention.** A session is not needed once its plan exists (the plan keeps a copy of the slots), so 30 days after the last activity is a convenience window for "resume" and "view what I told the coach", not a record. TTL deletion is described in `firestore-schema.md`, "Time to live".

**Example** — `users/uid_rajesh_demo/coach_sessions/s_01` (only four of the eleven slots are answered so far)

```json
{
  "status": "active",
  "stage": "debt",
  "language": "hi",
  "slots": {
    "destination_country": { "value": "AU", "confidence": 1.0, "source": "user", "confirmed": true, "updated_at": "2026-10-20T08:02:11Z", "turn": 1 },
    "job_type": { "value": "care_worker", "confidence": 0.95, "source": "user", "confirmed": true, "updated_at": "2026-10-20T08:02:40Z", "turn": 2 },
    "monthly_salary": { "value": { "amount": 4200, "currency": "AUD", "period": "month" }, "confidence": 0.9, "source": "contract_prefill", "confirmed": true, "updated_at": "2026-10-20T08:05:02Z", "turn": 4 },
    "departure_date": { "value": "2026-12-01", "confidence": 1.0, "source": "user", "confirmed": true, "updated_at": "2026-10-20T08:03:30Z", "turn": 3 }
  },
  "messages": [
    { "id": "t001-c", "role": "coach", "text": "नमस्ते! आप किस देश जा रहे हैं?", "language": "hi", "at": "2026-10-20T08:02:05Z" },
    { "id": "t001-u", "role": "user", "text": "ऑस्ट्रेलिया", "language": "hi", "at": "2026-10-20T08:02:10Z" }
  ],
  "turn_count": 5,
  "revision": 11,
  "last_active": "2026-10-20T08:06:40Z",
  "expires_at": "2026-11-19T08:06:40Z",
  "models": { "extraction": "gemini-3.1-flash-lite", "reply": "gemini-3.5-flash" },
  "prompt_versions": { "coach.extract_slots": 1, "coach.reply": 1 },
  "created_at": "2026-10-20T08:02:00Z",
  "schema_version": 1
}
```

**Access:** the owner reads; **no client writes**. Every change goes through the API so the state machine and the guardrails cannot be skipped. The backend writes with the Admin SDK.

## `users/{uid}/coach_plans/{planId}`

The score and the 90-day plan, written in English once (design 4.4). **The id is the first 20 hex characters of `slot_hash`**, so asking again for the same slots finds the same document and returns it (the idempotency rule of design 4.4; no query needed). Changing a slot changes the hash and makes a new plan; the old one stays until the account is deleted.

| Field | Type | Required | Description |
|---|---|---|---|
| `slot_hash` | string | yes | SHA-256, 64 hex, of the slots' **values only**, in canonical JSON (keys sorted; no confidence, timestamps or source), so re-confirming a slot does not change it |
| `session_id` | string | yes | The session it came from. The session may already be gone (TTL); the plan does not depend on it. |
| `slots` | map | yes | Copy of the slot values the plan was made from: slot name to value |
| `host_country` | string | yes | ISO-2, one of `SG`, `KR`, `MY`, `JP`, `HK`, `AU` |
| `home_country` | string | no | ISO-2 |
| `corridor_id` | string | no | For example `AU-IN`; absent when the route is not one of the six. The plan then has no provider quote. |
| `departure_date` | string (date) | no | `YYYY-MM-DD`, copied from the slots. **Queried across all users by the check-in job** (NF-FC-016), which needs the collection-group index listed in `firestore-schema.md`. Absent: no check-ins. |
| `reporting_currency` | string | yes | Currency of the plan's totals |
| `score` | map | yes | `{ "total": 0 to 100, "band": string, "factors": [ { "id", "value", "score", "weight" } ], "rubric_version": number }`. Factor ids: `debt_to_income`, `emergency_buffer`, `remittance_ratio`, `recruitment_fee_vs_cap`, `banked_status`. Weights, band names and cut-offs are defined in [`docs/features/coach-scoring.md`](../../features/coach-scoring.md) (NF-FC-006). Computed in Python, no model. |
| `plan` | map | yes | The 13-week plan in English: budget, remittance schedule, debt paydown, emergency-fund target, warnings, and the "not professional financial advice" note. Structure defined by NF-FC-011/-012 (`CoachPlan`). Every money figure is `{ "amount", "currency" }`. |
| `rates_as_of` | timestamp | yes | The oldest exchange rate or provider quote the plan used; the time of the plan when it used none (NF-FC-012) |
| `plan_rules_version`, `rubric_version` | number | yes | The versions of the plan rules (`docs/features/coach-plan.md`) and of the score rubric the plan was made with |
| `grounding` | map | yes | What the figures were derived from, so the validator and a reviewer can check them: `{ "baselines": { "host_country", "version" }, "labor_law": { "country", "version" }, "fx": [ { "pair", "rate", "fetched_at", "provider" } ], "provider_quote": { "slug", "name", "fetched_at" } }` |
| `language_generated` | string | yes | `en` |
| `pdf` | map | no | Language to `{ "storage_path", "created_at" }`, for example `{ "en": {...}, "hi": {...} }`. Path: `exports/{uid}/coach-plan-{planId}-{language}.pdf`. Links are signed on request and never stored. |
| `checkins` | map | no | `d30`, `d60`, `d90`, each `{ "due_on": "YYYY-MM-DD", "notified_at": timestamp, "answered_at": timestamp, "answers": map }`. **Absent when a plan is made.** The check-in job (NF-FC-016) writes `due_on` and `notified_at` of a milestone, by field path, once it has sent that milestone's reminder; a milestone without `notified_at` has not been reminded. Field paths keep whatever the app stores beside them later. `answered_at` and `answers` are the three check-in questions of NF-FC-022 (not built yet, D-233) and may move to their own subcollection there. |
| `models` | map | yes | `{ "plan": "...", "translation": "..." }` |
| `prompt_versions` | map | yes | `{ "coach.plan": 1, "coach.translate_plan": 1 }` |
| `created_at`, `updated_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

**Why PDFs live under `exports/`.** Account deletion already removes everything under `exports/{uid}/` (`app/integrations/cloud_storage.py`, `USER_FILE_FOLDERS`), so plan PDFs need no change to the deletion code, which design 2.5 had flagged for NF-FC-014. The Financial Identity export deletes only the one file its `latest_export` points to, so the two never clear each other's files.

**Example** — `users/uid_rajesh_demo/coach_plans/9f3a1c5e7b2d4a60c8e1`

```json
{
  "slot_hash": "9f3a1c5e7b2d4a60c8e1f4a7b9d2c5e8a1b4d7c0e3f6a9b2c5d8e1f4a7b0c3d6",
  "session_id": "s_01",
  "slots": {
    "destination_country": "AU",
    "job_type": "care_worker",
    "monthly_salary": { "amount": 4200, "currency": "AUD", "period": "month" },
    "departure_date": "2026-12-01"
  },
  "host_country": "AU",
  "home_country": "IN",
  "corridor_id": "AU-IN",
  "departure_date": "2026-12-01",
  "reporting_currency": "AUD",
  "score": {
    "total": 68,
    "band": "getting_ready",
    "factors": [
      { "id": "debt_to_income", "value": 0.18, "score": 72, "weight": 0.3 },
      { "id": "emergency_buffer", "value": 1.5, "score": 45, "weight": 0.25 }
    ],
    "rubric_version": 1
  },
  "plan": { "weeks": ["... defined by NF-FC-012 ..."] },
  "grounding": {
    "baselines": { "host_country": "AU", "version": 1 },
    "labor_law": { "country": "AU", "version": 1 },
    "fx": [ { "pair": "AUD_INR", "rate": 55.12, "fetched_at": "2026-10-20T08:00:00Z", "provider": "frankfurter" } ],
    "provider_quote": { "slug": "example-remit", "name": "Example Remit", "fetched_at": "2026-10-20T08:00:00Z" }
  },
  "language_generated": "en",
  "pdf": { "en": { "storage_path": "exports/uid_rajesh_demo/coach-plan-9f3a1c5e7b2d4a60c8e1-en.pdf", "created_at": "2026-10-20T08:09:00Z" } },
  "checkins": {
    "d30": { "due_on": "2026-12-31", "notified_at": "2026-12-31T02:00:04Z" }
  },
  "models": { "plan": "gemini-3.5-flash", "translation": "gemini-3.1-flash-lite" },
  "prompt_versions": { "coach.plan": 1, "coach.translate_plan": 1 },
  "created_at": "2026-10-20T08:08:30Z",
  "updated_at": "2026-10-20T08:09:00Z",
  "schema_version": 1
}
```

Values are illustrative: the score, the rate and the plan body come from NF-FC-006, the live rate cache and NF-FC-012. `checkins` is shown as it is after the day 30 reminder; the other two milestones are added when they are sent.

**Access:** the owner reads; **no client writes**. Backend only writes.

## `users/{uid}/coach_plans/{planId}/translations/{language}`

The plan in one other language (design 4.4: generated in English, then translated). The id is the language code: `hi`, `tl`, `id`, `ne`, `bn`. English is the parent's `plan`.

| Field | Type | Required | Description |
|---|---|---|---|
| `language` | string | yes | Same as the id |
| `plan` | map | yes | Same structure as the parent's `plan`, with the narrative translated. **Every number, currency code and date is byte-identical to the parent's** (NF-FC-014 checks this before saving). |
| `model` | string | yes | Translation model id |
| `prompt_version` | number | yes | `coach.translate_plan` version |
| `created_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

A translation is a separate document, as Contract Shield's `reports/{language}` is, so the main plan stays small and the languages a worker never asks for cost nothing.

**Access:** the owner reads; no client writes.

## Indexes

None beyond the automatic ones, except the collection-group index on `coach_plans.departure_date` in `firestore-schema.md`. The queries are: the active session (`status ==` inside one user's subcollection), the newest plans (`order by created_at desc`, one user), and the check-in job (`departure_date` in a range of 4 days for each of the three milestones, all users).

## Tasks that use it

NF-FC-001 (slots), NF-FC-006/-011 (score), NF-FC-008 (sessions), NF-FC-009/-010 (turns), NF-FC-012 (plan), NF-FC-013 (guardrails), NF-FC-014 (translation and PDF), NF-FC-015 (contract prefill, goals), NF-FC-016 (check-ins), NF-FC-017 to -023 (screens), NF-HR-001 (Financial Identity signal).
