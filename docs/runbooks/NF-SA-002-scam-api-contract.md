# NF-SA-002 — Scam Analyzer API contract and mocks

## Summary

The four routes of the Scam Analyzer are now specified, with a sample of every answer and a test that keeps the samples honest. The frontend can build the screens (NF-SA-015 to -018) against the mock API before any backend exists, and the backend tasks (NF-SA-007, -008, -012, -013) implement against models that are already written.

| Route | Does |
|---|---|
| `POST /api/v2/scam/analyze` | Check a pasted message (JSON) or a screenshot (multipart) |
| `GET /api/v2/scam/checks` | The worker's history, newest first, cursor pagination |
| `GET /api/v2/scam/checks/{id}` | One stored check |
| `POST /api/v2/scam/checks/{id}/report` | Warn other workers: report to Exploitation Radar |

The contract is `docs/api/v2-scam.md`. The executable form is `backend/app/schemas/scam.py` (Pydantic models, no logic). The mocks are in `docs/mocks/scam/` (22 files).

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Analyze is **one synchronous call** returning verdict, indicators, similar scams and explainer. The client allows 60 s. | Design 5.2 and the tracker describe one response. A scam waits for the explainer, which has taken 15 to 40 s on the reasoning tier (D-115), so the contract tells screens not to treat a slow answer as failure. |
| 2 | **The explainer degrades.** A failed explainer step is a `200` with `explainer: null` and `explainer_status: "unavailable"`; such a check is not served from the cache. | The worker keeps the verdict when the slowest, most quota-hungry step fails. A retry produces the explainer. |
| 3 | **No `Idempotency-Key`** on any scam route (D-126). | The conventions leave key storage to the data model and none was designed. Analyze is idempotent through the per-user cache, report through `reported_report_id`. |
| 4 | **20 checks an hour per worker count only requests that call Gemini.** A cache hit is free and does not use the budget. Other routes: 60 a minute. | The budget protects the Gemini quota; a repeat message costs none of it. |
| 5 | Text over 4,000 characters is a `422`, **never cut**. Screenshots: JPEG, PNG or WebP, at most 5 MB (`415` and `413` otherwise). | The payment request is often at the end of a scam message. HEIC is left to the implementers (D-125). |
| 6 | The answer **never contains** the cache key, model names, prompt versions or any ids of other people's reports. `similar` is `{source, scam_type, score}` only. | Internals are not the client's business; other workers' reports are not this worker's data. |
| 7 | The report request is `{indicator_ids, description?}` and the server **redacts the description again**. A repeat tap returns the first report (`200`, `already_reported: true`). A check the analyzer judged benign is `409 not_a_scam`. | The worker can type anything into the edit box. Nothing is sent that is not in the request. |
| 8 | Three error codes of this feature's own: `unsupported_media_type` (415), `image_unreadable` (422), `not_a_scam` (409). | The conventions allow a feature its own codes and forbid reusing one for another meaning. |
| 9 | Mock names are numbered, so the **default** answer of a route (the first by name, in the MSW layer) is the high-risk example, and the refusals sort after the successes. | A dev preview of the analyze route should show the interesting case, not an alphabetically-first benign one. |

## Files

| File | Purpose |
|---|---|
| `docs/api/v2-scam.md` (new) | The contract |
| `backend/app/schemas/scam.py` (new) | The request and response models; also `ScamVerdict`, the classifier's output schema (NF-SA-007) |
| `docs/mocks/scam/*.json` (new, 22 files) | The samples; list in `docs/mocks/README.md` |
| `backend/tests/unit/test_scam_mocks.py` (new) | The drift test and the model rules (111 cases: 110 run, 1 skipped by design) |
| `frontend/src/mocks/scam.msw.test.ts` (new) | Proves the mock API serves every route, by default and swapped (15 tests) |
| `docs/mocks/README.md`, `docs/api/endpoints.md` | The `scam/` section; a pointer to the v2 contracts |
| `docs/data-model/collections/scam.md`, `radar.md` | Samples corrected: they showed `[AMOUNT]`, a token the redaction utility does not produce (it leaves amounts as written) |
| `docs/deferred-items.md` | D-105 closed; D-124 to D-126 added; D-115 now also names NF-SA-009 |

No shared file, no new package, no change to any endpoint.

## How to use it

**Frontend** (NF-SA-015 to -018). In a test: `setupMockServer()` and `server.use(handlerForMock("scam/analyze-04-benign.json"))` to pick another answer; `frontend/src/mocks/scam.msw.test.ts` shows each route and each refusal. For a screen that needs the mock API outside tests, the same files are the source. The default analyze answer is the high-risk Hindi example; `analyze-05-cached`, `analyze-06-explainer-unavailable` and the four refusals cover the states a screen has to draw.

**Backend** (NF-SA-007, -008, -012, -013). Return `ScamAnalyzeResponse`, `ScamCheckListResponse`, `ScamCheckDetail` and `ScamReportResponse` from `app.schemas.scam`; take `ScamAnalyzeTextRequest` and `ScamReportRequest` as the bodies; use `ScamVerdict` as the classifier's `response_schema`. Errors go through `ApiError` / the v2 envelope. The model rules are real checks: a benign message has no type and low risk, an explainer is `null` exactly when `explainer_status` is `unavailable`, `reported` and `report_id` agree. If a rule is wrong for a good reason, change the model and the doc in one pull request: the drift test then tells you what else to update.

**Changing the contract.** Update `docs/api/v2-scam.md`, `backend/app/schemas/scam.py` and the mocks together. `backend/tests/unit/test_scam_mocks.py` fails until the mocks parse as the models, the type and tactic ids exist in the taxonomy, the stored text is already redacted (it is a fixed point of `redact_text`), every indicator id is the real hash of its kind and value, a check expires 90 days after it was made, the history rows say what their checks say, and the document names every route and added code.

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `black`, `ruff`, `mypy app` | clean |
| `pytest` (backend) | 1,447 passed, 76 skipped; 110 of the passes are the new drift and model tests |
| Mutation check | Six deliberate errors in the mocks (an extra field, a wrong indicator hash, a raw phone number in the stored text, a tactic outside the taxonomy, a history row that disagrees with its check, a wrong Radar slug) each make the tests fail; the mocks were restored and pass again |
| Frontend (`vitest`, eslint, `tsc`) | 47 files, 386 tests pass; the 15 new ones prove every route and refusal through MSW |
| Existing samples | `scam.md` / `radar.md` sample documents still pass the data-model checks after the correction |

## Definition of Done

- [x] Specified: `POST /scam/analyze` (text and image), `GET /scam/checks`, `GET /scam/checks/{id}`, `POST /scam/checks/{id}/report`
- [x] Request and response schemas published (`scam.py`) with 4 mocks for high, medium, low risk and benign, and 18 more for the other states
- [x] MSW handlers generated from the mocks, and shown to serve them
- [x] A backend check that the mocks cannot drift from the models
- [x] Written in Markdown with consistent formatting; no chat-style openers
- [ ] Reviewed by Pranjal (the tracker's reviewer) before any Scam frontend or backend branch is opened
