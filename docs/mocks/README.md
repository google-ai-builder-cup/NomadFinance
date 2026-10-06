# Mocks

Sample requests and responses for the API, written before the endpoint exists. Frontend work and MSW handlers use them as the source of truth until the real endpoint lands; the backend must produce the same shape.

| Folder | Owner task | What it shows |
|---|---|---|
| `conventions/` | NF-F0-002 | One sample per `/api/v2` convention (`docs/api/v2-conventions.md`) |
| `flags/` | NF-F0-014 | `GET /api/v2/flags`: both modules off, the Coach on, the Scam Analyzer on, and the 401 envelope |

Feature mocks (coach, scam) get their own folder, added by their contract tasks (NF-FC-002, NF-SA-002).

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

**Backend.** `backend/tests/unit/test_flags_mocks.py` checks that each `flags/` mock parses as the real response model, so a mock cannot drift from the backend. The contract task that adds a new folder (NF-FC-002, NF-SA-002) adds the same kind of check for it.
