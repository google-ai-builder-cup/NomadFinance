# NF-P3-001 — Radar: Report Submission Endpoint

## Summary

`POST /api/v1/radar/report`: a worker reports a money transfer operator, recruitment agency or employer. Steps 2 to 4 and 7 of the Exploitation Radar pipeline (`docs/mermaid/exploitation-radar-pipeline.mmd`): extract who and where it's about (Gemini, extraction tier), screen for spam/abuse/personal data (Gemini, classification tier), classify the violation type (Gemini, classification tier), then store `radar_reports/{id}`.

The three radar prompts (`extract_entity.v1`, `validate.v1`, `categorize.v1`), the internal `RadarReport`/`RadarValidation` schema and `RadarRepository.create_report`/`new_report_id` already existed (built by NF-P1-029 and the NF-P2-021 contract signal); this task fills the empty `services/radar/intake.py` and `app/api/v1/radar.py` stubs on top of them.

Not in this task: embedding/clustering (NF-P3-002 — every report here starts its own cluster, the same fallback `contract_to_radar.py` already uses), `radar_entities` risk aggregation and community rating (NF-P3-003), App Check / reCAPTCHA enforcement (NF-P3-025), the submission form UI (NF-P3-006).

## Files

| File | Change |
|---|---|
| `backend/app/schemas/radar_report.py` (new) | `RadarReportRequest`/`RadarReportResponse` (client-facing), plus `ExtractedEntity`, `ReportScreen`, `ViolationClassification` (the three Gemini structured-output models) |
| `backend/app/services/radar/intake.py` (was an empty stub) | `extract_entity`, `screen_report`, `classify_violation`, `submit_report`; `EntityUnknownError`, `LocationUnknownError`, `SpamDetectedError`, `AbusiveContentError`, `PersonalDataError` |
| `backend/app/api/v1/radar.py` (was an empty stub) | The router and the `POST /report` endpoint |
| `backend/app/api/v1/router.py` | Registers `radar.router` |
| `backend/app/utils/hashing.py` | Added `hash_reporter(uid, secret)` (HMAC-SHA-256) alongside the existing `hash_user_id` |
| `backend/app/config.py`, `backend/.env.example` | Added `radar_reporter_hash_secret` (required, like `gemini_api_key`) |
| `backend/tests/conftest.py` | Set a default test value for the new required setting |
| `backend/tests/unit/services/test_radar_intake.py` (new) | 12 tests on the service logic with a fake Gemini client and a fake repository |
| `backend/tests/integration/api/test_radar_report.py` (new) | 16 tests on the endpoint with dependency overrides |
| `docs/api/endpoints.md` | Added the endpoint's row and full section |

No backend files outside `radar/` and the two small shared touch points above; no frontend, no data-model or security-rules change (the schema was already documented for this task).

## Decisions

