# NF-FC-014 — Coach plan translation and PDF export

## Summary

A worker can read their 90-day plan, and download it as a PDF, in any of the six languages (en, hi, tl, id, ne, bn). `POST /api/v2/coach/sessions/{id}/plan` and `GET /api/v2/coach/plans/{id}` now honour `language`; the new `GET /api/v2/coach/plans/{id}.pdf?language=` returns the file. This closes D-218 (the plan was English only after NF-FC-012).

**Only sentences are translated, and the figures are never sent to the model.** Gemini Flash-Lite (`coach/translate_plan.v1`) gets the plan's narrative; every figure, currency code, date, id and severity stays in the stored English plan. Before a translation is saved, code checks that every number and currency code in each text is exactly as in the English, and that the translated plan with its words taken out equals the English one byte for byte. The tracker's finish line ("numeric fields byte-identical pre / post translation") therefore holds by construction and is also checked.

| Situation | What happens |
|---|---|
| A language not yet stored | Translated once, checked, saved as `translations/{lang}`; the Gemini budget is spent only now |
| The same language again | Read from storage; no Gemini call |
| The translation fails or changes a number | One retry with the reasons; then `502 ai_bad_response`, nothing saved (a retry of the call finds the English plan and only translates) |
| `GET .../{id}.pdf` | Rendered on the first request in a language (from the translated plan), stored at `exports/{uid}/coach-plan-{id}-{lang}.pdf`, returned with the bearer token; later requests read the stored file; a file deleted from storage is made again |

## Files

| File | Change |
|---|---|
| `backend/app/prompts/coach/translate_plan.v1.yaml`, `app/schemas/coach_plan_text.py` | The prompt and the `PlanTranslation` response model (text only) |
| `backend/app/services/coach/plan_translator.py`, `plan_translation_check.py` (new) | The Flash-Lite step with one retry; the numbers and structure check; `same_figures`. Under `mypy --strict` |
| `plan_pdf_labels.py`, `plan_pdf_labels_latin.py`, `plan_pdf_labels_indic.py`, `plan_pdf_html.py`, `plan_pdf.py` (new) | The six-language wording, the HTML, the render (reuses the Financial Identity renderer) |
| `plan_files.py` (new), `plan_service.py`, `plan_document.py` | Translation and PDF storage logic; `language` plumbing; `grounding_of` and `rates_as_of` moved |
| `backend/app/api/v2/coach_plans.py`, `dependencies.py` | `language` on both routes, the `.pdf` route (registered before `/plans/{id}`), the translation budget |
| `backend/app/repositories/coach_session_repo.py`, `app/integrations/cloud_storage.py` | Translation get/create/list, `set_pdf`; `ExportStore.read` |
| `backend/app/config.py`, `.env.example` | `GEMINI_COACH_TRANSLATE_TIER` (classification) and `GEMINI_COACH_TRANSLATE_THINKING_BUDGET` (0) |
| `docs/features/coach-plan.md`, `docs/api/v2-coach.md`, `docs/deferred-items.md`, `backend/app/prompts/README.md` | The translation and PDF rules; status and open point 7; D-218 closed, D-221, D-222; the prompt row |

No shared file was touched: `weasyprint==70.0` is already in `requirements.txt` and the Dockerfile already installs Pango and `fonts-noto-core` (Latin, Devanagari, Bengali) for the Financial Identity PDF.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Signed URL or the file | **The file through the API**, as the contract (NF-FC-002) says and the tracker does not: the bucket has no CORS policy, so the app could not read a signed link's bytes to share the file, and a link anyone can open would be a link to a worker's debts. Closes contract open point 7 |
| 2 | Disclaimer | Translated by the model with the rest, not fixed wording per language (D-221) |
| 3 | PDF headings | Fixed in code in six languages, not native-reviewed (D-221), like the Financial Identity report |
| 4 | Numbers | Always digits 0 to 9, in every script, as in the JSON plan; the check rejects other digits |
| 5 | Rate limit | `limit_ai_calls` is applied inside the route, only when a translation is really made, so reading a stored plan costs nothing |

## Results

**Offline (2026-10-09):** 3,100 backend tests pass (154 skipped, the live ones), 58 of them new.

