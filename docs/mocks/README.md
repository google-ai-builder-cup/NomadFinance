# Mocks

Sample requests and responses for the API, written before the endpoint exists. Frontend work and MSW handlers use them as the source of truth until the real endpoint lands; the backend must produce the same shape.

| Folder | Owner task | What it shows |
|---|---|---|
| `conventions/` | NF-F0-002 | One sample per `/api/v2` convention (`docs/api/v2-conventions.md`) |

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
