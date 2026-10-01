# NF-P3-014 — FIB: PDF Report Export

## Summary

`POST /api/v1/fib/report/export` renders the worker's current `users/{uid}/financial_profile/current` as a PDF with weasyprint, stores it at `exports/{uid}/financial-identity-{timestamp}.pdf`, sets `latest_export` on the profile and returns a signed download link. `GET /api/v1/fib/report/export` returns a fresh link to the latest PDF without rendering again. It does not recompute the profile: that is the weekly job (NF-P3-013), and the PDF prints the date the profile was computed.

The export UI with preview and share buttons (NF-P3-018) and the demo data (NF-P3-015) are separate.

## Files

| File | Change |
|---|---|
| `backend/app/services/fib/exporter.py` (was an empty stub) | `export_report`, `latest_report_link`, `render_pdf` |
| `backend/app/services/fib/report_html.py` (new) | The report as escaped HTML and CSS |
| `backend/app/services/fib/report_labels.py` (new) | Headings, metric names and disclaimer in the six app languages |
| `backend/app/integrations/cloud_storage.py` | `ExportStore`: upload, delete, V4 signed URL |
| `backend/app/repositories/fib_repo.py` | `set_latest_export` |
| `backend/app/schemas/fib_export.py` (new), `backend/app/api/v1/fib.py` | The two endpoints |
| `backend/app/config.py`, `backend/.env.example` | `EXPORT_URL_EXPIRY_MINUTES` (default 1440) |
| **`backend/requirements.txt`** (shared) | `weasyprint==70.0` |
| **`backend/Dockerfile`** (shared) | `libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-noto-core` |
| `backend/app/services/contract/extractor.py`, `backend/app/services/fib/ocr.py` | One typing annotation each (see decision 8) |
| `docs/api/endpoints.md`, `docs/data-model/collections/fib.md`, `infra/iam/service-accounts.md` | Endpoint section; notes; the new IAM role |
| 5 new test files, 1 extended | See below |

## Decisions

1. **Two endpoints.** `POST` makes and links a PDF, `GET` re-links the latest one, because stored links expire (the data model says links are never stored).
2. **It prints the stored profile and does not recompute.** With no profile yet, `POST` is a 404.
3. **Language is the narrative's.** The headings, metric names and disclaimer come from `report_labels.py` in the same language, so the page is not half English. **The hi, tl, id, ne and bn wording was written without a native-speaker review: have it reviewed before a lender sees a real report.**
4. **Content.** Title, period, months, reporting currency, dates; entry counts; the four scores as bars (`Not enough records` for a metric with no score); the narrative; verified employment (employer and salary) if the profile has it; a disclaimer that this is not a credit score and was not checked against bank records. The overall score is not printed: it is an average of this project's own formulas and could be read as a credit score. No uid, email or phone. `holder_name` is optional, printed on the PDF only, never stored (we keep no names).
5. **One PDF per worker.** The path is timestamped (as in `firestore-schema.md`), and the previous file is deleted after `latest_export` points at the new one. If the profile update fails the new file is removed, so a file the profile does not point to is never left behind. A previous file that cannot be deleted is logged and does not fail the export.
6. **Signed link.** V4, 24 hours by default, downloads as `financial-identity-report.pdf`. Cloud Run has no private key, so the link is signed through IAM as the service account itself. A key file used locally signs directly.
7. **Safe rendering.** Everything from the profile or the worker is HTML-escaped, the page links to nothing, and the renderer's URL fetcher refuses every request. `weasyprint` is imported when a PDF is made, not at startup, so a missing system library fails the export instead of stopping the API from starting.
8. **Adding weasyprint changed how mypy types two older files.** It pulls in Pillow, and with Pillow present mypy infers the Gemini `contents` list in `extractor.py` and `ocr.py` as `list[object]` and fails `--strict`. I annotated the list in both. Without it CI's mypy would fail after the dependency lands.
9. **Rate limit:** the API-wide 60 a minute only. A render is a 1 to 2 s CPU job in a threadpool, and there is no Gemini quota to protect.

## Before this works in production (manual)

1. **Merge, then wait for the backend deploy.** The image build installs the system libraries from the Dockerfile. This adds about 150 MB (mostly fonts).
2. **Let the runtime service account sign links.** Once:
   ```bash
   gcloud services enable iamcredentials.googleapis.com --project nomadfinance-prod
   gcloud iam service-accounts add-iam-policy-binding \
     nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com \
     --member "serviceAccount:nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com" \
     --role roles/iam.serviceAccountTokenCreator --project nomadfinance-prod
   ```
   Without it `POST` and `GET` answer 500 when they sign the link (the PDF itself is already stored). The runtime account already has `roles/storage.objectUser` on the bucket (`grant-account-deletion-roles.sh`), which covers writing and deleting the PDFs.
3. **Check the first real export** with the steps below, in particular that Hindi and Bengali show real glyphs, not boxes (it proves `fonts-noto-core` is in the image).

## Verified results (2026-10-02)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` | Clean |
| `mypy --strict app/services/`, `mypy app/` | Clean (43 and 131 files) |
| `pytest` (full suite) | 916 passed, 60 skipped (live-Gemini tests) |
| New: `test_fib_report_html.py` (21) | All six languages have every label; language and fallback; scores and missing scores; no overall score; dates; paragraphs; holder name; escaping of hostile values; verified employment; and **a real weasyprint render of all six languages** (skipped if the system libraries are missing) |
| New: `test_fib_exporter.py` (10) | Render, store, record, link; previous export deleted; failed delete ignored; failed profile update removes the new file; no profile; latest link without rendering; no export |
| New: `test_export_store.py` (10) | Path, content type and the checks that keep a path inside `exports/{uid}/`; key-file signing; IAM signing; refreshing expired credentials |
| New: `test_fib_report_export.py` (9) | Both endpoints, holder name, 404s, 422, the lifetime setting, auth, OpenAPI |
| `test_fib_repo_profile.py` (+1) | `set_latest_export` updates only that field |
| Visual check | The six PDFs were rendered to images and looked at (English, Hindi, Bengali in detail): one page, correct Indic shaping, bars and layout as intended, a hostile employer name and holder name shown as plain text |

**Not verified:**
- `docker build` and the apt package names (Docker was not running; they follow weasyprint's Debian instructions).
- The fonts: locally the PDFs use Windows' Nirmala UI, so the Noto fonts in the image are untested.
- Real Cloud Storage upload, deletion and a real signed link (the store is tested with mocks).
- The IAM signing path on Cloud Run.

## Manual test steps

Get a Firebase ID token as for the other endpoints, from a user that has a profile (run the `fib-recompute` job first, NF-P3-013). bash:

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"holder_name": "Test Worker"}' http://127.0.0.1:8080/api/v1/fib/report/export
```

PowerShell:

```powershell
curl.exe -s -X POST -H "Authorization: Bearer $env:TOKEN" -H "Content-Type: application/json" -d '{\"holder_name\": \"Test Worker\"}' http://127.0.0.1:8080/api/v1/fib/report/export
```

Open `download_url` in a browser: it downloads `financial-identity-report.pdf`. Call it again: the old file in `exports/{uid}/` is gone. `GET` on the same path returns a new link; a user without a profile gets a 404.

Local rendering only (no Firebase), from `backend/` with the venv active:

```bash
pytest tests/unit/services/test_fib_report_html.py -v
```
