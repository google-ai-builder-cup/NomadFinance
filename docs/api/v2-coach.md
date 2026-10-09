# API v2: Financial Coach

The contract of the Financial Coach (NF-FC-002): a worker who is about to leave answers a short interview in their own language, sees a preparedness score, and gets a 13-week plan with a PDF. Follows `docs/api/v2-conventions.md` (error envelope, streaming, idempotency, versioning) and is guarded by the `coach` flag (`docs/api/v2-flags.md`).

| Where | What |
|---|---|
| This file | The routes, the fields and the rules |
| `backend/app/schemas/coach_session.py`, `coach_plan.py` | The same contract as Pydantic models, with the rules that can be checked (the stage, the budget's arithmetic, the plan id). The endpoints import them (NF-FC-008 to -012, -014); the models win if this file and they ever disagree, and a test makes them agree with the mocks |
| `backend/app/schemas/coach_profile.py` | The eleven slots and their limits (NF-FC-001); a session and a plan hold their values |
| `docs/mocks/coach/` | One sample of every answer, 30 JSON files and 10 streams. The frontend's mock API (MSW) serves them, so the screens (NF-FC-017, -020, -021) can be built before the backend exists |
| `docs/data-model/collections/coach.md` | Where a session and a plan are stored, and for how long |
| `backend/app/services/coach/question_bank.json` | The questions, in order, with their skip rules (NF-FC-001) |

## Implementation status

The session routes are built (NF-FC-008): `POST /coach/sessions`, `GET /coach/sessions/{id}` and `GET /coach/overview`. The turn route is built (NF-FC-009): `POST /coach/sessions/{id}/messages`, with the stream, the idempotency rules, the history window and the summary. **Slot extraction is built (NF-FC-010)**: each message is read by one structured call (`coach/extract.v1`) and by checks that keep only what the worker stated, so `slot_update` events are sent, answers are stored and the stage moves. A gap (a money or period not named, an amount outside the usual range, an unsure reading) is asked about with the bank's follow-up wording instead of being guessed. **The score is built (NF-FC-011)**: at `review` and `plan` the session carries it, worked out from the answers, the stored cost baselines, the legal fee cap and the stored exchange rates (`docs/features/coach-scoring.md`). When something it needs is missing (a rate, the host's cost baseline, an amount in a currency with no rate) `score` stays `null`, which the contract allows, and the reason is logged. **The plan is built (NF-FC-012)**: `POST /coach/sessions/{id}/plan` and `GET /coach/plans/{id}` return the plan in English, with every figure worked out in code and the sentences checked (`docs/features/coach-plan.md`). **Translation and the PDF are built (NF-FC-014)**: `language` on `POST /plan` and `GET /plans/{id}` returns the plan in that language, translated once by Flash-Lite and kept (`coach_plans/{id}/translations/{language}`); every figure, currency code, date, id and severity is checked to be identical to the English plan before it is saved. `GET /plans/{id}.pdf?language=` returns the PDF through the API, made on first request and kept in Cloud Storage. The Gemini budget (10 a minute) is spent only when a translation is really made. **The guardrails are built (NF-FC-013)**: every worker message is screened before anything reads it (rules first, one Flash-Lite check for what the rules cannot judge). A message that is off topic, gives the coach orders, asks it to choose a loan, an investment, an app or a company, or signals danger is answered with fixed words, then `done`; see "A blocked turn" below. The plan and its PDF carry the "not professional financial advice" note in the worker's language, as fixed wording, not as a translation. The rest is specified only.

| Route | Built by |
|---|---|
| `POST /coach/sessions`, `GET /coach/sessions/{id}`, `GET /coach/overview` | NF-FC-008 (built), NF-FC-022 uses the overview |
| `POST /coach/sessions/{id}/messages` | NF-FC-009 (the stream, built), NF-FC-010 (understanding the answer, built), NF-FC-013 (guardrails, built) |
| `POST /coach/sessions/{id}/plan`, `GET /coach/plans/{id}` | NF-FC-011 (score, built), NF-FC-012 (plan, built), NF-FC-014 (translation, built) |
| `GET /coach/plans/{id}.pdf` | NF-FC-014 (built) |

## Routes

