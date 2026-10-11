# gemini_usage

How many requests the backend has sent to each Gemini model today, per feature, so the daily budget (NF-HR-010, `backend/app/integrations/gemini/budget.py`) is the same on every Cloud Run instance. Written and read only by the backend; no client rule matches the collection, so a browser is refused.

```
gemini_usage/{YYYY-MM-DD}
```

## `gemini_usage/{day}`

One document per **quota day**. The id is the date in US Pacific time, because Google's daily request quotas reset at midnight Pacific (07:00 UTC in summer, 08:00 in winter). Nothing is written for a day with no request, and nothing is written at all while the model's daily limit is not configured (`GEMINI_RPD_*` unset: the budget guard is off).

| Field | Type | Required | Description |
|---|---|---|---|
| `calls` | map | yes, after the first request | `calls.<feature>.<tier>` is the number of requests sent: `feature` is `contract`, `remittance`, `radar`, `fib`, `coach` or `scam`; `tier` is `reasoning`, `extraction`, `classification` or `embedding`. Counted with server-side increments, so two instances never overwrite each other. Retried attempts count, because Google counts them. |
| `exhausted` | map | only after a per-day 429 | `exhausted.<tier>` is the time Google first answered a per-day 429 for that tier's model. While the tier is listed, the backend sends it no request until the day turns. |
| `updated_at` | timestamp | yes | Server time of the last write |
| `schema_version` | number | yes | `1` |

**Example** — `gemini_usage/2026-11-12`

```json
{
  "calls": {
    "coach": { "classification": 412, "reasoning": 38 },
    "scam": { "classification": 77, "reasoning": 41, "embedding": 77 },
    "contract": { "extraction": 26, "reasoning": 19 }
  },
  "exhausted": { "reasoning": "2026-11-12T19:42:11Z" },
  "updated_at": "2026-11-12T19:42:11Z",
  "schema_version": 1
}
```

## How it is used

- A request is refused when its feature has used its share of the tier's daily limit (`SHARES` in `budget.py`: the share times `GEMINI_RPD_<TIER>`, rounded down, at least 1). The worker gets `503 ai_busy` with `Retry-After` set to the seconds until the day turns.
- Each instance keeps its own count and reads the document again every 15 seconds, so two instances can overshoot a share by the requests made in that window. A Firestore failure never blocks a request: the instance carries on with its own count.
- No TTL and no index: a document is a few hundred bytes, a year is about 365 of them, and they are the history of what the quota was spent on. Delete old days by hand if that ever matters.
- Rules: nothing matches `gemini_usage`, so it is denied to every browser by default (`frontend/tests/rules/` checks it).

## Reading it

```bash
# From backend/, with application default credentials for the project:
python - <<'PY'
from datetime import UTC, datetime
from app.integrations.gemini.budget import budget_day
from app.repositories.base import get_firestore_client
day = budget_day(datetime.now(UTC))
print(day, get_firestore_client().collection("gemini_usage").document(day).get().to_dict())
PY
```
