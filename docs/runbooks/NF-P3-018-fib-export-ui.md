# NF-P3-018 — FIB: Portable Report Export UI

Your own task.

## Summary

`/identity/export`: trigger `POST /fib/report/export` (NF-P3-014, already live), preview what the PDF contains, download it, and share the signed link. Checks for an existing export on load via `GET /fib/report/export` so returning to the page doesn't force a re-render.

## The preview constraint

Checked exactly how the PDF is served before building anything: `ExportStore.signed_url` (`cloud_storage.py`) always sets `Content-Disposition: attachment`, and there's no Cloud Storage CORS policy anywhere in this repo. Both ways to show the real PDF inline are therefore ruled out — an `<iframe src={download_url}>` just triggers a download (browsers honor `attachment`), and `fetch()`-ing the bytes for a blob viewer is blocked by CORS. Neither is a frontend bug to route around; `attachment` is NF-P3-014's own deliberate choice, not an oversight, and this task doesn't touch the shared storage integration to add inline-viewing support it was never designed for.

**Resolution:** "Preview" renders the report's actual content from `financial_profile/current` (already fetched by NF-P3-017) in a hand-built modal — no modal/dialog component existed anywhere in this app before this task. One deliberate accuracy detail: the real PDF never prints the overall score ("could be read as a credit score," NF-P3-014 decision 4) — this preview doesn't either, even though the dashboard's `ScoreMeter` does, since the preview represents what a lender will actually see. Download and Share both use the real signed URL directly, unaffected by any of this.

## Files

| File | Change |
|---|---|
| `types/fib.ts` | `ExportReportRequest`/`Response`, `VerifiedEmployment` |
| `services/fibService.ts` | `exportReport` (POST), `getLatestReport` (GET) |
| `hooks/useFIB.ts` | `useLatestReport` (`staleTime: 0` — always re-signs on page visit), `useExportReport` (`setQueryData` on success, no extra refetch) |
| `utils/fibScore.ts` (new) | `STATUS_COLOR`, `statusFor`, `savingsRatePct` — extracted out of `ScoreMeter.tsx` so the preview modal reuses the exact same status logic instead of duplicating it |
| `components/fib/ScoreMeter.tsx` | Now imports from `fibScore.ts` instead of defining its own copies |
| `components/fib/ReportPreviewModal.tsx` (new) | The modal: overlay, Escape/backdrop-click close, body-scroll lock, focus on open, report-shaped content, no overall score |
| `pages/fib/FIBExportReport.tsx` (was an empty stub) | Holder-name field, Generate/Regenerate, Preview, and (once a report exists) Download + Share |
| `router.tsx` | `/identity/export` |
| `pages/fib/FIBDashboard.tsx` | "Export report" link, shown once a profile exists |
| i18n | `fib.export.*`, `fib.dashboard.exportReport`, all 6 languages |

No backend changes.

## Decisions

1. **No modal/dialog primitive existed anywhere in this app** — built one scoped to this use case (`ReportPreviewModal.tsx`) rather than a generic reusable `Modal` component nothing else needs yet.
2. **The preview omits the overall score deliberately** (see above) — the one place this page's content must diverge from `ScoreMeter`'s, on purpose.
3. **Download and Share need no workaround.** A plain `<a href={download_url}>` is exactly right for `attachment` disposition, and the Web Share API shares the *link*, not file bytes — `navigator.share({ url })` needs no fetch and hits no CORS wall at all. Falls back to clipboard copy where Web Share isn't available (no prior precedent in this app; mirrors `ComplaintPreview.tsx`'s copy-with-toast pattern for the contract complaint letter).
4. **`useLatestReport` has `staleTime: 0`**, unlike most of this app's queries (global default 60s) — `GET /fib/report/export`'s whole purpose is handing back a link that hasn't expired, so returning to this page should always re-sign rather than reuse a cached link that might be close to `expires_at`.
5. **A successful `POST` writes straight into the `GET` query's cache** (`setQueryData`, not `refetchQueries`) — the response already *is* a fresh link, so there's no reason to make a second network call just to get the same shape back.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `tsc -b` | Clean |
| `eslint . --ext ts,tsx --max-warnings 0` | Clean |
| `prettier --check .` | Clean (2 files auto-formatted) |
| `pnpm exec vitest run` | 133 passed, no change (no new pure logic in this task to unit test beyond what NF-P3-017 already covers) |
| `pnpm run build` | Clean |

**Live browser (Firebase emulators, a fresh signed-in test worker, a `financial_profile/current` doc written directly into the emulator including `verified_employment`)**

