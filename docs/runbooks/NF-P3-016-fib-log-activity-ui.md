# NF-P3-016 — FIB: Log Activity UI

Originally assigned to Devam; picked up on your confirmation.

## Summary

The worker-facing form for logging Financial Identity activity by hand: four tabs (Income, Transfer, Bill, Savings) on `/identity`, feeding the already-live `POST /fib/income`, `/fib/bill`, `/fib/savings` (NF-P3-010) and `/fib/bill/scan` (NF-P3-011) endpoints. None of the FIB frontend plumbing existed before this task — `types/fib.ts`, `services/fibService.ts` and `hooks/useFIB.ts` were all empty stubs — so this is the first task to populate that layer.

Transfer turned out not to be a quick-entry form like the other three: `POST /remittance/log` needs the entire unmodified `RemittanceComparison` object plus a chosen `rpw_id`, never a free-typed amount, and nothing in the frontend called that endpoint yet despite the original design describing a transfer as "auto from Pillar 1." Flagged this to you before building (tasks.md's literal "Tabs for Income/Transfer/Bill/Savings" description doesn't match how the data model actually works) — confirmed building the missing "I used this" action on the Remittance comparison table instead of duplicating the compare flow inside FIB, with the Transfer tab here reduced to a short explainer + link.

## Files