1. **`entity_type`, `entity_name`, `corridor_id` and `host_country` are all optional in the request; only `description` and `language` are required.** `extract_entity.v1.yaml`'s own framing ("the values the worker chose in the form, **possibly empty**") anticipates this — a worker can file a report from free text alone, and step 2 fills whatever the form left blank. A form value present in the request always wins over what step 2 extracts.
2. **`violation_type` is not an accepted request field at all.** `categorize.v1.yaml` classifies fresh from the report text and does not take a form hint as input, and `RadarValidation.category_confidence`'s own docstring frames the stored `violation_type` as the classification tier's output, not a worker's pick. Accepting a field the backend would always discard would only invite the frontend (NF-P3-006) to trust it.
3. **Reject, don't store, when step 3 finds `is_abusive: true` or a non-empty `personal_data` list** — the same as spam (`spam_score >= 0.7`, a constant; no calibration data exists yet to tune it). This becomes a public community database: a threat or a stranger's home address must never be written to Firestore even once. Confirmed with you before building.
4. **The entity's slug is built from `extracted.entity_name_normalized` when Gemini gave one, falling back to the raw name.** The normalized form strips legal suffixes and punctuation ("QuickRemit Pte Ltd" → `quickremit`), which is exactly the dedup quality the slug exists for (`radar.md`: "the slug is the join key the cross-pillar badges match on").
5. **`reporter_hash` uses a new keyed HMAC (`hash_reporter`, `utils/hashing.py`), not the existing `hash_user_id`.** `hash_user_id` is deliberately unsalted for log correlation only; `radar_reports` is read through the API (`docs/api/endpoints.md` already documented this as a "salted hash" before this task existed), so it must not be feasible to test a known uid against it without the secret.
6. **`amount`/`currency` from step 2's `ExtractedEntity` are accepted into the schema but never persisted.** `radar_reports` has no field for them (checked `radar.md`); they're kept in the Gemini response model only because they are genuinely part of the model's answer, not invented.
7. **Step 4's `summary` is returned to the client (for a confirmation screen) but not stored on the report.** `categorize.v1.yaml`'s own description says it's "used in alerts (NF-P3-004)", but neither `RadarReport` nor `radar.md` has a field for it. Rather than inventing a Firestore field for another task to own, it's surfaced only in the response; NF-P3-004 will need its own decision about where a stored summary would live.
8. **Every closing tag the worker could write (`</report>`, `</entity>`, `</form>`) is escaped before interpolation into the three prompts** (`_untag`, copied from `services/contract/complaint.py`'s existing helper). A public, unmoderated report is more adversarial than a contract's own clause text, which already gets this treatment.

## Verified results (2026-09-30)

| Check | Result |
|---|---|
| `ruff check .` | Clean |
| `black --check .` | Clean |
| `mypy --strict app/services/` | Clean (36 files) |
| `mypy app/` (whole app, informational) | Clean (120 files) |
| `pytest` (full suite) | 653 passed, 51 skipped (pre-existing live-Gemini tests, gated by `RUN_LIVE_GEMINI`) — up from 625 passed before this task |
| New: `tests/unit/services/test_radar_intake.py` | 12 passed — form-vs-extraction reconciliation, entity/location-unknown rejection, spam/abuse/personal-data rejection (each confirmed **not stored**), slug dedup, reporter-hash keying, tag-injection, Gemini failures passed through untouched |
| New: `tests/integration/api/test_radar_report.py` | 16 passed — 201 happy path, auth, rate-limit dependency wired, all 422/502/503/504 error paths, OpenAPI documented, a `violation_type` sent by a client is silently ignored |
| Banned-word scan across every changed file | Clean, no matches |

**No live Gemini call was made.** All three prompts (`extract_entity.v1`, `validate.v1`, `categorize.v1`) load and validate at import (a malformed prompt file would fail every test), and the full pipeline logic is proven against a fake Gemini client standing in for all three calls. A real end-to-end call against the actual API is worth doing once, at your discretion — see Manual test steps below for exact commands; I did not spend real Gemini quota on this without asking first.

## Manual test steps

Requires the Firestore + Firebase Auth emulators running, and `RADAR_REPORTER_HASH_SECRET` set in `backend/.env.local` (any string — I did not write to that file myself; add it yourself alongside your existing `GEMINI_API_KEY`).

**1. Start the backend** (bash and PowerShell are the same here):

```bash
cd backend
uvicorn app.main:app --reload --port 8080
```

**2. Get a Firebase ID token for a test user** (Auth emulator), then:

bash:
```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_type": "money_transfer_operator", "entity_name": "Example Remit",
       "corridor_id": "SG-IN",
       "description": "They showed one rate and gave me a worse one at the counter.",
       "language": "en"}' \
  http://127.0.0.1:8080/api/v1/radar/report
```

PowerShell:
```powershell
$body = @{
  entity_type = "money_transfer_operator"; entity_name = "Example Remit"
  corridor_id = "SG-IN"
  description = "They showed one rate and gave me a worse one at the counter."
  language = "en"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/v1/radar/report" `
  -Headers @{Authorization = "Bearer $env:TOKEN"} -ContentType "application/json" -Body $body
```

Expect `201` with a `report_id`, the classified `violation_type`, and a `summary`. This spends real Gemini quota (three calls): extraction tier once, classification tier twice.

**3. Swagger:** open `http://127.0.0.1:8080/docs`, authorize with the bearer token, try `POST /api/v1/radar/report` with only `description` and `language` filled in — confirm it still succeeds (extraction fills the rest) or returns the "could not tell who/where" 422 if the free text genuinely names nobody.

**4. Confirm rejection paths without real PII:** resubmit with `"description": "My phone is 555-1234, call me about QuickCash's fees."` — expect a 422 asking to remove personal details, and no document written under `radar_reports` in the Firestore emulator UI.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| App fails to start: `radar_reporter_hash_secret` field required | Add `RADAR_REPORTER_HASH_SECRET=<anything>` to `backend/.env.local` |
| `pytest` fails everywhere, not just radar tests | Same cause during tests — check `tests/conftest.py` sets `RADAR_REPORTER_HASH_SECRET` via `os.environ.setdefault` before `app.main` is imported |
| 422 "Could not tell who this report is about" on a report that does name a business | Check step 2's prompt is actually reading the free text — `entity_name` in the request is optional, but the report text itself must name someone if the form field is blank |
| A worker's chosen `violation_type` doesn't come back in the response | By design (decision 2) — the stored and returned `violation_type` is always step 4's fresh classification |

## Definition of Done

**Backend Endpoint**
- [x] Endpoint defined in FastAPI with Pydantic request/response models
- [x] Firebase Auth token verification
- [x] Structured logging (`radar_report_created`, slug/violation/corridor/country; Gemini call logging is the client's own `gemini_call` line, already built)
- [x] Error handling with specific HTTP status codes (401/422/429/502/503/504)
- [ ] Manual test via Swagger /docs — not run live (no Gemini spend without asking first; exact steps given above)
- [x] OpenAPI docs updated (auto-generated; sanity-checked via the integration test and the route listing)
- [x] `docs/api/endpoints.md` updated
- [x] Rate limiting applied (`limit_ai_calls`, same as every other Gemini-calling endpoint)

**Gemini Pipeline Step**
- [x] Correct model tiers (extraction for step 2, classification for steps 3 and 4)
- [x] Structured output via Pydantic `response_schema` — no free-form parsing
- [x] Retry logic via tenacity (built into `GeminiClient`, reused as-is)
- [x] Timeout set (default 30 s; no override needed — these are short, single-paragraph calls)
- [x] Token usage logged (via `GeminiClient`'s existing `gemini_call` logging)
- [x] Prompts stored in code, versioned (`radar/extract_entity.v1`, `radar/validate.v1`, `radar/categorize.v1` — pre-existing)
- [ ] Tested with 3+ diverse inputs against the **real** model — tested with 12+16 automated cases against a fake Gemini client instead; a live pass is the one item I'm flagging as not done, pending your OK to spend the quota

## Commit and PR

Branch: `feature/radar-report-submit` (already checked out).

```
feat(radar): add report submission endpoint
Refs: NF-P3-001
```

PR title: `feat: exploitation radar report submission endpoint (NF-P3-001)`

## Noticed, not fixed

- Evidence-photo upload (`radar_reports.evidence_paths`, `radar-evidence/{reportId}/` in `firestore-schema.md`) has no owning task in `.claude/tasks.md`, the original design, or the data model. `evidence_paths` stays an empty list on every report created by this endpoint until some task claims it.
- Step 4's `summary` (decision 7 above) has no field to live in on `radar_reports`, even though its own prompt says it exists for NF-P3-004's alerts. NF-P3-004 will need to either add that field or regenerate its own summary from the stored report.
