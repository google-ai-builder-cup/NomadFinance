# NF-P3-011 — FIB: Bill OCR Extraction

Assigned to Devam; built by Aditya.

## Summary

`POST /api/v1/fib/bill/scan` reads a photo or PDF of a bill with Gemini Vision (extraction tier, prompt `fib/extract_bill.v1`) and stores it in `users/{uid}/bills` with `source: "bill_ocr"`. This is step 2a of the Financial Identity pipeline (`docs/mermaid/financial-identity-pipeline.mmd`). The manual `POST /fib/bill` from NF-P3-010 is unchanged.

Categorizing uncategorized entries (NF-P3-012), the weekly recompute (NF-P3-013) and the upload UI (NF-P3-016/017) are separate tasks.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/fib.py` | `ExtractedBill` (the Gemini `response_schema`) and `BillScanResponse` |
| `backend/app/services/fib/ocr.py` (was an empty stub) | `read_bill` (the Gemini call) and `scan_bill` (validate, upload the photo, write the entry) |
| `backend/app/api/v1/fib.py` | `POST /fib/bill/scan`; reuses `read_contract_upload` for the size, empty and type checks |
| `backend/app/integrations/cloud_storage.py` | `BillImageStore`, writes `bills/{uid}/{entry_id}/bill.<ext>` |
| `docs/api/endpoints.md`, `docs/data-model/collections/fib.md` | Endpoint section; note on `category_confidence` |
| 3 new test files | Service, endpoint, and an opt-in live Gemini test |

No shared files touched. `FibRepository` is reused as it is, and `storage.rules` already lets the owner read `bills/{uid}/…`.

## Decisions

1. **The photo is kept** under `bills/{uid}/{entry_id}/` and stored as `image_path`, as the data model describes. Account deletion already removes the `bills/` folder. If the upload fails the entry is still saved without `image_path`: losing the photo must not lose the amount just read.
2. **Nothing is stored unless it is a bill with an amount above 0 and a 3-letter currency.** Both are required fields of an entry. Not a bill and unreadable amount or currency are two different 422 messages.
3. **`paid` unknown is stored as `false`** and the response says `paid_assumed: true`, so the app can ask the worker. `entry_date` is the bill's date when it shows as paid, otherwise today (data model: "the day it was paid, or the day it was logged if unpaid").
4. **Category from this call is stored as `category_source: "model"` without `category_confidence`.** The prompt returns one `confidence`, for amount and currency together. Using it as the category's confidence would be wrong; NF-P3-012 sets the real value.
5. **`bill_date` is a string in the Gemini schema**, parsed in the service. A misread date is dropped instead of failing the whole response and discarding a good amount.
6. **Timeout:** a photo uses the default 30 s; a PDF uses `GEMINI_EXTRACTION_TIMEOUT_SECONDS` (90 s), the same split as contract extraction.
7. **Rate limit:** `limit_ai_calls` (10 a minute per user), because each call costs Gemini quota.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` | Clean |
| `mypy --strict app/services/` | Clean (39 files) |
| `mypy app/` | Clean (125 files) |
| `pytest` (full suite) | 808 passed, 54 skipped (live-Gemini tests) |
| New: `test_fib_ocr.py` (18) | Prompt, tier and timeout; stored fields; paid, unpaid and unknown `paid`; dropped date; currency and vendor clean-up; PDF extension; failed photo upload; refusals write nothing |
| New: `test_fib_bill_scan.py` (10) | 201, both 422s, 504, 400, 415, 413, missing file, auth, OpenAPI |
| New: `test_fib_bill_scan_live.py` (3), `RUN_LIVE_GEMINI=1` | Real Gemini: unpaid English SGD electricity bill (total, not subtotal; `utilities`), paid Indonesian receipt (`Rp 1.250.000` read as 1250000 IDR, day-first date `05/09/2026` read as 2026-09-05, `rent`), a photo that is not a bill (422). 1.5 to 1.8 s a call |

Not verified: a real phone photo of a bill (the live bills are generated text PDFs, so skew, glare and creases are untested), and the real Cloud Storage upload and Firestore write (both faked in tests; `FibRepository.save_entry` is the same code NF-P3-010 uses).

## Manual test steps

Start the API from `backend/`, get a Firebase ID token the same way as for the other endpoints, then:

bash:
```bash
curl -s -H "Authorization: Bearer $TOKEN" -F "file=@bill.jpg" http://127.0.0.1:8080/api/v1/fib/bill/scan
```

PowerShell:
```powershell
curl.exe -s -H "Authorization: Bearer $env:TOKEN" -F "file=@bill.jpg" http://127.0.0.1:8080/api/v1/fib/bill/scan
```

Expected: `201` with the stored entry, and a new document in `users/{uid}/bills` plus the photo in `bills/{uid}/{entry_id}/`. Try a selfie (422 "No bill found"), an empty file (400) and a `.txt` (415). Or use Swagger at `/docs`, `POST /api/v1/fib/bill/scan`, with Authorize set first.

Live Gemini test (needs `GEMINI_API_KEY` in `.env.local`):

```bash
RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_fib_bill_scan_live.py -v -s
```