- "No report yet" empty state renders correctly
- Preview modal: every section (period, months of data, all four metric bars with correct status colors and the `savings_rate` percentage, verified employment, narrative, disclaimer) renders correctly, **no overall score** — confirmed matches decision 2
- Escape key closes the modal; backdrop click closes it; the page behind is visually dimmed and non-interactive while open
- **Generate PDF**, tried for real: first attempt failed on `ModuleNotFoundError: No module named 'weasyprint'` — the backend venv here predates that dependency landing (NF-P3-014). Installed it (`pip install weasyprint==70.0`, already pinned in `requirements.txt`, so this was just catching the local venv up, not a requirements change) and retried: next failure was `OSError: cannot load library 'libpango-1.0-0'` — a system library weasyprint needs, missing on this Mac, exactly the gap NF-P3-014's own runbook already flagged as unverified locally. Asked you first, then installed it (`brew install pango`) and restarted the backend. Retried again: **the PDF rendered successfully this time** (`fib_report_exported size_bytes=12381` in the backend log) — proving the request my frontend sends is correctly shaped and the whole pipeline up through rendering works. It then failed one step later, signing the download link: `AttributeError: 'Credentials' object has no attribute 'service_account_email'` — this local environment's Google credentials aren't a service-account key, which is NF-P3-014's own separately-documented production prerequisite ("Let the runtime service account sign links... without it, 500"). That needs real GCP IAM setup outside this sandbox, so verification stopped there.
- Throughout all of the above, the frontend's own error handling was confirmed correct at every stage: the button shows "Generating…" while pending, a graceful inline error message appears on any failure, and the page is never left in a broken or stuck state
- Mobile (375×812) and dark mode — both clean, confirmed on the preview modal specifically (the hardest case: scrolling content, status colors, backdrop)

**Not verified:** an actual successful download_url (needs real GCP service-account signing credentials); Web Share / clipboard-copy in a real mobile browser (this environment's headless automation doesn't exercise either meaningfully).

## Manual test steps

Same emulator setup as NF-P3-016/017's runbooks, plus a `financial_profile/current` document (NF-P3-017's runbook has the exact script). To actually render a PDF locally, the backend venv additionally needs:

```bash
cd backend
.venv/bin/python -m pip install weasyprint==70.0   # already pinned in requirements.txt
brew install pango                                    # macOS; see weasyprint's own install docs for other platforms
# restart the backend process after installing pango
```

A real signed `download_url` additionally needs a GCP service account key or the IAM `serviceAccountTokenCreator` role on a real project — not available in a pure local/emulator setup; see NF-P3-014's runbook, "Before this works in production."

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Our server had a problem" on Generate, `ModuleNotFoundError: weasyprint` in the backend log | The venv predates NF-P3-014; `pip install -r requirements.txt` (or just `weasyprint==70.0`) |
| Same, but `OSError: cannot load library 'libpango-1.0-0'` | System library missing; `brew install pango` on macOS, or the Dockerfile's apt packages in a real deploy |
| Same, but `AttributeError: 'Credentials' object has no attribute 'service_account_email'` | Local ADC isn't a service-account key; this is a real-GCP-credentials requirement, not fixable locally — see NF-P3-014's runbook |
| Preview modal shows a score the real PDF wouldn't | Should never happen — if it does, check `ReportPreviewModal.tsx` didn't regain an `overall_score` render (decision 2) |

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind + shadcn/ui (reuses `Button`; the modal is hand-built, matching this app's established pattern of plain Tailwind for anything with no existing primitive)
- [x] Mobile responsive — verified live at 375×812, including the modal
- [ ] Slow network — not tested throttled
- [x] Loading states (`LoadingSpinner`, "Generating…" on the button while the mutation is pending)
- [x] Error states (inline error on a failed generate; graceful degradation confirmed through three real failure modes during live testing)
- [x] i18n keys added for all user-facing strings, all 6 languages
- [x] Screenshots — captured during live verification, sent to you directly

## Commit and PR

Branch: `feature/fib-export-ui` (already checked out).

```
feat(fib): add portable report export UI
Refs: NF-P3-018
```

## Noticed, not fixed

- The three backend/environment gaps hit during live verification (missing `weasyprint`, missing `libpango`, non-service-account local credentials) are all pre-existing and already documented in NF-P3-014's own runbook — not introduced by this task. Fixed the first two locally (useful for future local testing); the third needs real GCP credentials outside this task's reach.
