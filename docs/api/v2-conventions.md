# API v2 conventions

Rules every endpoint under `/api/v2` follows. Feature contracts (coach, scam, partner) cite this file and do not repeat it. Task: NF-F0-002. Design context: `docs/future-scope/design.md`, section 2.2.

**Frozen after NF-F0-002 merges.** Changing a rule here later needs a PR that updates this file, the mocks in `docs/mocks/conventions/` and the handlers in `backend/app/core/errors.py` together, with both other teammates as reviewers.

The v1 reference stays in `docs/api/endpoints.md` (the tracker calls it `docs/api-contract.md`). v1 routes and their `{"detail": "..."}` errors do not change.

## 1. Prefix, layout and what carries over from v1

- All new routes live under `/api/v2/`. `/health` stays unversioned.
- Code layout: `backend/app/api/v2/<feature>.py` with a `router.py` next to `app/api/v1/router.py`, mounted with `prefix="/api/v2"`. The folder is created by the first v2 route (NF-F0-005), not before. Request and response models go in `backend/app/schemas/`, as in v1.
- Unchanged from v1: Firebase ID token as `Authorization: Bearer ...`, the `X-Request-ID` header (sent by the caller or generated, echoed on every response), the rate limits and their `X-RateLimit-*` headers, the request size limit and CORS rules (`docs/api/endpoints.md`, "CORS, rate limits and request size").
- A route behind a feature flag answers `404` with the standard envelope (code `not_found`) when the flag is off (NF-F0-005). A request to an unknown `/api/v2/...` path gets the same answer.

## 2. Error envelope

Every error under `/api/v2` has this JSON body, whatever produced it: a handler, the rate limiter, the request size limit or an uncaught exception.

```json
{
  "code": "validation_failed",
  "message": "The request is not valid.",
  "request_id": "b81e5a62c9d34f0e8a7351c6d2e94f07",
  "details": [{ "field": "body.amount", "issue": "Input should be greater than 0" }]
}
```

| Field | Type | Rule |
|---|---|---|
| `code` | string | Stable snake_case identifier from the table below. Clients branch and translate on it. |
| `message` | string | English text for logs and as a fallback. Never translated, never shown as the only text to a worker. |
| `request_id` | string | Equal to the `X-Request-ID` response header. Show it in "contact support" copy. |
| `details` | list, optional | Only on `validation_failed`: `{field, issue}` per rejected field, at most 20. `field` is a dotted path such as `body.amount`; `issue` says why and **never contains the value that was sent**. |

No stack traces, model names, Gemini messages, document paths or other internals in any field.

### Codes

| Status | `code` | When |
|---|---|---|
| 400 | `bad_request` | Malformed request that is not a validation failure |
| 400 | `invalid_cursor` | Cursor is malformed, expired or belongs to another user |
| 400 | `idempotency_key_invalid` | Key missing where required, or not in the allowed shape |
| 401 | `unauthenticated` | Missing, invalid, expired or revoked token (sends `WWW-Authenticate: Bearer`) |
| 403 | `forbidden` | Signed in but not allowed |
| 404 | `not_found` | Unknown path or resource, or the feature flag is off |
| 405 | `method_not_allowed` | |
| 409 | `request_in_progress` | Same `Idempotency-Key` is still being processed (sends `Retry-After`) |
| 409 | `conflict` | Request conflicts with the resource's current state |
| 410 | `gone` | Route removed after its sunset date |
| 413 | `payload_too_large` | Body over the size limit: 128 KB for a JSON body, 10 MB for a screenshot |
| 422 | `validation_failed` | Body, query or path failed validation; carries `details` |
| 422 | `idempotency_key_reused` | Same key sent with a different request |
| 429 | `rate_limited` | Over a rate limit (sends `Retry-After` and `X-RateLimit-*`) |
| 500 | `internal_error` | Our bug. The cause is in the logs under `request_id` |
| 502 | `ai_bad_response` | Gemini returned empty, blocked or invalid output |
| 503 | `ai_busy` | Gemini quota hit. A per-minute limit or a busy model sends `Retry-After: 30`. A spent **daily** quota, whether Google's or this service's per-feature budget (NF-HR-010), sends the seconds until it resets (midnight US Pacific) and a message that says "try again later". The code is the same, so a client needs no new case |
| 503 | `ai_unavailable` | Gemini unavailable (sends `Retry-After: 30`) |
| 504 | `ai_timeout` | Gemini timed out on every attempt |

