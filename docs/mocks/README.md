# Mocks

Sample requests and responses for the API, written before the endpoint exists. Frontend work and MSW handlers use them as the source of truth until the real endpoint lands; the backend must produce the same shape.

| Folder | Owner task | What it shows |
|---|---|---|
| `conventions/` | NF-F0-002 | One sample per `/api/v2` convention (`docs/api/v2-conventions.md`) |
| `flags/` | NF-F0-014 | `GET /api/v2/flags`: both modules off, the Coach on, the Scam Analyzer on, and the 401 envelope |
| `scam/` | NF-SA-002 | The Scam Analyzer API (`docs/api/v2-scam.md`): a check at each risk level and a benign one, the history, one stored check, a report, and every refusal |
| `coach/` | NF-FC-002 | The Financial Coach API (`docs/api/v2-coach.md`): a session at every stage, the three score bands, plans in English and Hindi, ten streamed turns, the dashboard overview, the check-in answers, and every refusal |

## `scam/`

Written for NF-SA-002 and checked against the backend's models by `backend/tests/unit/test_scam_mocks.py`: shape, taxonomy ids, redaction, indicator hashes and agreement between the history, the detail and the analyze answer. The numbered names make the default answer of a route the first by name: **the high-risk example is what the analyze route returns unless a test swaps another in**. The sample messages and numbers are invented (`.example` is a reserved name that never resolves).

| File | Request | Shows |
|---|---|---|
| `analyze-01-high-risk.json` | `POST /api/v2/scam/analyze` | An illegal recruitment fee, in Hindi, on SG-IN, with a number reported 5 times (default) |
| `analyze-02-medium-risk.json` | same | A loan-app threat in Tagalog, explained in English |
| `analyze-03-low-risk.json` | same | A prize message in Indonesian that asks for nothing yet: a scam, low risk |
| `analyze-04-benign.json` | same | Not a scam: a reassurance and a tip instead of next steps |
| `analyze-05-cached.json` | same | The high-risk message sent again: `cached` true |
| `analyze-06-explainer-unavailable.json` | same | Verdict without the explainer: `explainer` null, `explainer_status` unavailable |
| `analyze-error-text-too-long.json` | same | 422, over 4,000 characters |
| `analyze-error-unsupported-media-type.json` | same | 415 |
| `analyze-error-image-unreadable.json` | same | 422, no text in the screenshot |
| `analyze-error-rate-limited.json` | same | 429 with the hourly budget headers |
| `checks-list-01-first-page.json`, `-02-last-page`, `-03-empty` | `GET /api/v2/scam/checks` | History, newest first, with and without a next page |
| `check-01-high-risk.json` to `check-04-benign.json` | `GET /api/v2/scam/checks/k_01` to `k_04` | The four stored checks |
| `check-error-not-found.json` | `GET /api/v2/scam/checks/k_missing` | 404 |
| `report-01-created.json` | `POST /api/v2/scam/checks/k_01/report` | 201, with the Radar profile to link to (default) |
| `report-02-already-reported.json` | same | 200, a second tap |
| `report-error-validation.json` | same | 422, an indicator that is not in the check |
| `report-error-not-a-scam.json` | `POST /api/v2/scam/checks/k_04/report` | 409 |

The frontend serves them through `frontend/src/mocks/` (`scam.msw.test.ts` is the working example).

## `coach/`

Written for NF-FC-002 and checked against the backend's models by `backend/tests/unit/test_coach_mocks.py`: shape, the next question against the question bank, redaction of the transcript, the plan id against the real hash of the answers, the plan's arithmetic, the Hindi plan's numbers against the English one's, and agreement between the sessions, the overview and the streams. Every person, message and number is invented. Three workers appear: **A** from India to Australia (care work, a debt at 3% a month, the middle band; ids `s_03`, `s_04`, `s_07`), **B** from the Philippines to Singapore (a heavy debt, the lowest band, did not say when she leaves; `s_05`) and **C** from Nepal to South Korea (no debt, the highest band, not one of the six corridors; `s_06`).

