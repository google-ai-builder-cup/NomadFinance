# NF-P3-010 — FIB: Activity Logging Endpoints

Originally assigned to Aditya; picked up on your confirmation of the pattern from NF-P3-009.

## Summary

Three manual activity-logging endpoints — `POST /api/v1/fib/income`, `POST /api/v1/fib/bill`, `POST /api/v1/fib/savings` — writing into `users/{uid}/income`, `users/{uid}/bills`, `users/{uid}/savings`. The fourth entry type, `transfers`, was already built (NF-P2-017, remittance log); this task adds the other three onto the exact same shared repository, which already existed for exactly this purpose.

No Gemini call in this task — category classification (Flash-Lite, NF-P3-012) and bill-photo OCR (Gemini Vision, NF-P3-011) are separate, later steps over the same collections. Every category here is `category_source: "user"`, whatever the worker chose or left blank.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/fib.py` (was an empty stub) | `IncomeLogRequest`/`Response`, `BillLogRequest`/`Response`, `SavingsLogRequest`/`Response`, and the shared category/direction/account-type literals |
| `backend/app/services/fib/logger.py` (was an empty stub) | `log_income`, `log_bill`, `log_savings` — mirrors `services/remittance/logger.py`'s `log_transfer`, the first writer into this same repository |
| `backend/app/api/v1/fib.py` (was an empty stub) | The three endpoints |
| `backend/app/api/v1/router.py` | Registers `fib.router` |
| `docs/api/endpoints.md` | New endpoints' rows and section |
| 2 new test files | 26 tests: the service layer, and the endpoints |

**No changes to `backend/app/repositories/fib_repo.py`.** `FibRepository` already had everything this task needed — `new_id`/`save_entry`/`get_entry`, generic across all four entry kinds — built by NF-P2-017 with a comment saying so explicitly: *"NF-P2-017 is the first writer, for transfers only; NF-P3-010 adds the rest."* This task only had to add the schemas, the service functions, and the routes on top of it.

## Decisions

Fewer open questions than recent tasks — `docs/data-model/collections/fib.md` already specified every field, required-vs-optional, and the category enums precisely, so most of this was transcription, not design. The few real calls:

1. **`verified` is never a request field, always `false` in this endpoint's writes.** Per the data model, `verified: true` (a contract-backed income line) is set only by NF-P3-024's cross-pillar flow — accepting it here would let a worker mark their own manual entry "verified," which defeats the point of the field.
2. **`category` is required for income, optional for bills, absent entirely for savings** — exactly matching the data model's own table ("category — no (yes for income)"; "Transfers and savings: none needed"). A bill's `category_source` is `null`, not `"user"`, when no category was sent, so NF-P3-012 can tell "not yet categorized" apart from "the worker said none of these fit" (which doesn't actually exist as an option here, but the `null` state matters for the categorizer's own query later).
3. **`bill_date` (printed on the bill) is a separate field from `entry_date`** (when the worker logged it, or paid it) — both optional, both dates, easy to conflate; kept as two fields exactly as the data model names them, not collapsed into one.
4. **`entry_date` defaults to today when omitted**, same as `POST /remittance/log` already does — one convention across every activity-logging endpoint in this pillar, not something to reinvent per entry type.
5. **A simple `Field(pattern="^[A-Z]{3}$")` on `currency`.** No existing precedent for validating a *user-typed* currency code elsewhere in this codebase (remittance's transfer log takes its currencies from the comparison result, never types them fresh) — this is a new, narrow validator, not a reused one, but matches the ISO 4217 convention used everywhere else in the docs.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` | Clean |
| `mypy --strict app/services/` | Clean (39 files) |
| `mypy app/` (whole app, informational) | Clean (125 files) |
| `pytest` (full suite) | 780 passed (26 new), 51 skipped (pre-existing live-Gemini tests) — up from 754 before this task |
| New: `test_fib_logger.py` (15) | Income (user category, unverified, optional fields omitted when blank, entry_date kept when given), bills (category present vs absent, `bill_date` vs `entry_date` kept separate, unpaid stored as such), savings (deposit/withdrawal, optional account_type omitted, amount always positive even for a withdrawal), shared notes-blanking and currency-pattern validation |
| New: `test_fib_log.py` (11) | All three endpoints: 201 happy path, required-field validation (`category`/`paid`/`direction`), negative amount and malformed currency both 422, auth required on all three, all three documented in OpenAPI |

No live browser/emulator pass this time — pure backend, JSON in and out, no UI and no Firestore-emulator-specific behavior beyond what the unit/integration tests with a fake repository already exercise faithfully (the real `FibRepository.save_entry` is a thin, already-tested wrapper reused unchanged from NF-P2-017, not new code this task wrote).

## Manual test steps

bash / PowerShell (same commands; in PowerShell use `curl.exe`):
```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"amount": 650, "currency": "SGD", "category": "salary", "employer_name": "Acme"}' \
  http://127.0.0.1:8080/api/v1/fib/income

curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"amount": 38.5, "currency": "SGD", "paid": true, "vendor": "Example Telecom"}' \
  http://127.0.0.1:8080/api/v1/fib/bill

curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"amount": 120, "currency": "SGD", "direction": "deposit", "account_type": "bank"}' \
  http://127.0.0.1:8080/api/v1/fib/savings
```
Expect `201` from each, and the new documents visible under `users/{uid}/income`, `users/{uid}/bills`, `users/{uid}/savings` in the Firestore console or emulator UI.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 422 on a request that looks right | Check `currency` is exactly 3 uppercase letters — `"sgd"` and `"SG"` are both rejected on purpose |
| A bill's `category_source` is unexpectedly `null` | Correct if no `category` was sent — `null` means "not yet categorized," not an error; NF-P3-012 is the step that fills it in later |
| An income entry shows `"verified": false` even though the worker has an analysed contract | Expected — this endpoint never sets `verified: true`; that only happens through NF-P3-024's own write path |

## Definition of Done (Backend Endpoint)

- [x] Endpoints defined in FastAPI with Pydantic request/response models
- [x] Firebase Auth token verification
- [x] Structured logging (`fib_income_logged`/`fib_bill_logged`/`fib_savings_logged`)
- [x] Error handling with specific HTTP status codes (401/422)
- [ ] Manual test via Swagger — not run live this time (no UI to click through end to end, no Gemini/external call to be cautious about spending on; exact `curl` steps above cover it)
- [x] `docs/api/endpoints.md` updated
- [x] Rate limiting applied (API-wide only, no Gemini call on any of the three)

## Commit and PR

Branch: `feature/fib-activity-log` (already checked out).

```
feat(fib): add manual activity logging endpoints
Refs: NF-P3-010
```

PR title: `feat: financial identity builder activity logging endpoints (NF-P3-010)`

## Noticed, not fixed

- None — the data model doc was thorough enough that nothing came up outside this task's own scope.
