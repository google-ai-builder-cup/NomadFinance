# NF-P2-017 — Remittance X-Ray: Transfer Logging

## Summary

`POST /api/v1/remittance/log` stores a transfer the worker actually sent, under `users/{uid}/transfers/{id}` — the entry that links Remittance X-Ray to Financial Identity (design doc §5.6, `docs/pipelines/remittance-xray.md`, `docs/data-model/collections/fib.md`). No Gemini call; the "Log a transfer" step in the pipeline table.

**Every stored amount comes from the comparison's own chosen provider, never typed freely by the client.** The body is the unmodified response of `POST /remittance/compare` as `comparison`, plus the `rpw_id` of the service the worker actually used. `provider_name`, `send_amount`, `receive_amount`, `fee`, `cost_pct` and `mid_market_rate` are all read from that provider's row and `comparison`'s own fields — the same reasoning NF-P2-016's `/recommend` uses to never trust a provider name Gemini wrote over the comparison's own top-ranked one. A `rpw_id` that is not a comparable, ranked provider of `comparison` (pays out in another currency, or was never on the ranked list, so has no `recipient_receives`) is a `422`.

No new package, no shared file changed. `frontend/firestore.rules` already allows owner-read on `transfers` generically (NF-P1-014); nothing to add there since the backend is the only writer.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/remittance_log.py` (new) | `TransferLogRequest`, `TransferLogResponse` |
| `backend/app/repositories/fib_repo.py` (was a stub) | `FibRepository`: generic `users/{uid}/{transfers,income,bills,savings}` entry read/write, used here for `transfers` only |
| `backend/app/services/remittance/logger.py` (was a stub) | `log_transfer()`, `_chosen_provider()`, `ProviderNotInComparisonError` |
| `backend/app/api/v1/remittance.py` | `POST /api/v1/remittance/log` |
| `backend/tests/unit/services/test_remittance_logger.py` (new) | 7 tests |
| `backend/tests/integration/api/test_remittance_log.py` (new) | 9 tests |
| `docs/api/endpoints.md`, `docs/pipelines/remittance-xray.md` | Endpoint; step marked built |

`requirements*.txt`, `pyproject.toml`, `Dockerfile`, the workflows, `firestore.rules` and `frontend/` are unchanged.

## Decisions

1. **The request carries the whole comparison, not raw amounts.** The same pattern `/remittance/recommend` already uses (send back the unmodified `/compare` body) instead of a form with `send_amount`/`fee`/etc. typed by the client. Nothing about a transfer's cost is trusted from outside the comparison the worker already saw; only `rpw_id` (which provider), `entry_date` and `notes` are genuinely new information the client supplies.
2. **`fx_rate_applied` (fib.md, "rate the provider used") is never set.** The engine (`services/remittance/engine.py`) prices every provider against one shared live rate plus a fee and a margin percentage; it does not model a provider's own quoted exchange rate as a separate number. Only `mid_market_rate` (`comparison.rate.rate`) is stored, which the data model already marks optional. Setting `fx_rate_applied` to a number we do not actually have would be worse than leaving it out.
3. **A non-comparable or unranked `rpw_id` is a 422, not a fallback.** Such a provider has `recipient_receives: null` in the comparison, so there is nothing correct to store as `receive_amount`. `_chosen_provider()` requires `comparable and recipient_receives is not None`, matching (`comparable`, `recipient_receives`) failures identically whether the id is unknown, not comparable, or (in principle) both.
4. **`FibRepository` is written generically, but only used for `transfers` here.** `docs/data-model/collections/fib.md` groups `transfers`, `income`, `bills`, `savings` under one shared shape (`entry_date`, `notes`, `source`, timestamps, `schema_version`) and one file, `fib_repo.py` — an existing stub, not a new file. `save_entry`/`new_id`/`get_entry` take an `EntryKind` so NF-P3-010 (income/bill/savings endpoints) can reuse them without a new repository class; no method for those other kinds is added yet, since nothing calls them.
5. **Blank `notes` become `null`**, not an empty string, so a worker who types and deletes a note doesn't leave a stray empty field. Not stored under Firestore at all when absent, matching every `fib.md` example (no `notes` key shown when there is none), rather than writing an explicit `null`.
6. **`entry_date` defaults to today (UTC) when omitted**, since most logs happen right after the transfer; a worker who is backfilling can still send a past date.
7. **`201 Created`, matching `POST /api/v1/contracts`** (NF-P2-007): this creates a new resource, unlike `/compare` and `/recommend`, which compute and return without storing.
8. **`comparison.providers` is bounded to 60**, the same `MAX_PROVIDERS` reasoning as `/recommend` (a real corridor has at most 44 surveyed services): rejected before any Firestore write.

## Flow

```
POST /api/v1/remittance/log
  {comparison, rpw_id, entry_date?, notes?}
  auth (401), body checked: comparison ≤ 60 providers (422)
  log_transfer(uid, body, transfers, now)                      [services/remittance/logger.py]
    └─ _chosen_provider(): comparison.providers where rpw_id matches, comparable, recipient_receives set
                                                                 → none found → ProviderNotInComparisonError (422)
    └─ entry_date = body.entry_date or now.date()
    └─ FibRepository.new_id(uid, "transfers")                   Firestore auto id
    └─ FibRepository.save_entry(uid, "transfers", id, {...})    users/{uid}/transfers/{id}
  201 {transfer_id, corridor_id, provider_rpw_id, provider_name,
       send_amount, send_currency, receive_amount, receive_currency,
       fee, mid_market_rate, cost_pct, entry_date, notes}