**The streams are written to the contract byte for byte; they were not captured from a running server**, because none exists yet. They are `.sse` files: the raw body of the response. A test replays one with `sseHandler(requestLine, "coach/<file>")`.

The turn route has no default answer: a test always picks a stream. The JSON refusals declared on the same path (`turn-error-*.json`) are what a request gets if it does not.

| File | Request | Shows |
|---|---|---|
| `sessions-create-01-new.json` | `POST /api/v2/coach/sessions` | 201, a new English session at the first question, no messages (default) |
| `sessions-create-02-resumed.json` | same | 200, the open session comes back: Hindi, debt stage, the transcript so far |
| `session-01-new.json` to `session-07-completed.json` | `GET /api/v2/coach/sessions/s_01` to `s_07` | New; Hindi in the debt stage; the review (two answers unconfirmed, a salary from a contract); stage `plan` at the middle, lowest and highest band; completed |
| `session-error-not-found.json` | `GET /api/v2/coach/sessions/s_missing` | 404 |
| `turn-error-session-not-active.json` | `POST /api/v2/coach/sessions/s_07/messages` | 409, the session is completed |
| `turn-error-in-progress.json` | `POST /api/v2/coach/sessions/s_02/messages` | 409 with `Retry-After`, another turn is running |
| `turn-error-session-full.json` | same | 409, 200 messages |
| `turn-error-text-too-long.json` | `POST /api/v2/coach/sessions/s_01/messages` | 422, over 1,000 characters |
| `turn-error-rate-limited.json` | same | 429, 10 a minute |
| `turn-error-ai-busy.json` | same | 503 before any stream started |
| `plan-01-created.json` | `POST /api/v2/coach/sessions/s_04/plan` | 201, worker A's plan in English (default) |
| `plan-02-created-no-debt.json` | `POST /api/v2/coach/sessions/s_06/plan` | 201, worker C: no debt, no provider quote |
| `plan-03-already-exists.json` | `POST /api/v2/coach/sessions/s_07/plan` | 200, the stored plan |
| `plan-error-not-ready.json` | `POST /api/v2/coach/sessions/s_02/plan` | 409, the answers are not confirmed |
| `plan-error-in-progress.json`, `plan-error-ai-bad-response.json` | `POST /api/v2/coach/sessions/s_04/plan` | 409 with `Retry-After`; 502, the figures failed the check twice |
| `plan-get-01-english.json` | `GET /api/v2/coach/plans/5a202702c922fc9b4fcf` | Worker A's plan, English (default) |
| `plan-get-02-hindi.json` | `GET /api/v2/coach/plans/5a202702c922fc9b4fcf?language=hi` | The same plan in Hindi, every figure unchanged |
| `plan-get-03-no-debt.json` | `GET /api/v2/coach/plans/e75fa9f24fd3159ad83d` | Worker C's plan |
| `plan-get-error-not-found.json` | `GET /api/v2/coach/plans/0123456789abcdef0123` | 404 |
| `overview-01-active-session.json`, `-02-plan-only`, `-03-session-and-plan`, `-04-empty` | `GET /api/v2/coach/overview` | The four states of the dashboard card: Resume (default), View plan, both, Start |
| `checkin-01-answered.json`, `-02-already-answered` | `PUT /api/v2/coach/plans/5a202702c922fc9b4fcf/checkins/d30` | 200: the first answers stored (default); the same milestone again, the first answers back with `already_answered: true` |
| `checkin-error-not-due.json`, `-error-not-found` | `PUT .../checkins/d60`; `PUT /api/v2/coach/plans/0123456789abcdef0123/checkins/d30` | 409 `checkin_not_due` (the day has not come); the same 404 for a plan that is missing or not the caller's |

