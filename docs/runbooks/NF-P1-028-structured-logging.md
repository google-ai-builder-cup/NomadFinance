# NF-P1-028: Structured logging

Every backend request gets a request ID and one log line with its status and latency. On
Cloud Run the logs are JSON, so Cloud Logging can filter and count them by field.

## What you get

**One line per request**, written when the response is done (`app/core/middleware.py`):

```json
{"severity": "INFO", "message": "request_completed method=GET path=/api/v1/nope status=404 latency_ms=2.6",
 "timestamp": "2026-09-25T21:34:20.545555+00:00", "logger": "app.core.middleware",
 "request_id": "5a78542e22f54df7a1f6b87be4e2b56f",
 "logging.googleapis.com/trace": "projects/nomadfinance-prod/traces/105445aa7843bc8bf206b12000100000",
 "method": "GET", "path": "/api/v1/nope", "status": 404, "latency_ms": 2.6}
```

- `request_id`: taken from the caller's `X-Request-ID` header when it is 8 to 64 characters
  of `A-Z a-z 0-9 . _ -`, otherwise a new UUID. Always returned in the `X-Request-ID`
  response header, so a user can quote it in a bug report.
- `user_hash`: 16 hex characters of SHA-256 of the Firebase uid, added by
  `get_current_user` once the token is verified. Absent on public endpoints, unauthenticated
  calls and Cloud Scheduler calls.
- `logging.googleapis.com/trace`: built from Cloud Run's `X-Cloud-Trace-Context` header, so
  the line links to the Cloud Run request log in the Logs Explorer.
- `latency_ms`: time spent in the whole app for this request.
- Level: `INFO` up to 4xx, `ERROR` for 5xx and unhandled exceptions. `/health` is logged at
  `DEBUG`, so uptime probes stay out of the logs.

**Every other log line written during a request** (Gemini calls, account deletion, FX
lookups) carries the same `request_id` and `user_hash`, and any `extra=` fields, such as
`gemini_usage` with token counts, appear as their own JSON fields.

**Unhandled exceptions** are logged at `ERROR` with the traceback inside `message` (Error
Reporting reads it from there). The client only gets a generic 500 with no details.

## Formats

| `APP_ENV` | Format |
| --- | --- |
| `local` | readable text: `2026-09-26 03:03:35,625 INFO    app.core.middleware: request_completed ... [req=... user=...]` |
| `staging`, `prod` | one JSON object per line on stdout |

`LOG_LEVEL` (default `INFO`) now takes effect; before this task nothing applied it. uvicorn's
own lines go through the same formatter, and its per-request access line is switched off
because `request_completed` replaces it.

## What is never logged

The middleware logs the path only: no query string, headers, cookies or request body. The
raw uid is never logged, only its hash.

The `httpx` and `httpcore` loggers are held at `WARNING`. They log every outgoing URL at
`INFO`, and the CurrencyFreaks API key travels in its query string, so with the root logger at
`INFO` the key would otherwise land in Cloud Logging.

When you add a log call, keep to the same rule: log ids, counts and enum values, never
document text, names, phone numbers or tokens.

## Finding things in Cloud Logging

Console → Logging → Logs Explorer, project `nomadfinance-prod`:

```
resource.type="cloud_run_revision"
resource.labels.service_name="nomadfinance-api"
jsonPayload.request_id="5a78542e22f54df7a1f6b87be4e2b56f"
```

Other useful filters (add to the first two lines):

```
jsonPayload.message:"request_completed" jsonPayload.status>=500
jsonPayload.message:"request_completed" jsonPayload.latency_ms>2000
jsonPayload.user_hash="<16 hex characters>"
severity>=ERROR
```

From a terminal:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="nomadfinance-api" AND jsonPayload.status>=500' \
  --project nomadfinance-prod --limit 20 --freshness 1d --format json
```

To find one person's requests: compute their hash from the uid, then filter on `user_hash`.

```bash
python3 -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:16])" <uid>
```

## Try it locally

From `backend/` with the virtualenv active (bash; in PowerShell use `$env:NAME="value"` for
each variable):

```bash
# text format, as in everyday development
uvicorn app.main:app --port 8080
curl -i "http://127.0.0.1:8080/api/v1/nope?token=SECRET"
```

Expect a 404, an `x-request-id` response header, and a log line with `status=404`, the same
request id and no `SECRET` anywhere.

```bash
# JSON format, as on Cloud Run (non-local needs the two cron variables)
APP_ENV=prod GEMINI_API_KEY=x CRON_SERVICE_ACCOUNT=a@b.c CRON_AUDIENCE=https://x \
  uvicorn app.main:app --port 8091
curl -s -H "X-Request-ID: my-trace-12345" -o /dev/null http://127.0.0.1:8091/api/v1/nope
```

Expect one JSON line per request with `"request_id": "my-trace-12345"`.

Tests: `pytest tests/unit/core/test_logging.py tests/integration/api/test_request_logging.py tests/unit/test_hashing.py`.

## After deploy

After the next backend deploy, open the Logs Explorer, filter on
`jsonPayload.message:"request_completed"`, and check that lines are structured (fields under
`jsonPayload`), that `request_id` is present, and that `trace` is filled in. Then call
`GET https://<service-url>/health` and confirm `x-request-id` is in the response.

## Design notes

- **Plain ASGI middleware**, not `BaseHTTPMiddleware`. The latter runs the app in another task,
  where the user hash recorded by the auth dependency would not be visible to the middleware.
  The request context is a small mutable object in a `ContextVar`, so a change made anywhere
  during the request is seen when the line is written.
- **Outermost layer.** `app.add_middleware(RequestLoggingMiddleware)` is the last call in
  `create_app()`, so requests answered by other middleware (CORS preflights, rate-limit 429s
  from NF-P1-027) are logged too. Keep it last when adding middleware.
- **Unsalted hash.** Firebase uids are random, so the hash cannot be reversed; anyone who
  already holds a uid can match it, which is the point of a correlation id. A salt would be a
  new secret in Secret Manager for little gain. Change `app/utils/hashing.py` if that
  changes.
- **Browsers and the header.** Frontend code can only read `X-Request-ID` if the CORS
  configuration (NF-P1-027) lists it in `expose_headers`. Without that the header still
  reaches the logs and tools such as curl, just not `fetch()` in the browser.
- Gunicorn's own start-up lines (before the app loads) are still plain text; they appear as
  text entries in Cloud Logging, next to the JSON ones.