| Check | Result |
|---|---|
| Figures identical across languages | For all **12 personas × 5 languages** (60 translations through the service with a faithful stand-in), `same_figures` holds, and the score, answers, rates date and id are equal |
| Doctored translations | A changed number, a dropped or added number, digits of another script, a changed currency code, another separator, a link, a runaway length, wrong week numbers, wrong ids, a missing action: each rejected. Edited figures (amount, id, severity) change the fingerprint |
| Translator | Only text is sent (no budget or provider fields); a rejected answer is asked again with the reasons; two rejected are a 502; English is refused; Gemini errors pass through |
| Storage | Translated once then read; `available_languages` lists what is stored; a failed translation stores nothing and the retry does not make the plan twice; two requests at once use the stored one |
| PDF | All 6 languages render; the figures are in the text; HTML is escaped and links to nothing; a plan with no debt or provider leaves those sections out; stored per language and read back; a missing file is made again |
| Routes | `language` on both routes; the PDF headers (`application/pdf`, `Content-Disposition`, `Cache-Control: private, no-store`); the `.pdf` route does not swallow the plan route; JSON errors; 404 for another worker's plan; flag and token |
| `black`, `ruff`, `mypy app`, `mypy --strict app/services` | clean |

**Live, real Gemini (`gemini-3.1-flash-lite`, classification tier), 2026-10-09:** persona 1's plan translated into **hi, tl, id, ne and bn, one call each, all accepted by the checks with every figure intact** (about 4 to 8 seconds a language).

**Seen by eye:** pages of the Hindi, Bengali, Nepali and Tagalog PDFs rendered to images and read (Indonesian was rendered and not looked at): conjuncts and vowel signs are shaped correctly, nothing is cut off at the edge after one padding fix, warnings carry a severity word as well as a colour.

**Not verified:** the fonts in the production image (the pages above used this Mac's fonts; the Dockerfile installs `fonts-noto-core`, which the Financial Identity PDF already relies on); translations of all 12 personas live (the checks are the same code; only persona 1 was run live); the quality of the words by native speakers (D-221).

## Manual test

```bash
cd backend
# free: the check, the translator, the PDF, the service and the routes
pytest tests/unit/services/test_coach_plan_translation.py tests/unit/services/test_coach_plan_pdf.py tests/unit/services/test_coach_plan_files.py tests/integration/api/test_coach_plans.py
# live, real Gemini (five calls); PLAN_PDF_DIR keeps the PDFs to look at
RUN_LIVE_GEMINI=1 PLAN_PDF_DIR=/tmp/plans pytest tests/integration/test_coach_plan_translate_live.py -v -s
```

Against production, once `cost_baselines` is loaded (D-216) and the `coach` flag is on for you: with a plan made, `GET /api/v2/coach/plans/{id}?language=hi` (translated, then stored), the same again (no Gemini call in the logs), and `GET /api/v2/coach/plans/{id}.pdf?language=hi` with the bearer token (a PDF).

## Limits (D-221, D-222)

Wording not read by native speakers; a translation is made once and not redone; two requests at once may both call the model; numbers are Latin digits in every language.

## Definition of Done (Backend, Gemini step)

- [x] Correct tier (classification, Flash-Lite) via a setting
- [x] Structured output via a Pydantic response model; no free-text parsing
- [x] Prompt in the library as a versioned file, with its variables
- [x] Failures handled (Gemini errors keep their codes; an unusable translation is a 502; nothing half-stored)
- [x] PDF renders in all 6 languages (checked by eye for the three Indic scripts)
- [x] Numeric fields byte-identical before and after translation (checked in code on every translation; tested for 12 personas × 5 languages)
- [x] Tests with a stand-in model, and a live run recorded here
- [ ] Wording reviewed by native speakers (D-221)
- [ ] Reviewed by a teammate (Pranjal, per the tracker)

## Commit

Branch: `feature/NF-FC-014-coach-plan-pdf` (already checked out).

```bash
git commit -m "feat(coach): add plan translation and PDF export" -m "Refs: NF-FC-014"
```

PR title: `feat(coach): plan translation and PDF export in six languages (NF-FC-014)`