A feature contract may add codes for its own cases (for example `scam_text_too_long`) in its own table; it may not reuse a code above for a different meaning. **A client that meets a code it does not know falls back to the HTTP status.** Adding a code is therefore not a breaking change; changing what a code means is.

The frontend picks its translated message by `code`, then by status. `message` is the last fallback (this closes D-10 for v2).

## 3. Cursor pagination

Applies to every endpoint that returns a list that can grow (check history, plans, notifications). Lists that are bounded by design (the six corridors, the six languages) are returned whole.

Request query parameters:

| Parameter | Type | Default | Rule |
|---|---|---|---|
| `limit` | integer | 20 | 1 to 100. Out of range is `validation_failed`, not silently clamped |
| `cursor` | string | none | Opaque, at most 512 characters. Omit for the first page |

Response:

```json
{ "items": [ ... ], "next_cursor": "eyJ0IjoiMjAyNi0xMC0xOVQwNzo1NTowMloifQ" }
```

- `next_cursor` is `null` on the last page. A page may hold fewer than `limit` items; only `next_cursor: null` means the end.
- The order is fixed per endpoint and stated in its contract (newest first unless said otherwise). New items inserted while paging do not cause repeats or gaps in what the client has already passed.
- No total count: Firestore has no cheap count. A contract that needs one adds its own field.
- Clients treat the cursor as a black box and never build one. The server validates it, binds it to the caller and the query, and answers `400 invalid_cursor` for any cursor it did not issue to this user. A cursor must never be able to widen what the caller is allowed to read.

## 4. Server-Sent Events (streaming)

Streaming endpoints are `POST` (they carry a body and a bearer token), so the browser's `EventSource` cannot be used: it can do neither. The frontend reads the response with `fetch` and a stream reader.