| File | Change |
|---|---|
| `types/fib.ts` (was an empty stub) | Request/response types for all four entry kinds, mirroring `backend/app/schemas/fib.py` wire-for-wire |
| `services/fibService.ts` (was an empty stub) | `logIncome`, `logBill`, `scanBill` (multipart), `logSavings` |
| `hooks/useFIB.ts` (was an empty stub) | One mutation per service function, `retry: false` — each stores an entry the moment it succeeds, so a retry would double-log it |
| `utils/fibForm.ts` (new) | `HOST_CURRENCY` map, `parseAmount` (no survey-range bound, unlike `utils/corridors.ts`'s), `scanFailureKey` |
| `components/fib/styles.ts` (new) | Shared `fieldClass`, mirrors `components/profile/styles.ts` |
| `components/fib/IncomeForm.tsx`, `SavingsForm.tsx` (new) | Quick manual-entry forms |
| `components/fib/BillPhotoPicker.tsx` (new) | Dropzone + camera-capture picker, its own fib-scoped copy of `components/contract/UploadDropzone.tsx`'s pattern |
| `components/fib/BillForm.tsx` (new) | Photo mode (→ `scanBill`) and manual mode (→ `logBill`), switchable |
| `components/fib/ActivityLogger.tsx` (was an empty stub) | The tab switcher; a successful log shows a toast and remounts the active form via a bumped `key` |
| `pages/fib/FIBLogActivity.tsx` (was an empty stub) | Thin page wrapper, mirrors `pages/radar/RadarReport.tsx`'s shape |
| `router.tsx` | `/identity` now renders `FIBLogActivity` (was `ComingSoon`) |
| `types/remittance.ts` | `TransferLogRequest`/`TransferLogResponse` |
| `services/remittanceService.ts` | `logTransfer` |
| `hooks/useRemittance.ts` | `useLogTransfer` |
| `components/remittance/ComparisonTable.tsx` | `onLog`/`pendingRpwId`/`loggedRpwIds` props — every comparable row gets its own "I used this" button, not just the best one |
| `pages/remittance/RemittanceCompare.tsx` | Wires the mutation, toasts on success/failure |
| `i18n/{en,hi,tl,id,ne,bn}.json` | New `fib.*` and `remittance.table.logAction.*` keys, genuinely translated in all 6 |

No backend changes — every endpoint used here already existed.

## Decisions

1. **Transfer is an explainer + link, not a form.** `/remittance/log` requires the comparison object the compare step already produced; a worker typing a bare amount into a Transfer tab here would have nothing valid to send. Confirmed with you before building, since this is the one place tasks.md's literal task description and the actual backend/data model disagree.
2. **The "I used this" action lives on `ComparisonTable`/`RemittanceCompare`, not inside FIB**, because that's where the comparison data worth logging actually exists — no frontend code called `/remittance/log` anywhere before this task, despite the endpoint being built back in NF-P2-017.
3. **Every comparable row gets its own log button**, not just the top-ranked one — a worker may not have used the cheapest service, and the row data (`rpw_id`) needed to log it is already right there per row.
4. **`BillPhotoPicker` is its own fib-scoped copy** of `UploadDropzone.tsx`'s dropzone-plus-camera-capture pattern, not a shared import — same precedent as `EvidencePicker.tsx` vs `UploadDropzone.tsx` already being two independent implementations for two different pillars.
5. **Currency is a closed picker of the six host currencies** (`HOST_CURRENCY`), not the backend's open ISO 4217 pattern — a short, typo-free list matching what a worker here will ever actually type, defaulting to their own host country's currency.
6. **A successful log shows a toast and resets the form in place** (remount via a bumped `key`), instead of navigating to a confirmation screen like the multi-step radar report — fits "quick entry": the worker can log several entries back to back without re-navigating.
7. **Resetting which rows show "Logged" on a new comparison uses React's render-time state-adjustment pattern, not a `useEffect`.** The first version called `setLoggedRpwIds` inside an effect keyed on `compare.data` and tripped `react-hooks/set-state-in-effect`; fixed by comparing against a `loggedFor` ref during render instead.
8. **Bill-scan's two known English 422 rejection texts are mapped to translated keys by prefix match** (`scanFailureKey`), mirroring `utils/radarForm.ts`'s existing `reportFailureKey` for the radar report's own screening rejections — same reasoning: the backend's own text there is English only (D-10), so the frontend matches on it rather than re-wording it.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `tsc -b` | Clean |
| `eslint . --ext ts,tsx --max-warnings 0` | Clean (one issue found and fixed: `react-hooks/set-state-in-effect` in `RemittanceCompare.tsx`, see decision 7) |
| `prettier --check .` | Clean (3 files auto-formatted) |
| `pnpm exec vitest run` | 124 passed, 11 test files passed. The 2 Firestore/Storage rules test files need `pnpm test:rules`'s `firebase emulators:exec` wrapper to run at all — pre-existing, unrelated to this change |
| `pnpm run build` | Succeeds (pre-existing >500kB main-chunk warning, not materially changed by this task) |

**Live browser (Firebase Auth + Firestore emulators, a real signed-in test worker, onboarded SG→India)**

World Bank corridor pricing wasn't seeded in the emulator yet, so I ran `python -m src.loaders.corridors` against it first (`FIRESTORE_EMULATOR_HOST=127.0.0.1:8085`) to get a real comparison to log against.

- **Income tab** — submitted a salary entry; backend logged `fib_income_logged`, 201, toast "Logged.", form reset
- **Bill tab, photo mode** — dropzone and "Take a photo" camera-capture button render correctly; didn't invoke Gemini since the local emulator has no real key (`GEMINI_API_KEY=not-used-here` in `.claude/launch.json`) — that call path is NF-P3-011's own, already built and tested in its task
- **Bill tab, manual mode** — submitted a phone bill; first pass through the "paid" checkbox used the wrong `form_input` value type and logged `paid=False` — re-tested with a real click and confirmed the backend log showed `paid=True`, so the checkbox itself is correct, that first result was a test-harness mistake, not a bug
- **Savings tab** — submitted a deposit; 201, toast, reset
- **Transfer tab** — shows the explainer and the link to `/remittance`
- **Remittance "I used this"** — ran a real SG→IN comparison, clicked "I used this" on the Wise row: toast "Transfer logged.", that row switched to a "Logged" badge, every other row's button stayed enabled; backend confirmed `POST /remittance/log` 201
- **Mobile (375×812)** and **dark mode** — both render cleanly across every new component (tabs, forms, the bill photo picker, the savings direction toggle)

**Not live-verified:** actual Gemini Vision extraction on `/fib/bill/scan` (needs a real `GEMINI_API_KEY`, outside this task's scope) and a throttled-3G pass (no network-throttle control in the tooling used).

## Manual test steps

**bash**
```bash
cd data-scripts
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \
  .venv/bin/python -m src.loaders.corridors   # only needed once per fresh emulator
```
Then start, in separate terminals (or via `.claude/launch.json`'s `backend-emulators`, `backend-api-emulator`, `frontend-emulator` configs): the Auth+Firestore emulators, the backend pointed at them, and `pnpm dev --mode emulator` from `frontend/`. Sign in at `/sign-in` by phone (any number works; read the SMS code from `curl http://127.0.0.1:9099/emulator/v1/projects/demo-nomadfinance/verificationCodes`), finish onboarding, open `/identity`.

**PowerShell** — same three services, started from their own terminals per `.claude/launch.json`; everything after that is browser-driven and identical.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Prices for this corridor aren't available yet" on `/remittance` | Corridor pricing isn't seeded in a fresh emulator — run the `src.loaders.corridors` command above |
| Bill photo scan always fails locally | `GEMINI_API_KEY` is a placeholder in the local emulator config; needs a real key to actually call Gemini Vision (NF-P3-011) |
| Clicking a second "I used this" button does nothing | By design — every row's button disables while any one log request is in flight (`pendingRpwId`), so a second click mid-request is a no-op, not a bug |
| A bill amount with 3+ decimal places is rejected | Intentional — `utils/fibForm.ts`'s `parseAmount` caps at 0 decimals for JPY/KRW and 2 for everything else, matching real currency minor units |

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind + shadcn/ui (reuses `Button`; the rest is plain Tailwind matching the existing radar/profile form pattern)
- [x] Mobile responsive — verified live at 375×812
- [ ] Slow network — not tested throttled; worth a manual DevTools pass before the next release
- [x] Loading states (`disabled` + "Logging…"/"Reading the bill…" text on every submit button, including the new per-row "Logging…" state on Remittance Compare)
- [x] Error states handled (inline errors on every form; bill-scan's known rejections translated; remittance log errors go to a toast)
- [x] i18n keys added for all user-facing strings, genuinely translated in all 6 languages
- [x] Screenshots — captured during live verification, sent to you directly

## Commit and PR

Branch `feature/fib-log-activity-ui`, commit `e2e13c2`, merged to `main` via PR #93 ("feat: FIB log activity UI with cross-pillar transfer logging (NF-P3-016)").

```
feat(fib): add log activity ui with cross-pillar transfer logging
Refs: NF-P3-016
```

## Noticed, not fixed

- No "recent entries" list on this page — that's NF-P3-017's Financial Timeline Dashboard, not this task's scope.
- Bill-scan's live Gemini Vision path is code-complete but not live-verified here (no real key in local dev) — already built and tested in NF-P3-011's own task.