| Method | Path | Does | Rate limit |
|---|---|---|---|
| `POST` | `/api/v2/coach/sessions` | Start the interview, or resume the one that is open | 60 a minute API-wide |
| `GET` | `/api/v2/coach/sessions/{id}` | One session: the answers so far, the transcript, the next question, the score | 60 a minute |
| `POST` | `/api/v2/coach/sessions/{id}/messages` | One turn: the worker speaks, the coach answers as a stream (SSE) | 10 a minute (the Gemini budget), plus 60 a minute API-wide |
| `POST` | `/api/v2/coach/sessions/{id}/plan` | Make the plan (and its PDF) from the confirmed answers | 10 a minute when it calls Gemini, plus 60 a minute |
| `GET` | `/api/v2/coach/plans/{id}` | A stored plan, in one language | 60 a minute; 10 a minute when it has to translate |
| `GET` | `/api/v2/coach/plans/{id}.pdf` | The plan as a PDF file | 60 a minute; 10 a minute when it has to make the file |
| `GET` | `/api/v2/coach/overview` | The active session and the newest plan, for the dashboard card | 60 a minute |

"When it calls Gemini" means the Gemini budget (10 a minute per worker, `RATE_LIMIT_AI`) is used only by a request that really makes a Gemini call; a plan or a translation that is already stored costs none of it.

## What every route shares

- **Auth.** Firebase ID token as `Authorization: Bearer ...`. Missing or invalid is `401 unauthenticated` before anything else.
- **Flag.** Every route adds `require_flag("coach")`. With the flag off for the caller the answer is the same `404 not_found` an unknown path gets, whichever route and whatever the body.
- **Errors** are the standard envelope `{code, message, request_id}` (conventions, section 2). `X-Request-ID` is on every response. A Gemini failure uses the `ai_*` codes of the conventions.
- **Languages** are `en`, `hi`, `tl`, `id`, `ne`, `bn`. **Corridors** are `SG-PH`, `SG-IN`, `AU-IN`, `MY-ID`, `JP-PH`, `AU-PH`. **Host countries** are `SG`, `KR`, `MY`, `JP`, `HK`, `AU`.
- **Ownership.** A session and a plan belong to the worker who made them. Asking for another worker's, or one that does not exist, is the same `404 not_found`, so a stranger cannot learn which ids exist.
- **`Idempotency-Key`** (conventions, section 5):

  | Route | Key | Why |
  |---|---|---|
  | `POST /sessions` | not used | One active session per worker: asking twice gives the same session |
  | `POST /sessions/{id}/messages` | **required** | A turn spends Gemini quota and changes the session; a dropped connection is retried with the same key |
  | `POST /sessions/{id}/plan` | optional, ignored | Idempotent by its own nature: the plan is found by the hash of the answers (below) |

  A missing key where it is required is `400 idempotency_key_invalid`.
- **What no answer ever contains:** model names, prompt versions, the revision of a session, the slot hash's inputs, another worker's data, or a stack trace. Transcript text is always the redacted one (phone numbers, emails, ID and account numbers and URLs masked; amounts stay).

## The interview

```
POST /sessions ──► POST /messages (no text: the coach speaks first)
                         │
                         ▼
        ┌─► POST /messages (the worker answers) ──► stream ──► done ─┐
        └────────────────────────────────────────────────────────────┘
                         │ the last answer
                         ▼
                 stage `review`: the coach lists what it understood; GET /sessions/{id} has the score
                         │ the worker says yes
                         ▼
                 stage `plan`: the score screen's button ──► POST /plan ──► GET /plans/{id}(.pdf)
```

A worker who corrects something at `review` goes back to the stage that holds it (design 4.3); the contract does not change, only `stage` and `next_slot` do.

**Stages**, in order (a stage is left only when its required answers are in; a worker who volunteers a later fact keeps it):

| Stage | Slots asked |
|---|---|
| `intro` | `destination_country`, `job_type`, `departure_date` (the only optional one) |
| `income` | `monthly_salary` |
| `obligations` | `dependents`, `remittance_target` |
| `debt` | `recruitment_fee_paid`, `debt_outstanding`, `debt_interest` (skipped when the debt is 0) |
| `savings` | `savings`, `bank_or_wallet` |
| `review`, `plan` | none. `next_slot` is `null` |