Response headers: `Content-Type: text/event-stream; charset=utf-8`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`. The request sends `Accept: text/event-stream`.

Wire format: standard SSE. An event is an optional `event:` line, a `data:` line holding **one line of JSON**, and a blank line. No `id:` or `retry:` fields: streams are not resumed, they are retried (below).

| `event` | `data` | Meaning |
|---|---|---|
| `token` | `{"text": "..."}` | A piece of the reply, appended in order |
| `slot_update` | `{"slot": "...", "value": ...}` | The server understood a fact and stored it. `value` is any JSON value; slot names come from the feature contract |
| `done` | object, defined by the endpoint | Terminal. The turn is complete and saved |
| `error` | the error envelope of section 2 (no `details`) | Terminal. The turn failed after the stream had started |

**Heartbeat.** When 15 seconds pass with no event, the server writes `: ping` followed by a blank line. A line starting with `:` is a comment: clients ignore it. It keeps proxies and the phone's radio from closing an idle connection.

**Order.** Zero or more `token` and `slot_update` events in any order, then exactly one `done` or `error`, then the server closes the stream. Nothing follows a terminal event.

**Errors.** A failure *before* the first byte (auth, validation, rate limit, flag off, a Gemini failure before any output) is an ordinary HTTP error with the envelope and its real status. A failure *after* the stream has started cannot change the status (it is already 200), so it is an `error` event.

**Client rules.**
- A message is final only after `done`. A stream that ends with neither `done` nor `error` (dropped connection) is incomplete: discard the partial text, show a retry, and send the same request again **with the same `Idempotency-Key`** (turn requests require one). The server then returns the stored result instead of running the turn twice.
- Closing the connection (navigating away, pressing stop) must cancel the upstream Gemini call on the server.
- Announce a streamed message to screen readers once, when `done` arrives (NF-FC-023), not per token.

**Replay.** A retried turn whose first attempt completed is answered from storage: the same events, with `Idempotency-Replayed: true`. The server may merge the stored text into fewer `token` events.

Samples: `docs/mocks/conventions/sse-stream-done.sse`, `sse-stream-error.sse`.

## 5. Idempotency

`Idempotency-Key: <key>` makes a `POST` safe to send twice. It matters here because workers' connections drop mid-request, a repeated Gemini call costs quota, and a repeated plan or report must not create a second record.

- **Which endpoints.** Each feature contract states `required`, `optional` or `not used` for every route. Default: `required` for a `POST` that creates a record or spends Gemini quota. `GET`, `PUT` and `DELETE` do not use it. A missing key where required is `400 idempotency_key_invalid`.
- **Key shape.** 16 to 64 characters from `A-Za-z0-9_-`. Generate a UUID v4 per user action and reuse it for every retry of that action; a new action gets a new key.
- **Scope.** A key is unique per user, method and path. The same key on another path is a different key.
- **Same key, same body.** If the first request finished with a `2xx`, the stored status and body are returned again with `Idempotency-Replayed: true`. `X-Request-ID` is the new request's own id. Error responses are not stored, so a retry after an error runs again.
- **Same key, different body.** `422 idempotency_key_reused`. "Same body" means the same SHA-256 of the body (JSON with keys sorted).
- **Same key, first request still running.** `409 request_in_progress` with `Retry-After: 2`. The client waits and retries with the same key.
- **Retention.** 24 hours, then the key is forgotten. Where the keys are stored is decided in NF-F0-003, not here.
- Some operations are idempotent by their own nature and the contract says which key makes them so: plan by slot hash, report by check id, check-in by milestone (design section 9). The header is still accepted on them.

Sample: `docs/mocks/conventions/idempotency-exchange.json`.

## 6. Versioning and deprecation

- The version is the path prefix (`/api/v2`). There are no minor versions in the path.
- **Not breaking** (done without notice, and clients must tolerate them): a new endpoint, a new optional request field or query parameter, a new response field, a new error code (section 2), a new event type on a stream that is documented as extensible, a new value of a field documented as open.
- **Breaking** (needs a new version or the deprecation steps below): removing or renaming a field, changing a field's type or meaning, making an optional request field required, changing a code's meaning or an endpoint's status code, changing the order or format of events, and tightening a limit.
- **Deprecating a route or field** within v2:
  1. Announce it in the PR and in the feature's contract, with the replacement.
  2. From that day every response of the route carries `Deprecation: @<unix-seconds>` (RFC 9745), `Sunset: <HTTP-date>` (RFC 8594) and `Link: <replacement>; rel="deprecation"`.
  3. At least **90 days** between the `Deprecation` date and the `Sunset` date. The frontend stops calling it before the sunset.
  4. After the sunset date the route answers `410 gone` for another 90 days, then `404`.
- **v1.** v1 stays served alongside v2. Nothing in v2 requires a v1 route to change, and no v1 sunset is planned. A v1 sunset would follow the same steps.
- Every change to this file is listed below.

Sample: `docs/mocks/conventions/deprecation-headers.json`.

## 7. For the people building a v2 route

- **Raise errors, do not build them.** `raise HTTPException(404, "Not found")` becomes the envelope on its own. Use `ApiError(status, code, message)` (`app.core.errors`) when the status is not enough, for example `ApiError(409, "request_in_progress", "...", headers={"Retry-After": "2"})`.
- **Gemini errors** raised by the client (`GeminiError` and subclasses) are mapped to `ai_*` codes by the same module; endpoints do not catch them just to rewrite them.
- **Validation** is Pydantic's. Do not write your own 422.
- **Only `/api/v2` paths change.** The handlers pass every other path to FastAPI's own v1 behaviour, so a v1 route's errors are byte-for-byte what they were.
- **CORS.** The first v2 route that needs them must add `Idempotency-Key` to `allow_headers`, and `Idempotency-Replayed`, `Deprecation` and `Sunset` to `expose_headers`, in `app/main.py` (tracked as D-98). Browsers hide response headers that are not exposed.
- **Tests.** Assert the envelope, not just the status: `code`, `request_id` equal to the `X-Request-ID` header, and that no value from the request appears in the body.

## Changelog

| Date | Change | Task |
|---|---|---|
| 2026-10-06 | First version: prefix, error envelope, pagination, SSE, idempotency, versioning | NF-F0-002 |
| 2026-10-11 | Checked against the code. Every code the backend raises is in the tables of this page or of the two feature contracts; `ai_busy` also covers a spent daily quota (NF-HR-010, already in the table); the 128 KB JSON cap is in `endpoints.md`. No convention changed | NF-HR-013 |