```

## All commands, in order

From `backend/` with the virtual environment active.

### 1. Checks (the same ones CI runs, plus tests in mypy)

```bash
ruff check .
black --check .
mypy app
mypy app tests
python -m pytest -q
```

As CI runs it:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent python -m pytest -q
docker build --platform linux/amd64 -t nomadfinance-backend:ci .
```

### 2. Try the endpoint by hand

Start the API, get a Firebase ID token as in the NF-P2-001 runbook, call `/remittance/compare` for a corridor and amount, then send its response as `comparison` (with the `rpw_id` of any comparable provider from it) to the example in `docs/api/endpoints.md`.

```powershell
# Windows PowerShell
$body = @{ comparison = $compareResponse; rpw_id = 521250759 } | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/v1/remittance/log `
  -Headers @{ Authorization = "Bearer $Token" } -ContentType "application/json" -Body $body
```

```bash
# bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"comparison\": $compare_response, \"rpw_id\": 521250759}" \
  http://127.0.0.1:8080/api/v1/remittance/log
```

Confirm the write with the Firestore Emulator UI (or the Firebase console) at `users/{uid}/transfers/{transfer_id}`.

## Verified results (2026-09-30)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` | Pass (188 files unchanged plus the new ones) |
| `mypy app`, `mypy app tests` | Pass (116 / 187 source files; no new errors — pre-existing env gaps for `limits`/`yaml`/`google.genai` stubs unrelated to this change) |
| `pytest -q`, with and without Google credentials | 578 passed, 47 skipped (opt-in live and emulator tests) |
| New tests | 7 service, 9 endpoint |
| `docker build --platform linux/amd64 -t nomadfinance-backend:ci .` | **Not run**: Docker daemon not running on this machine this time. `Dockerfile` and `requirements.txt` are unchanged; NF-P2-014 already built and smoke-tested an image from the same `Dockerfile` |
| Manual Swagger try-out with a real token | Not run this session — do before merging |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 422 `rpw_id is not a comparable, ranked provider...` | Either `rpw_id` isn't in `comparison.providers`, or it is but pays out in another currency (`comparable: false`) or was never ranked. Pick an `rpw_id` from a provider with `rank` not null in the same `/compare` response |
| 422 FastAPI validation list, no custom message | `comparison` or `rpw_id` missing, or `comparison.providers` has more than 60 entries |
| Logged transfer not visible to the app | The app reads `users/{uid}/transfers` directly from Firestore (`firestore.rules`, owner read); check the signed-in uid matches the token used to log it |
| `fx_rate_applied` is always absent | Expected — see decision 2. Only `mid_market_rate` is stored |

## Definition of Done (Backend Endpoint)

- [x] Endpoint defined in FastAPI with Pydantic request/response models
- [x] Firebase Auth token verification (`Depends(get_current_user)`)
- [x] Structured logging with request ID, user ID (hashed), timing — from NF-P1-028, automatic; `logger.info` in `logger.py` adds corridor/rpw_id/entry_date
- [x] Error handling with specific HTTP status codes (401, 422, 429)
- [ ] Manual test via Swagger `/docs` successful — yours, needs a real token
- [x] OpenAPI docs updated (auto-generated; sanity-checked in `test_endpoint_is_documented_in_openapi`)
- [x] `docs/api/endpoints.md` updated
- [x] Rate limiting applied via slowapi if user-facing — API-wide only (no Gemini call), same as `/compare` and `/trends`

## Commit and PR for this task

Branch: `feature/remittance-transfer-log` (already checked out).

```bash
git commit -m "feat(remittance): log a completed transfer for Financial Identity" -m "Refs: NF-P2-017"
```

PR title: `feat(remittance): log a completed transfer (NF-P2-017)`

## For teammates

- **Whoever builds the FIB timeline / NF-P3-010 activity endpoints:** `FibRepository` (`repositories/fib_repo.py`) already has generic `new_id`/`save_entry`/`get_entry` keyed by `EntryKind` (`"transfers" | "income" | "bills" | "savings"`); reuse it for income/bills/savings rather than writing a second repository class. No update/delete method exists yet — add one when an edit flow needs it.
- **NF-P3-013 (weekly recompute):** a logged transfer already has everything `fib.md`'s example shows except `fx_rate_applied`, which is never set (decision 2) — the recompute should not expect it.
- **Frontend (whoever wires the "log this transfer" button after `/compare` or `/recommend`):** call `/remittance/log` with the same `comparison` object already in hand and the `rpw_id` the worker picked; show `receive_amount`/`fee`/`cost_pct` back from the `201` response as confirmation, not from the original comparison (in case the two ever drift).

## Not covered here

- Income, bill and savings logging endpoints, bill OCR, weekly recompute, PDF export (NF-P3-010 to NF-P3-014, NF-P3-018)
- Any UI for logging a transfer — no frontend task for it before Week 3's FIB UI
- `docker build`: not run this time (daemon not running); see NF-P2-014's runbook for the last successful run