**What the screen offers for each slot** (it knows the slot from `next_slot`; the values are those of `CoachProfile`):

| Slot | Value | Input |
|---|---|---|
| `destination_country` | `SG` `KR` `MY` `JP` `HK` `AU` | six choices |
| `job_type` | `domestic_worker` `manufacturing_worker` `care_worker` `plantation_worker` `construction_worker` `working_holiday` `other` | seven choices |
| `departure_date` | `YYYY-MM-DD` | a date, and "I do not know yet" |
| `monthly_salary`, `remittance_target` | `{amount, currency, period}`, period `month`, `week` or `year` | an amount, a currency, a period |
| `recruitment_fee_paid`, `debt_outstanding`, `savings` | `{amount, currency, period: "once"}` | an amount and a currency |
| `dependents` | whole number, 0 to 20 | a number |
| `debt_interest` | `{rate_percent, period}`, period `month` or `year` | a rate and a period |
| `bank_or_wallet` | `bank_account` `mobile_wallet` `both` `none` | four choices |

The screen's helpers (chips, amount and currency fields) **write the answer as text** ("4,200 AUD a month"); the server understands it (NF-FC-010). There is no structured answer in this version (open point 3).

## `POST /api/v2/coach/sessions`

Start the interview, or resume the open one. **Request**, `CoachSessionCreateRequest`, `Content-Type: application/json`:

| Field | Type | Required | Rule |
|---|---|---|---|
| `language` | string | yes | The language a **new** session starts in. A resumed session keeps its own; the screen changes it with a turn (below) |
| `restart` | boolean | no | `true` closes the active session (it becomes `abandoned`) and starts a new one. Default `false` |

**Response**, `CoachSessionCreateResponse`: the session of `GET` below plus `resumed` (`true` when the worker already had an active one). **`201`** for a new session, **`200`** when it was resumed. A new session has no messages: the screen opens the interview with a turn that has no text. No Gemini call is made here.

A worker has one active session (`status: "active"`); a completed or abandoned one does not count. Two requests at the same moment still give one session (the backend checks and creates in one transaction, `coach.md`). Errors: `401`, `404` (flag off), `409 request_in_progress` (a burst of starts at the same moment made the transaction give up; sends `Retry-After: 2`, retry), `422 validation_failed` (a language outside the six), `429`. Samples: `sessions-create-01-new.json` (the default), `sessions-create-02-resumed.json`.

## `GET /api/v2/coach/sessions/{id}`

**Response `200`**, `CoachSession`:

| Field | Type | Meaning |
|---|---|---|
| `id` | string | |
| `status` | `active`, `completed`, `abandoned` | `completed` once a plan was made; `abandoned` after 14 days without a turn, or after `restart` |
| `stage` | see the table above | |
| `language` | string | The language the coach replies in now |
| `slots` | object | Answered slots only, by slot name: `{value, confirmed, source}`. `value` is shaped as in the table above; `confirmed` is `true` once the worker agreed to it; `source` is `user` or `contract_prefill` |
| `messages` | array, at most 200 | The whole transcript, oldest first: `{id, role, text, language, at}`, `role` is `user` or `coach`. Bounded by design, so it is not paged. The text is the redacted one: a phone number the worker typed comes back as `[PHONE]` |
| `next_slot` | slot name or `null` | The slot the coach asks for next. `null` exactly in the stages `review` and `plan` |
| `turn_count` | number | Answers the worker has given (a clarifying turn counts) |
| `score` | object or `null` | The preparedness score (below). `null` before `review`; at `review` and `plan` it is there unless it cannot be worked out yet (an exchange rate is missing), in which case the screen shows "try again" and asks again |
| `plan_id` | string or `null` | Set exactly when `status` is `completed` |
| `created_at`, `last_active` | timestamp | `last_active` is the time of the last completed turn |

