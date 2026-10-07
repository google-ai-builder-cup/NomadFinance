# NF-SA-012 — Scam check history, hash cache and hourly limit

## Summary

`POST /api/v2/scam/analyze` now stores each check under the worker, answers a repeated message from storage without calling Gemini, and refuses a worker's 21st new check in an hour. Two read routes, `GET /api/v2/scam/checks` (history) and `GET /api/v2/scam/checks/{id}` (one check), were added. This is the "stored, cached and limited" half of the analyzer that NF-SA-007 to -011 left as the contract's "not yet" values (`cached: false`, an `id` that matched nothing).

| | Before | Now |
|---|---|---|
| `id` of an answer | random, matches no stored check | the first 32 hex characters of the cache key, a real stored check |
| `cached` | always `false` | `true` for a repeated message |
| Limit | 10 a minute (the general AI budget) | 20 an hour per worker for checks that call Gemini, plus the API-wide 60 a minute |
| History, detail | not built | built |
| `indicators[].seen` | always `null` | read live from `scam_indicators` (stays `null` until NF-SA-013 writes it) |

The contract is `docs/api/v2-scam.md`; the stored shape is `docs/data-model/collections/scam.md`.

## How a check is looked up

```
message -> redact -> cache key = SHA-256( normalised redacted text, "\n", language )
        -> read users/{uid}/scam_checks/{first 32 hex of the key}
             usable?  yes -> count it, move the expiry, answer `cached: true`   (no Gemini, no budget)
                      no  -> spend one of the 20 checks an hour (429 if none left)
                             classify, explain and find similar scams, store, answer
```

A stored check is served again only if **all** of these hold, otherwise the message is checked afresh and the document is overwritten:

| Rule | Why |
|---|---|
| It has not passed `expires_at` | The TTL job deletes within a day or so, not at the moment, so the code treats the time as the truth |
| It has an explainer | Contract: a check whose explainer failed is not served, so the next try makes one |
| Its `taxonomy_version` is the current one | The scam types and tactics changed, so the answer could differ |
| Every prompt it was made with still has its version (`scam.classify`, and `scam.explain` or `scam.reassure`) | A new prompt version can change the answer |

When a check is made again over an older one, the older one's **report state is kept** (`reported_report_id`, `reported_at`) and `check_count` goes up. The report belongs to the message, and NF-SA-013 sets it.

**Normalising:** Unicode form NFKC, lower-cased, whitespace collapsed. A message that differs only in case, spacing or a look-alike character form is the same message. The language is part of the key because the explainer is written in it.

## Files

| File | Purpose |
|---|---|
| `backend/app/repositories/scam_check_repo.py` (new) | `users/{uid}/scam_checks`: get, save, touch (count and expiry), list newest first, and `ref()` for NF-SA-013's transaction |
| `backend/app/repositories/scam_indicator_repo.py` (new) | Read-only `scam_indicators` lookup in one round trip |
| `backend/app/services/scam/check_store.py` (new) | Cache key, stored shape, the "usable" rules, and `CheckStore` (lookup, serve a hit, save) |
| `backend/app/services/scam/history.py` (new) | History list, one check, the cursor |
| `backend/app/services/scam/indicator_seen.py` (new) | `seen` from `scam_indicators` |
| `backend/app/services/scam/analyzer.py` | Cache lookup first, hourly budget, store at the end |
| `backend/app/api/v2/scam.py`, `scam_checks.py` (new), `router.py` | Analyze without the per-minute AI budget; the two GET routes |
| `backend/app/core/rate_limit.py`, `config.py`, `.env.example` | `consume_limit()` and the setting `RATE_LIMIT_SCAM_ANALYZE` (default `20/hour`) |
| `backend/app/dependencies.py` | `get_scam_check_store` |
| `backend/tests/...` | 114 new tests (below), the in-memory fakes, and 4 existing tests updated |
| `docs/api/v2-scam.md`, `docs/data-model/collections/scam.md`, `docs/mocks/scam/analyze-error-rate-limited.json` | Status, two clarifications, the new id rule, the hourly message |

No shared file, no new package, no new index (every query is a direct read or `order by created_at desc` on one field, which Firestore indexes automatically), and no rules change (the owner can already read `scam_checks`; every write is the backend's). The TTL policy on `scam_checks.expires_at` is already active in production.

## Where this differs from, or sharpens, the documents

| # | Point | What was done |
|---|---|---|
| 1 | **The check's id.** The data model said "auto id"; the contract said "a check is written under its hash". | Followed the contract: the id derives from the cache key, so a retried request writes the same document and a repeat is one direct read. `cache_key` is still stored as the data model defines it. The data model now says so |
| 2 | **A screenshot always spends the hourly budget**, even when its text then matches a stored check. | Gemini Vision has to read the image before there is any text to look up. The contract said a hit never spends the budget; it now names this exception. The later steps are still saved |
| 3 | **The 10-a-minute AI budget is gone from this route.** | The contract's table says 20 an hour plus 60 a minute API-wide, and a hit must be free, which a per-request dependency cannot do. `limit_ai_calls` runs before the message is looked at. The auth-matrix test records this on purpose |
| 4 | **"No raw PII in stored documents."** | The stored text is the redacted one and nothing else of the message is kept. NF-F0-003 decision 2 deliberately keeps each indicator's value (a phone number, a link's host, an email, a handle), owner-only, for 90 days, never logged. Tests assert no raw message and no identifier outside `indicators` |
| 5 | **`seen` is read live.** | The detail route and every answer read `scam_indicators` (a hidden indicator counts as never reported). Nothing writes it until NF-SA-013, so it is `null` today |
| 6 | **The hourly-limit message.** | The mock said "Please wait a minute", which is wrong for an hour. It now reads "You have used all your checks for this hour. Please try again later." The code, status and headers are unchanged |