| Stream | Request to replay it on | Shows |
|---|---|---|
| `turn-01-start.sse` | `POST /api/v2/coach/sessions/s_01/messages` | The coach speaks first (the request has no `text`) |
| `turn-02-answer.sse` | same | A fact is understood (`slot_update`), a heartbeat while the reply is slow, then the next question |
| `turn-03-answer-hindi.sse` | `POST /api/v2/coach/sessions/s_02/messages` | The same in Hindi, with the amount in rupees |
| `turn-04-clarify.sse` | same | The currency is missing: no `slot_update`, the same `next_slot` |
| `turn-05-review.sse` | `POST /api/v2/coach/sessions/s_03/messages` | The last answer: stage `review`, no next slot; the text is the last message of `session-03-review.json` |
| `turn-06-late-slot-update.sse` | `POST /api/v2/coach/sessions/s_01/messages` | The fact arrives after the words (design 4.2 fallback) |
| `turn-07-redirect.sse` | same | An off-topic question is answered with a redirect, nothing stored |
| `turn-08-language-switch.sse` | `POST /api/v2/coach/sessions/s_02/messages` | The request has no `text` and a new language: the current question again in Hindi |
| `turn-error-midstream.sse` | `POST /api/v2/coach/sessions/s_01/messages` | Words, then an `error` event (`ai_timeout`) |
| `turn-error-dropped.sse` | same | Words and then nothing: no `done`, no `error`. The client must retry with the same key |

The plan's PDF has no mock yet (D-179): the loader reads JSON and `.sse` only.

## `conventions/`

| File | Convention | Notes |
|---|---|---|
| `error-not-found.json` | Error envelope | Also what a flag-off route returns |
| `error-validation-failed.json` | Error envelope with `details` | 422 only |
| `error-rate-limited.json` | Error envelope + rate-limit headers | |
| `pagination-page.json` | Cursor pagination | A middle page and the last page |
| `sse-stream-done.sse` | SSE format | A complete turn: heartbeat, `token`, `slot_update`, `done`. Slot name and values are illustrative; NF-FC-001 and NF-FC-002 fix the real ones |
| `sse-stream-error.sse` | SSE format | A stream that fails after it started: `error`, then the stream ends |
| `idempotency-exchange.json` | `Idempotency-Key` | First request, replay, reuse with a different body, in flight, missing key |
| `deprecation-headers.json` | Versioning and deprecation | Headers before the sunset date and the 410 after it |

Item fields in these files (`id`, `label`) are placeholders for the shape, not a real resource. Every sample is synthetic. Samples that need a corridor or amount use Australia as the host country.

`.sse` files are the raw bytes of the response body: a blank line ends each event, and a line starting with `:` is a heartbeat comment. An MSW handler can return the file as a `text/event-stream` body.

## File format and how the tests use it (NF-F0-014)

A JSON mock is one response to one request:

```json
{
  "description": "What this mock is for, in a sentence (not used by code).",
  "request": "GET /api/v2/flags",
  "status": 200,
  "headers": { "X-Request-ID": "..." },
  "body": { "coach": false, "scam": false }
}
```

| Key | Rule |
|---|---|
| `request` | `METHOD /path`, optionally with a query string (the handler matches the path only). A mock without one fits any route and is used by name, for example the error envelopes |
| `status` | Required when `request` is present |
| `headers`, `body` | Optional. No `body` sends an empty response |

A file with another shape, such as `idempotency-exchange.json` (a list of steps), is documentation of a flow, not one response, and gets no handler.

**Frontend tests.** `frontend/src/mocks/` turns these files into MSW handlers, so a test of a screen or hook gets the same answers the backend contract promises, and a changed mock reaches the tests on their next run. A test file opts in:

```ts
import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";

setupMockServer();                                         // once, at the top of the file
server.use(handlerForMock("flags/flags-coach-on.json"));   // inside a test: pick another answer
```

When several mocks declare the same request (the three `flags` mocks do), the first by file name is the default and a test swaps in another with `server.use(...)`. `sseHandler("POST /api/v2/...", "conventions/sse-stream-done.sse")` replays a stream. A request no handler matches fails the test. A working example: `frontend/src/hooks/useFeatureFlags.msw.test.tsx`.

**Backend.** `backend/tests/unit/test_flags_mocks.py` checks that each `flags/` mock parses as the real response model, so a mock cannot drift from the backend. The contract tasks that added a folder (NF-SA-002 for `scam/`, NF-FC-002 for `coach/`) added the same kind of check for it.
