# NF-P3-006 — Radar: Report Submission Form

## Summary

A four-step form at `/radar/report` where a signed-in worker reports a money transfer service, recruitment agency or employer. It calls the existing backend (`POST /api/v1/radar/report`, then `POST /api/v1/radar/report/{id}/evidence` for each photo) and shows a confirmation. Frontend only: no backend change.

Not in this task: the heatmap (NF-P3-007), entity page (NF-P3-008), alert feed (NF-P3-009), App Check on submit (NF-P3-025), and any link to the form from another screen. `/radar` still shows "Coming soon" until NF-P3-007, so the form is reached by its URL for now.

## Steps of the form

1. **Who**: type (operator, agency, employer) and the business name.
2. **Where**: an operator or agency needs a money route (one of the six corridors, default from the worker's profile); an employer needs the host country.
3. **What happened**: description (10 to 2000 characters) and the language it is written in (default: the worker's preferred language).
4. **Check and send**: a summary, optional evidence (up to 5 files, PDF or image, 10 MB each, same limits as the backend), then Send.

## Decisions worth knowing

- **No violation picker.** The tracker lists "violation" as a form field, but the backend does not accept `violation_type`: it always classifies it from the description (step 4 of the pipeline). The confirmation screen shows the violation the backend chose.
- **Evidence is best effort.** The report is stored by the first call. Each photo is then uploaded on its own; a failed photo is counted on the confirmation screen ("could not be attached, your report was still saved") instead of failing the report. The mutation does not retry, so a report cannot be stored twice.
- **Errors.** A 422 is mapped to a specific message by the start of the backend's text (`utils/radarForm.ts`, `REJECTION_KEYS`, copied from `api/v1/radar.py`); if the backend words change, the form falls back to a generic "could not be accepted" message. 503, 504 and 429 have their own messages.
- **Privacy note** is shown on the last step and on the confirmation: the worker's name and account are not shown with the report (only a one-way hash is stored).

## Files

- `frontend/src/types/radar.ts`, `services/radarService.ts`, `hooks/useRadar.ts`
- `frontend/src/utils/radarForm.ts` (step checks, request builder, error mapping) and `radarForm.test.ts`
- `frontend/src/components/radar/ReportForm.tsx`, `EvidencePicker.tsx`, `ReportConfirmation.tsx`
- `frontend/src/pages/radar/RadarReport.tsx`, `router.tsx` (route `/radar/report`)
- `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json`: new `radar` block (violation names and the form)

## Test it by hand

Needs the backend running with Gemini access (or the emulators and a test setup the team uses) and a signed-in, onboarded user.

```bash
cd frontend
pnpm dev
```

1. Open `/radar/report`. Try Next on step 1 with nothing chosen: an error appears and you stay on the step.
2. Choose "Money transfer service", enter a name, Next. The money route defaults to your profile's corridor.
3. Go back, choose "Employer": step 2 now asks for a country instead.
4. Step 3: write fewer than 10 characters and press Next: error. Write a real description.
5. Step 4: add 2 photos, try adding a 6th file (error "up to 5"), remove one, then Send.
6. The confirmation shows the business, the violation the backend chose and the summary, plus "Files attached".
7. Switch the app language (header) and repeat: all text follows.
8. Turn off the network before Send: the offline message appears and your answers stay on screen.
9. Write a phone number in the description: the backend answers 422 and the form shows the "remove personal details" message.

## Limits

- Not run in a browser by me: the page sits behind sign-in and needs a live backend. Type-check, lint, unit tests (`radarForm.test.ts`) and translation key parity were run.
- hi, tl, id, ne and bn strings were written without a native speaker; have them reviewed before the demo.
- `tsc -b` reports one error outside this task: `TrendChart.tsx` cannot find `recharts` in this checkout's `node_modules` (run `pnpm install`).
