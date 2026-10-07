# API v2: Scam Analyzer

The contract of the Scam Analyzer (NF-SA-002): a worker pastes a message or shares a screenshot and gets a verdict, the manipulation it uses, what to do, and a way to warn other workers. Follows `docs/api/v2-conventions.md` (error envelope, pagination, versioning) and is guarded by the `scam` flag (`docs/api/v2-flags.md`).

| Where | What |
|---|---|
| This file | The routes, the fields and the rules |
| `backend/app/schemas/scam.py` | The same contract as Pydantic models. The endpoints import them (NF-SA-007, -008, -012, -013); the models win if this file and they ever disagree, and a test makes them agree with the mocks |
| `docs/mocks/scam/` | One sample of every answer, 22 files. The frontend's mock API (MSW) serves them, so the screens (NF-SA-015 to -018) can be built before the backend exists |
| `docs/data-model/collections/scam.md`, `radar.md` | Where a check is stored, for how long, and what a Radar report holds |
| `data-scripts/data/source/scam-taxonomy/` | The scam types and tactics whose ids appear in answers (`illegal_recruitment_fee`, `urgency`, ...). The screens translate an id through the `scam` i18n namespace; the API never sends a label |

## Routes

| Method | Path | Does | Rate limit |
|---|---|---|---|
| `POST` | `/api/v2/scam/analyze` | Check a message or a screenshot | 20 an hour that call Gemini, plus 60 a minute API-wide |
| `GET` | `/api/v2/scam/checks` | The worker's history, newest first | 60 a minute |
| `GET` | `/api/v2/scam/checks/{id}` | One stored check | 60 a minute |
| `POST` | `/api/v2/scam/checks/{id}/report` | Warn other workers: report it to Exploitation Radar | 60 a minute |

## What every route shares

- **Auth.** Firebase ID token as `Authorization: Bearer ...`. Missing or invalid is `401 unauthenticated` before anything else.
- **Flag.** Every route adds `require_flag("scam")`. With the flag off for the caller the answer is the same `404 not_found` an unknown path gets, whichever route and whatever the body.
- **Errors** are the standard envelope `{code, message, request_id}` (conventions, section 2). `X-Request-ID` is on every response. A Gemini failure uses the `ai_*` codes of the conventions.
- **Languages** are `en`, `hi`, `tl`, `id`, `ne`, `bn`. **Corridors** are `SG-PH`, `SG-IN`, `AU-IN`, `MY-ID`, `JP-PH`, `AU-PH`; a request may name one, otherwise the one in the worker's profile is used.
- **Ownership.** A check belongs to the worker who made it. Asking for another worker's check, or one that does not exist, is the same `404 not_found`, so a stranger cannot learn which ids exist.
- **`Idempotency-Key`: not used on any of these routes** (a departure from the conventions' default of "required" for a `POST` that spends quota). The conventions leave the storage of keys to the data model, and none was designed. Both `POST`s are idempotent in their own way instead:
  - *analyze* by the check's cache: the same message in the same language is found by the hash of its redacted text and answered from storage (`cached: true`), so a retry after a dropped connection costs nothing if the first request finished. If it did not finish, the retry runs again: one extra Gemini call, and still one stored check, because a check is written under its hash.
  - *report* by the check: `reported_report_id` is set once, so a second tap returns the first report.
  If a header is sent it is ignored.
- **What no answer ever contains:** the raw message, the screenshot, the model names, the prompt versions, the cache key, or anything of another worker. The text is always the redacted one.

## `POST /api/v2/scam/analyze`

Check one message. The body is either JSON (a pasted message) or a form (a screenshot); the `Content-Type` decides.

**Pasted message**: `Content-Type: application/json`, `ScamAnalyzeTextRequest`:

| Field | Type | Required | Rule |
|---|---|---|---|
| `text` | string | yes | The message as received, 1 to **4,000** characters after trimming. Over the limit is a `422`, **never cut**: the payment request is often at the end |
| `language` | string | yes | The worker's language; the explainer is written in it |
| `corridor_id` | string | no | The worker's route |

**Screenshot**: `Content-Type: multipart/form-data`:

| Field | Type | Required | Rule |
|---|---|---|---|
| `image` | file | yes | JPEG, PNG or WebP, at most **5 MB**. Anything else is `415`; larger is `413 payload_too_large` |
| `language`, `corridor_id` | string | as above | |

The server resizes the image, reads the message text and any visible sender, redacts the text and **discards the image**: it is never stored. A sender found in the image becomes an indicator of kind `sender`. If no text can be read the answer is `422 image_unreadable`.

**What happens** (design 5.2): the text is redacted (`[PHONE]`, `[EMAIL]`, `[ID]`, `[ACCOUNT]`, `[URL]`; amounts stay) and its hash looked up; on a hit the stored check is returned and **no Gemini call is made and the hourly budget is not used**. On a miss the server extracts indicators (nothing is ever fetched), classifies the message, looks for similar scams in parallel, writes the explainer, and stores the check.

**Response `200`**, `ScamAnalyzeResponse`: the check below plus `cached`.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | The check's id, for the detail and report routes |
| `cached` | boolean | `true` when this exact message was checked before |
| `input_type` | `text` or `screenshot` | |
| `language` | string | The worker's language (the explainer's) |
| `message_language` | string or `null` | The message's own language: the six codes, or `other` |
| `redacted_text` | string | The message with identifiers masked. This is what the screen shows, with `trigger_phrases` highlighted |
| `corridor_id` | string or `null` | |
| `verdict` | object | See below |
| `details` | object | What the message asks for. Every key optional; `{}` when nothing is known |
| `indicators` | array, at most 10 | Phone numbers, addresses and accounts found in the message |
| `explainer` | object or `null` | See below |
| `explainer_status` | `ready` or `unavailable` | `unavailable` exactly when `explainer` is `null` |
| `similar` | array, at most 3 | Known scams that resemble it |
| `corridor_report_count` | number or `null` | Radar reports on the worker's route when the check ran |
| `reported`, `report_id` | boolean, string or `null` | Whether the worker already warned others, and the report's id |
| `created_at`, `expires_at` | timestamp | The check is deleted at `expires_at` (90 days after it was last checked) |