## Behaviour to know

- **A Firestore failure never fails a check.** If the lookup fails the check goes ahead; if the write fails the worker still gets the answer (the id then matches no stored check), and a warning is logged (`scam_check_not_stored`).
- **The budget is spent when Gemini is about to be called**, so a check that then fails with a Gemini error has used one of the 20. That matches "checks that call Gemini".
- **The limit is counted per Cloud Run instance, in memory,** like the others (D-94). With `max-instances 2`, up to 40 an hour can get through, and a restart resets the count. The key is the verified uid, not an address.
- **Two requests for the same new message at the same moment** both call Gemini and write the same document; the second overwrites the first. Rare, and still one stored check.
- **A cache hit returns the first check's corridor-dependent fields:** the `unexpected_country` flag and `corridor_report_count` as they were when it was made. The key (message and language) is the data model's.
- **`models.explainer`** records the tier the explainer started on. A scam is explained on the reasoning tier and, if that is busy, on the classification tier; that fallback is not recorded, because changing the explainer's return type is NF-SA-009's.
- **The history cursor** is the last row's `created_at`, tied to the worker. A cursor from another worker, or one that was never issued, is `400 invalid_cursor`. Ties at the same microsecond are not a concern with server-set times.
- **Check ids are validated** (letters, digits, `_`, `-`, up to 64): `..` or a slash would make the Firestore client raise, and answers the same `404` as an unknown id.

## Manual test

With the emulators and the API running as in `NF-F0-005-backend-feature-flags.md` (`firebase emulators:start --only auth,firestore`, then uvicorn with the emulator variables), a signed-in test user's token in `$ID_TOKEN`, the `scam` flag on in `config/feature_flags`, and the taxonomy loaded (`python -m src.loaders.scam_taxonomy` from `data-scripts/`). The analyze call needs a real Gemini key; without one use the tests below.

```bash
curl -s -X POST http://127.0.0.1:8080/api/v2/scam/analyze -H "Authorization: Bearer $ID_TOKEN" -H "Content-Type: application/json" -d '{"text": "Pay 800 SGD fee today", "language": "en"}'
```

Send the same body twice: the second answer has `"cached": true` and the same `id`, and the log shows `scam_cache result=hit`. Then:

```bash
curl -s "http://127.0.0.1:8080/api/v2/scam/checks?limit=5" -H "Authorization: Bearer $ID_TOKEN"
```

```bash
curl -s "http://127.0.0.1:8080/api/v2/scam/checks/<id>" -H "Authorization: Bearer $ID_TOKEN"
```

To see the limit without spending Gemini calls, run `pytest tests/integration/api/test_scam_history.py -k "21st"`.

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `black`, `ruff`, `mypy app`, `mypy --strict app/services` | clean |
| `pytest` (backend, no emulator) | **1,881 passed**, 96 skipped; 108 of them new |
| The CI emulator step (`firebase emulators:exec ... pytest tests/integration`) with Google credentials hidden, as on a runner | 514 passed, 60 skipped (live Gemini); 6 new tests use the real Firestore emulator |
| New tests | stored shape and cache rules (33), history, cursor and detail (26), `seen` (12), the API: cache, budget, stored contents, history, detail, guards (37), repositories on the emulator (6) |
| Break the code on purpose | Never consulting the cache (5 tests failed), spending the budget before the lookup (4), storing a raw-looking field (1) and listing expired checks (1) were each caught |
| End to end on the real Auth and Firestore emulators, real repositories and flag document and taxonomy, only Gemini and the neighbour search faked | 16 of 16: a repeat is cached with **zero Gemini calls**; the stored document holds no raw message, phone, account, email or link outside `indicators`; the 21st new message is a 429 in the envelope with `Retry-After` and `X-RateLimit-*`; a repeat still answers once the budget is gone; the history pages with a cursor; another worker gets a 404 and an empty history and cannot use the cursor |
| The id derivation | `indicator_doc_id` reproduces the data model's own example id (`8c83cb97151fd86a6c73ff5fa296244e` for the number 6590000001) |

**Not verified:** a real Gemini answer end to end (the test environment has no valid key, so the model's answers are recorded), p95 latency, and several Cloud Run instances sharing a count.

## Definition of Done (Backend Endpoint)

- [x] FastAPI endpoints with Pydantic request and response models (the contract's own)
- [x] Firebase token verification on every route (and the `scam` flag)
- [x] Structured logging: `scam_cache result=hit|miss`, nothing of the message or its hash
- [x] Specific status codes (200, 400 `invalid_cursor`, 401, 404, 422, 429)
- [x] Manual test: steps above, and the live run on the emulators
- [x] Contract (`v2-scam.md`) and mock updated; the drift test passes
- [x] Rate limit applied (20 an hour per worker, plus the API-wide 60 a minute)
- [ ] Reviewed by a teammate (Devam)

## Commit

Branch: `feature/NF-SA-012-scam-history-cache`.

```bash
git commit -m "feat(scam): store checks, add hash cache, history and hourly limit" -m "Refs: NF-SA-012"
```

PR title: `feat(scam): check history, hash cache and hourly limit for the analyzer (NF-SA-012)`