A session is kept 30 days after its last turn, then deleted with its transcript (`coach.md`); the plan outlives it. Errors: `401`, `404 not_found` (flag off, no such session, or not the caller's), `429`. Samples: `session-01-new.json` to `session-07-completed.json` (one per state, three score bands among them) and `session-error-not-found.json`.

## `POST /api/v2/coach/sessions/{id}/messages` (stream)

One turn. The worker's answer goes in, the coach's reply comes back **as it is written**, token by token, as Server-Sent Events (conventions, section 4: read it with `fetch` and a stream reader, not `EventSource`).

**Request**, `CoachTurnRequest`, `Content-Type: application/json`, `Accept: text/event-stream`, `Idempotency-Key: <key>` (required):

| Field | Type | Required | Rule |
|---|---|---|---|
| `text` | string | no | The worker's answer: 1 to **1,000** characters after trimming. Over the limit is `422`, **never cut**. **Omit it** and the coach speaks without a new answer: the opening question of a session with no messages, or the current question again after the worker changed `language` (NF-FC-018). Omitted at any other time is `422` |
| `language` | string | yes | The language of this turn and of the reply. It becomes the session's `language` when the turn is saved: a worker who switches language keeps every answer and the stage |

**Response `200`** (once the stream has started), headers `Content-Type: text/event-stream; charset=utf-8`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`, `X-Request-ID`. The events are those of the conventions:

| Event | `data` | Meaning |
|---|---|---|
| `token` | `{"text": "..."}` | A piece of the reply, appended in order. The reply is in `language`, in short sentences |
| `slot_update` | `{"slot", "value", "confirmed"}` | The server understood a fact. `value` is shaped as in the slot table; `confirmed` says whether the worker agreed to it |
| `done` | `{"message_id", "stage", "next_slot", "turn_count"}` | Terminal. The turn is complete and **saved**. `message_id` is the coach message just stored; `stage` and `next_slot` are where the interview stands now |
| `error` | the error envelope, without `details` | Terminal. The turn failed after the stream had started. Nothing was saved |

A line `: ping` is sent after 15 seconds without an event; ignore it.

**Order.** Any number of `token` and `slot_update` events in any order, then exactly one `done` or `error`, then the stream ends. The server first understands the answer and then writes the reply (design 4.2), so a `slot_update` normally comes before the first `token`; if that costs too much time (D-115) the facts arrive after the words, just before `done`. **Do not depend on the order.**

**Everything in a stream is provisional until `done`.** A `slot_update` is not stored until the turn is. The screen keeps the facts and the text aside, and applies them when `done` arrives. A stream that ends with neither `done` nor `error` (the connection dropped) is **incomplete**: discard the text and the facts, show "try again", and send the same request again **with the same `Idempotency-Key`**. A clarifying turn has no `slot_update` and an unchanged `next_slot`: the coach asked again instead of guessing.

**Client rules.**
- Wait up to **30 seconds** for the first byte (a `: ping` counts) and up to **60 seconds** for the whole turn, then treat the stream as dropped. The goal is the first token in under 2 seconds at the 95th percentile (NF-FC-009); the reasoning tier has been slower (D-115), which is what the heartbeat is for.
- Closing the connection (leaving the screen, pressing stop) cancels the upstream Gemini call. Nothing is saved.
- Announce a finished reply to a screen reader once, when `done` arrives, not per token.

**A blocked turn (NF-FC-013).** Before the answer is read, the guard looks at `text` (design 4.2). Most turns pass with no model call: an ordinary answer is recognised by the rules. Only a message the rules cannot place costs one Flash-Lite check (`coach/guard.v1`). When the guard blocks a turn, the stream is the usual one with **fixed words** instead of a model's reply: `token` events (a sentence each), then `done`. There is **no `slot_update`**, nothing is read from the message, the stage and `next_slot` are unchanged, and the turn is saved and replayable like any other (`turn_count` goes up by one). The fixed words are in `language`:

| Why the turn was blocked | The reply says |
|---|---|
| Off topic, or the message gives the coach orders (change the rules, show its instructions, take a role) | The coach can only help plan money before leaving; please answer the last question. It does not repeat or discuss the order |
| The worker asks the coach to choose a loan, a lender, an investment, insurance, an app, a bank or a company, or to lend money | The coach cannot recommend loans, investments, apps or companies; then the same line as above |
| The worker, or someone close, seems in danger (hurt, threatened, held, passport or papers taken, no food, talk of dying) | A referral: sorry; talk to someone you trust; contact your embassy or consulate, or a support group for migrant workers; call the local emergency number if in danger now; the money plan waits. **No organisation is named and no phone number is given**: the repository has no sourced contact data |

A worker telling the coach about their own loan or bank ("I owe my agent 3000 SGD") is an answer, not a request, and is never blocked. The wording is the same for everyone (`backend/app/services/coach/guard_texts.py`); a screen need not tell a blocked turn from any other, and there is no new field in `done` (open point 6). If the check itself fails (Gemini busy), the turn fails before the stream like any other Gemini failure: `503`, nothing saved, the worker sends it again.

**A reply that recommends a product ends in `error`.** The coach's own reply is checked when it is complete. If it recommends a loan, an investment or an app, the stream ends with an `error` event (`ai_bad_response`) and **nothing is saved**, so the screen, which treats text as provisional until `done`, discards it and offers "try again". The decision of every turn is logged as `coach_guard action=... reason=... source=...`, never with the text.

**Failures before the first byte** are ordinary HTTP errors with the envelope and the real status; after it they are an `error` event.

| Status | `code` | When |
|---|---|---|
| `200` | | The stream |
| `400` | `idempotency_key_invalid` | The key is missing or not 16 to 64 characters from `A-Za-z0-9_-` |
| `401`, `404` | `unauthenticated`, `not_found` | No token; flag off, no such session or not the caller's |
| `409` | `session_not_active` | The session is `completed` or `abandoned`. The screen offers a new interview |
| `409` | `session_full` | The transcript already holds 200 messages. The screen offers `restart` |
| `409` | `turn_in_progress` | Another turn of this session is still running (a second tab, or a double tap with a new key). Sends `Retry-After: 2` |
| `409` | `request_in_progress` | This key is still being processed. Sends `Retry-After: 2` |
| `422` | `validation_failed` | Empty or over-long `text`, `text` omitted when it may not be, a language outside the six. `details` names the field |
| `422` | `idempotency_key_reused` | The key was used with a different body |
| `429` | `rate_limited` | More than 10 turns a minute. Sends `Retry-After` and `X-RateLimit-*` |
| `502`, `503`, `504` | `ai_bad_response`, `ai_busy` or `ai_unavailable`, `ai_timeout` | Gemini failed before any reply started. The session is intact |

**How the key is kept (closes D-126).** The session document carries `last_turn`: `{key, body_hash, state, started_at, turn}` (`coach.md`), written when a turn starts and finished when it is saved. No other collection is needed, and the key goes away with the session.
- Same key, same body, turn finished: the stream is **replayed** with `Idempotency-Replayed: true`. It is rebuilt from the transcript and the slots stamped with that turn; the server may merge the text into fewer `token` events. Nothing runs again.
- Same key, turn still running: `409 request_in_progress`. Same key, a different body hash (SHA-256 of the JSON with sorted keys): `422 idempotency_key_reused`.
- A different key while a turn runs: `409 turn_in_progress`. A turn that has been running more than 90 seconds is treated as failed, so a crashed server never locks a session.
- Only the **latest** turn can be replayed, and only for 24 hours (conventions, section 5). A client never sends the key of an earlier turn.

Samples (streams, `docs/mocks/coach/`): `turn-01-start.sse` (the coach speaks first), `turn-02-answer.sse` (a fact, a heartbeat, the next question), `turn-03-answer-hindi.sse`, `turn-04-clarify.sse` (the currency is missing, so nothing is stored), `turn-05-review.sse` (the last answer: stage `review`), `turn-06-late-slot-update.sse` (facts after the words), `turn-07-redirect.sse` (off topic; the real wording is the fixed text of NF-FC-013, which does not repeat the question, D-225), `turn-08-language-switch.sse` (no `text`), `turn-error-midstream.sse`, `turn-error-dropped.sse` (no terminal event: retry). Refusals: `turn-error-*.json`.

```bash
# the coach speaks first, then the worker answers (-N: do not buffer the stream)
curl -N -X POST http://127.0.0.1:8080/api/v2/coach/sessions/$SESSION_ID/messages \
  -H "Authorization: Bearer $ID_TOKEN" -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" -H "Idempotency-Key: $(uuidgen)" \
  -d '{"language": "en"}'
```

## `POST /api/v2/coach/sessions/{id}/plan`

Make the plan from the confirmed answers. **Request**, `CoachPlanRequest`: `{"language": "hi"}`, the language of the plan and its PDF.

**What happens** (design 4.4): the plan is looked up by the **hash of the answers**. If it exists (in this language too), it is returned and nothing is made. Otherwise the server works out the score, asks Remittance X-Ray for the cheapest provider on the worker's corridor, makes the plan in English, checks that every figure can be worked out from the answers, the cost baselines and the exchange rates (once more if not; if the second try fails too, nothing is stored and the answer is `502 ai_bad_response`), translates it into `language`, makes the PDF, and marks the session `completed`. A plan for a route that is not one of the six corridors has no provider quote.

**Response**, `CoachPlanResponse` (below). **`201`** when the call stored a new plan, **`200`** when the plan already existed (even if this call added a translation). The session must be at stage `plan` (or already `completed`, which returns its plan); a plan is made once per set of answers.

**Time.** The reasoning tier writes the plan: 20 to 40 seconds, and a translation and a PDF on top. **The client allows 90 seconds and shows progress**; a slow answer is not a failure. A second request for the same answers while the first is still running is `409 request_in_progress` with `Retry-After: 5`: keep the progress state and ask again.

| Status | `code` | When |
|---|---|---|
| `201`, `200` | | A new plan; the stored plan |
| `401`, `404` | `unauthenticated`, `not_found` | No token; flag off, no such session or not the caller's |
| `409` | `plan_not_ready` | The worker has not confirmed their answers (the stage is not `plan`) |
| `409` | `session_not_active` | The session is `abandoned` |
| `409` | `request_in_progress` | The plan for these answers is still being made |
| `422` | `validation_failed` | A language outside the six |
| `429` | `rate_limited` | |
| `502`, `503`, `504` | `ai_bad_response`, `ai_busy` or `ai_unavailable`, `ai_timeout` | Gemini failed, or the sentences failed the check twice. Nothing is stored |
| `503` | `score_unavailable` | The score, so the plan, cannot be worked out now: an exchange rate, the host's cost baseline or the fee rule is missing. `Retry-After: 30`. Nothing is stored (added by NF-FC-012) |

Samples: `plan-01-created.json` (the default), `plan-02-created-no-debt.json`, `plan-03-already-exists.json`, `plan-error-*.json`.

## `GET /api/v2/coach/plans/{id}`

A stored plan. Query `language` (default `en`). If the plan is not yet stored in that language it is translated now and kept, so the call can take a few seconds the first time and uses the Gemini budget; reading never changes the plan itself. The worker's session may be long gone: the plan does not need it. Errors: `401`, `404 not_found` (flag off, no such plan or not the caller's), `422` (a language outside the six), `429`, and the `ai_*` codes when a translation was needed. Samples: `plan-get-01-english.json`, `plan-get-02-hindi.json`, `plan-get-03-no-debt.json`, `plan-get-error-not-found.json`.

**`CoachPlanResponse`:**

| Field | Type | Meaning |
|---|---|---|
| `id` | string | 20 hex characters: the start of the hash of the answers (below) |
| `session_id` | string or `null` | `null` once the session has expired |
| `language`, `available_languages` | string, array | The language of `plan`, and the languages already stored (`en` always) |
| `host_country`, `home_country`, `corridor_id`, `departure_date` | | `home_country` and `corridor_id` are absent when unknown or not one of the six; `departure_date` when the worker did not say |
| `reporting_currency` | string | The host country's currency (`SGD`, `KRW`, `MYR`, `JPY`, `HKD`, `AUD`). Every figure is in it, except what arrives at home |
| `slots` | object | The answers the plan was made from, by slot name, as bare values |
| `rates_as_of` | timestamp | The oldest exchange rate or provider quote used; when none was used, the time the plan was made. The screen says "rates as of ..." |
| `score` | object | The score (below), as it was when the plan was made. **This one counts**: it can differ from the session's by the move of an exchange rate in between (open point 1) |
| `plan` | object | See below |
| `created_at` | timestamp | |

**`plan`** (`CoachPlan`). Written in English once, then translated; **every sentence is text, every figure is `{amount, currency}`**, and the translation leaves all numbers, currency codes and dates as they are (NF-FC-014 checks it).

| Field | Meaning |
|---|---|
| `summary` | Two or three sentences |
| `monthly_budget` | One normal month after arrival: `income`; `costs` (lines `{id, amount}` from the cost baselines: `accommodation`, `food`, `transport`, `phone_data`, `deductions`); `goals` (`remittance`, `debt_payment`, `emergency_fund`); `left_over` (**exactly** income minus costs minus goals as shown, negative is a gap); `setup_costs` (one-off costs of the first month, not part of the lines) |
| `remittance` | `corridor_id` (or `null`); `monthly_amount`; `provider` (or `null` without a corridor): `{slug, name, fee, receives, fx_rate, quoted_at}`, where the fee is taken from the amount and `receives` is what arrives at home; `schedule`: `{week, amount}` for the weeks to send. The screen opens Remittance X-Ray with the corridor and the amount (NF-FC-021) |
| `debt` | `null` when the worker owes nothing; else `outstanding`, `monthly_payment`, `months_to_clear` (`null` if the payment does not cover the interest) |
| `emergency_fund` | `target` (`months_of_costs` times the monthly costs), `monthly_saving`, `weeks_to_target` |
| `weeks` | Exactly 13 entries, weeks 1 to 13 in order: `{week, title, actions}`, one to four actions |
| `warnings` | At most 8: `{id, severity, text}`, severity `info`, `warning` or `urgent`; the id (`fee_above_legal_limit`, `high_interest_debt`, ...) is open |
| `checklist` | 3 to 10 items `{id, text}`. The ticks are kept on the phone, not here |
| `disclaimer` | The "not professional financial advice" note, in the plan's language. It is on every plan and in the PDF |

New ids of `costs`, `goals`, `warnings` and `checklist` are not breaking changes: a screen shows a neutral label for an id it does not know.

**The hash of the answers.** `slot_hash` (`backend/app/schemas/coach_plan.py`) is the SHA-256 of the answers' values only, written as `CoachProfile` writes them (sorted keys, no spaces, UTF-8, unanswered slots left out). Confirming an answer again, or answering in another language, gives the same hash, so the same plan. Changing a value makes a new plan; the old one stays until the account is deleted.

## `GET /api/v2/coach/plans/{id}.pdf`

The plan as a file. Query `language` (default `en`). **Response `200`**: the bytes, `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="nomadfinance-plan-<language>.pdf"`, `Cache-Control: private, no-store`. The PDF holds the score, the plan and the disclaimer, in that language, with the same figures as the JSON. It is made on first request in a language and then kept in Cloud Storage; that first request can take a few seconds and uses the Gemini budget when it first needs a translation.

The bytes come **through the API**, with the bearer token, and not as a signed link (as the Financial Identity export does): the bucket has no CORS policy, so the app could not read a signed link's bytes to share the file (`NF-P3-018`), and a link anyone can open would be a link to a worker's debts (open point 7). Errors: `401`, `404 not_found`, `422`, `429`, `502`, `503`, `504`, as for the plan; they are JSON, not a PDF.

## `GET /api/v2/coach/overview`

What the dashboard card (NF-FC-022) needs to say Start, Resume or View plan, without creating anything. **Response `200`**, `CoachOverview`:

| Field | Meaning |
|---|---|
| `session` | The active session: `{id, stage, language, turn_count, last_active}`, or `null` |
| `plan` | The newest plan: `{id, created_at, score_total, band, departure_date}`, or `null` |

Both can be present: a worker with a plan who started a new interview. Errors: `401`, `404` (flag off), `429`. Samples: `overview-01-active-session.json` (the default), `-02-plan-only`, `-03-session-and-plan`, `-04-empty`.

## The score

`score` is pure arithmetic on the answers, the exchange rates and the legal fee cap: no model (NF-FC-006, -011). The formula, weights, bands and a worked example are in [`docs/features/coach-scoring.md`](../features/coach-scoring.md).

| Field | Meaning |
|---|---|
| `total` | Whole number, 0 to 100 |
| `band` | An open id, translated by the screen: `needs_work` (0 to 39), `getting_ready` (40 to 69) and `well_prepared` (70 to 100), with a floor rule (a factor under 20 points keeps the band at `getting_ready` or below). Fixed by the rubric, [`docs/features/coach-scoring.md`](../features/coach-scoring.md) |
| `factors` | The five, once each: `debt_to_income`, `emergency_buffer`, `remittance_ratio`, `recruitment_fee_vs_cap`, `banked_status`. Each is `{id, value, score, weight}`: the measured figure (`null` if it cannot be measured), its points out of 100 and its weight. The samples' weights add up to 1 and `total` is the rounded weighted sum |
| `rubric_version` | Raises when the rubric changes |

The words that explain a factor ("what this means", "how to improve") are in the screens' translations, keyed by factor id and band; the API sends none (NF-FC-020).

## Error codes added by this feature

The conventions allow a feature its own codes (section 2). These do not reuse any code above for another meaning.

| Status | `code` | Used by |
|---|---|---|
| 409 | `session_not_active` | messages, plan |
| 409 | `session_full` | messages |
| 409 | `turn_in_progress` | messages |
| 409 | `plan_not_ready` | plan |

The plan route also answers `409 request_in_progress` when the plan for the same answers is still being made. That is the conventions' code with its meaning (the same request is still being processed), without a key: the answers are the key.

## Changing this contract

The rules of the conventions (section 6) apply. Adding a field to a response, an optional request field, a route, a new value of an open id (`band`, a budget line, a warning), or a new event data field is not breaking. Removing or renaming a field, changing a type, making an optional request field required, or tightening a limit is. A change updates this file, `backend/app/schemas/coach_session.py` or `coach_plan.py`, and the mocks together: the drift test (`backend/tests/unit/test_coach_mocks.py`) fails until they agree.

## Open points for the implementing tasks

| # | Point | Owner |
|---|---|---|
| 1 | The score at `review` and the score in the plan are worked out at different times, so an exchange rate can move them apart. Freezing the score on the session when it reaches `review` and copying it into the plan would make them equal. **NF-FC-012:** the plan stores the score it was made with; the session's is still worked out on each read (D-217) | NF-FC-012 |
| 2 | The band ids and cut-offs of the samples are now the rubric's (NF-FC-006, `docs/features/coach-scoring.md`). The factor points and totals in the samples are still placeholders and differ from the rubric by up to 10 points, always within the same band (D-200) | NF-FC-011 |
| 3 | Answers from the chips and fields are sent as text and understood again. A structured `answer` field (`{slot, value}`) would skip that and could be added later without breaking anything | NF-FC-010, NF-FC-017 |
| 4 | Check-in routes (answering the three questions on day 30, 60 and 90) are specified when the reminder job is: new routes, and possibly a `checkins` field on the plan | NF-FC-016, NF-FC-022 |
| 5 | A salary taken from a contract (NF-FC-015) enters as a slot with `source: "contract_prefill"` after a confirmation turn. There is no route for it | NF-FC-015 |
| 6 | **Decided in NF-FC-013: text only.** A worker in distress gets fixed referral text in the stream (see "A blocked turn"). No structured referral card was added; an optional field of `done` can be added later without breaking anything, once the team has sourced organisations and numbers to put in it (D-224) | done |
| 7 | NF-FC-014 says "return a signed URL"; this contract returns the stored file through the API. **Decided in NF-FC-014: through the API, as specified** (the bucket has no CORS policy, and a signed link would be a link to a worker's debts); the tracker's wording is out of date | NF-FC-014 |
| 8 | **Resolved by NF-FC-008.** A worker who answered "not sure" to the departure date is kept apart from one never asked by `declined_slots` on the stored session (`coach.md`); the contract still shows only `next_slot` | done |
| 9 | NPR and BDT have no exchange rate yet (D-170), so a fee or debt in those currencies leaves `score` empty at `review` until the rates exist or the coach asks the worker to restate the amount | NF-FC-011, NF-FC-006 |
| 10 | The streams in `docs/mocks/coach/` are written to this contract, byte for byte, **not captured** from a running server (there is none). Replace or add to them with a capture when NF-FC-009 runs on staging | NF-FC-009 |