**`verdict`** (`ScamVerdict`, also the classifier's output schema):

| Field | Type | Rule |
|---|---|---|
| `is_scam` | boolean | |
| `scam_type` | taxonomy id or `null` | `null` exactly when `is_scam` is `false`. `other_scam` for a scam that fits none of the types |
| `tactics` | array of taxonomy ids, at most 6 | Empty when not a scam |
| `risk_level` | `low`, `medium`, `high` | How much is at stake if the worker acts on it. **Always `low` when `is_scam` is `false`**. A scam can be low (a prize message that asks for nothing yet) |
| `confidence` | number, 0 to 1 | |
| `trigger_phrases` | array of strings, at most 5 | Each is a piece of `redacted_text`, at most 80 characters, for highlighting |

**`details`** (`ScamDetails`): `claimed_identity` (string), `contact_channel` (`sms`, `whatsapp`, `call`, `email`, `other`), `payment_requested` (string), `amount_requested` (`{amount, currency}`), `deadline_stated` (boolean). The classifier fills what the message says and leaves the rest out; an absent key means unknown, not "no".

**`indicators[]`** (`ScamIndicator`):

| Field | Meaning |
|---|---|
| `id` | 8 hex characters, stable for the same kind and value. The report names indicators by it |
| `kind` | `url`, `phone`, `email`, `handle` or `sender` |
| `value` | A URL is its host only; a phone number is digits with the country code |
| `flags` | Any of `shortener`, `punycode`, `lookalike`, `premium_rate`, `unexpected_country`; may be empty |
| `imitates` | The real domain a `lookalike` copies, for example `mom.gov.sg`. Only with that flag |
| `seen` | `{reports, incidents, last_reported_at, flagged}`: how often workers reported it. `flagged` means at least 2 incidents. **`null` when it was never reported** (or an operator hid it) |

The values are the scam's own contact points, shown to the worker who pasted them. A phone number in a message may be the worker's own, which is why none of it leaves the check until the worker confirms it (the report below). Nothing is ever fetched, opened or previewed.

**`explainer`**, one of two shapes by `kind`, written in `language` at a grade-6 reading level:

| `kind` | Fields |
|---|---|
| `scam` | `why_it_works`: array of `{tactic, text}`, one per detected tactic (the "tap to explain" text); `scammer_wants`: string; `next_steps`: exactly 3 strings |
| `benign` | `reassurance`: string; `tip`: string |

**`similar[]`**: `{source, scam_type, score}`; `source` is `scam_pattern` (a known template) or `radar_report` (a worker's report); `score` 0 to 1. No ids and no text of other people's reports are sent.

**When the explainer fails.** If classification worked but the explainer step failed (Gemini busy or out of quota), the answer is still `200`, with `explainer: null` and `explainer_status: "unavailable"`: the worker keeps the verdict. Such a check is **not** served from the cache, so sending the same message again produces the explainer. If classification itself fails the answer is an error (`ai_*`) and nothing is stored.

| Status | `code` | When |
|---|---|---|
| `200` | | Checked, or served from the cache |
| `401` | `unauthenticated` | |
| `404` | `not_found` | Flag off |
| `413` | `payload_too_large` | Image over 5 MB |
| `415` | `unsupported_media_type` | Body is neither JSON nor a form, or the image is not JPEG, PNG or WebP |
| `422` | `validation_failed` | Empty text, text over 4,000 characters, a language or corridor outside the project. `details` names the field |
| `422` | `image_unreadable` | No message text could be read from the image |
| `429` | `rate_limited` | Over 20 checks an hour that called Gemini (cache hits do not count), or 60 calls a minute. Sends `Retry-After` and `X-RateLimit-*` |
| `502`, `503`, `504` | `ai_bad_response`, `ai_busy` or `ai_unavailable`, `ai_timeout` | Gemini failed before a verdict existed |

**Time.** A message that is not a scam, or one answered from the cache, returns in a few seconds (the verdict budget is 6 s at the 95th percentile). A scam also waits for the explainer, which is on the reasoning tier and has taken 15 to 40 s (D-115): **the client allows 60 s and shows progress**, and the screens must not treat a slow answer as a failure. If the explainer step proves too slow, the implementation may move it to a faster tier or time-box it into the `unavailable` case above; neither changes this contract.

```bash
# a pasted message
curl -s -X POST http://127.0.0.1:8080/api/v2/scam/analyze \
  -H "Authorization: Bearer $ID_TOKEN" -H "Content-Type: application/json" \
  -d '{"text": "Pay 800 SGD processing fee today or the visa slot is cancelled", "language": "hi", "corridor_id": "SG-IN"}'

# a screenshot
curl -s -X POST http://127.0.0.1:8080/api/v2/scam/analyze \
  -H "Authorization: Bearer $ID_TOKEN" -F "image=@message.png" -F "language=en"
```

Samples: `analyze-01-high-risk.json` (the default), `-02-medium-risk`, `-03-low-risk`, `-04-benign`, `-05-cached`, `-06-explainer-unavailable`, and the refusals `analyze-error-*.json`.

## `GET /api/v2/scam/checks`

The worker's history, **newest first by `created_at`**, with cursor pagination (conventions, section 3): query `limit` (1 to 100, default 20) and `cursor`. A bad cursor is `400 invalid_cursor`.

**Response `200`**, `ScamCheckListResponse`: `{items, next_cursor}`; `next_cursor` is `null` on the last page. Each item (`ScamCheckSummary`) is what a history row needs and nothing more:

| Field | Meaning |
|---|---|
| `id`, `created_at`, `input_type`, `language` | |
| `is_scam`, `scam_type`, `risk_level`, `confidence` | The verdict's headline, for the risk badge |
| `excerpt` | The first 140 characters of `redacted_text` |
| `reported` | Whether the worker already warned others |

Errors: `401`, `404` (flag off), `400 invalid_cursor`, `422 validation_failed` (limit out of range), `429`. Samples: `checks-list-01-first-page.json`, `-02-last-page`, `-03-empty`.

## `GET /api/v2/scam/checks/{id}`

One stored check, `ScamCheckDetail`: the same fields as the analyze answer without `cached`. **`indicators[].seen` is read live**, so a number reported since the check was made shows its current count. Errors: `401`, `404 not_found` (flag off, no such check, or not the caller's), `429`. Samples: `check-01-high-risk.json` to `check-04-benign.json`, `check-error-not-found.json`.

## `POST /api/v2/scam/checks/{id}/report`

Warn other workers: report the scam to Exploitation Radar. The app shows a **confirmation sheet** first, listing exactly what will be visible to other workers, and this request carries exactly that. Nothing is sent that is not in the request.

**Request**, `ScamReportRequest`, `Content-Type: application/json`:

| Field | Type | Rule |
|---|---|---|
| `indicator_ids` | array of strings | The ids of the indicators the worker left ticked: at most 10, no repeats, each one in this check. **May be empty**: the worker unticked everything and the report carries no contact point |
| `description` | string | Optional. The message text as the worker edited it (to remove a name, for example), 1 to 1,000 characters. Defaults to `redacted_text` cut at 1,000 |

**What the server does:**
1. Checks that the check is the caller's and that its verdict is a scam. Reporting a message the analyzer judged benign is `409 not_a_scam`.
2. **Redacts `description` again.** The worker can type anything into the box, so what they send is never trusted to be clean. (Personal names are not masked by a pattern; the sheet is where the worker removes one, D-108.)
3. Writes the Radar report, adds one to the counters of each confirmed indicator, and marks the check as reported, **in one transaction** (`radar.md`, "Scam reports"; `scam.md`, `scam_indicators`). No uid and no reporter hash is stored.
4. If the check was already reported, returns the first report and writes nothing.

**Response**, `ScamReportResponse`: `{report_id, already_reported, entity_slug, entity_name, created_at}`. **`201`** for a new report, **`200`** with `already_reported: true` for a repeat. `entity_slug` is the Radar profile of the scam type (`scam-illegal-recruitment-fee`): link to `/radar/entity/{entity_slug}`.

| Status | `code` | When |
|---|---|---|
| `201`, `200` | | Reported; already reported |
| `401`, `404` | `unauthenticated`, `not_found` | No token; flag off, no such check or not the caller's |
| `409` | `not_a_scam` | The check's verdict is not a scam |
| `422` | `validation_failed` | An `indicator_ids` entry not in this check, a repeat, more than 10, an empty or over-long `description` |
| `429` | `rate_limited` | |

Samples: `report-01-created.json`, `report-02-already-reported.json`, `report-error-validation.json`, `report-error-not-a-scam.json`.

## Error codes added by this feature

The conventions allow a feature its own codes (section 2). These do not reuse any code above for another meaning.

| Status | `code` | Used by |
|---|---|---|
| 415 | `unsupported_media_type` | analyze |
| 422 | `image_unreadable` | analyze |
| 409 | `not_a_scam` | report |

## Changing this contract

The rules of the conventions (section 6) apply. Adding a field to a response, an optional request field, a new value of `flags`, `kind` or `contact_channel` (clients ignore a value they do not know), or a new taxonomy id is not breaking. Removing or renaming a field, changing a type or the meaning of `risk_level`, tightening a limit, or making an optional request field required is. A change updates this file, `backend/app/schemas/scam.py` and the mocks together: the drift test (`backend/tests/unit/test_scam_mocks.py`) fails until they agree.

## Open points for the implementing tasks

| # | Point | Owner |
|---|---|---|
| 1 | The explainer's latency on the reasoning tier (D-115). The contract allows a slow answer and an `unavailable` explainer; the task decides the tier and the time-box | NF-SA-009 |
| 2 | iPhones can produce HEIC photos, which the image library cannot read without a new dependency. Browsers usually convert to JPEG on upload; if they do not, the answer is `415` | NF-SA-008, NF-SA-015 |
| 3 | `Idempotency-Key` has no storage in the data model. If a later feature needs real keys (the Coach's plan may), the storage is designed then; this feature does not need it | NF-FC-002 |
| 4 | Radar's existing `GET /api/v1/radar/entities/{slug}/reports` must return the `scam` map of a scam report (`radar.md`), without `reporter_hash`, for the entity page of a scam type | NF-SA-013, NF-SA-018 |
