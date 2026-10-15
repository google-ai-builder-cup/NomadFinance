# NF-P2-009 — Contract Shield: Upload UI

Written retroactively (2026-09-28): this task was already implemented and merged (PR #48, commit `5df4388`) before this runbook existed. The **Decisions**, **Files** and **Flow** sections below describe what commit `5df4388` actually built, read straight from that commit; **Verified results** were re-run now, against the current branch, rather than reconstructed from that day. No code changed to produce this file.

## Summary

The Contract Shield pillar's `/contract` route went from `ComingSoon` to a working upload form: drag-and-drop or camera capture for one file, a host-country and report-language picker (each defaulting from the worker's profile, either overridable), and a single submit that reads the file and analyses it in one request.

- **`UploadDropzone`** (new): `react-dropzone` for drag-and-drop/browse, a separate `capture="environment"` file input for "Take a photo" (a dropzone's own input can't set `capture`), a preview (thumbnail for an image, a file icon for a PDF) with name, size and a remove button, and inline messages for a rejected file (too large, wrong type).
- **`useUploadAndAnalyzeContract`** (new hook): one mutation wrapping both backend calls — `POST /api/v1/contracts` (step 1, read and store), then `POST /api/v1/contracts/{id}/analyze` (steps 2–6) — unless step 1 comes back `legibility: "poor"`, in which case analysis is skipped and the form asks for a clearer photo.
- **Country and language pickers** default to the signed-in worker's profile (`host_country`, `preferred_language`) and fall back to the first supported host country / English when the profile has neither; either field can still be changed for this one check.
- **Result:** a small card (score, risk badge, the three clause counts) — a stand-in the same commit's message called out as temporary; NF-P2-011 replaced it with the full report card.
- `frontend/package.json` gained `react-dropzone` (a shared file; the addition was reviewed and merged with the rest of PR #48 at the time — no new shared-file change here).
- All texts in the 6 languages (`contract.upload.*`, `contract.result.*`, plus `common.or`).

## Files (as changed by commit `5df4388`)

| File | Change |
|---|---|
| `frontend/src/components/contract/UploadDropzone.tsx` (new) | Drag-and-drop, browse, camera capture, file preview, rejection messages |
| `frontend/src/services/contractService.ts` (new) | `uploadContract()`, `analyzeContract()` — thin wrappers over `apiRequest` |
| `frontend/src/hooks/useContract.ts` (new) | `useUploadAndAnalyzeContract()`: the combined upload-then-analyze mutation |
| `frontend/src/types/contract.ts` (new) | `Legibility`, `ClauseRisk`, `ClauseCounts`, `ContractUploadResponse`, `AnalyzeRequest`, `ContractAnalysis`, `PipelineErrorCode` |
| `frontend/src/pages/contract/ContractUpload.tsx` (new) | The form, the small result card, profile-loading and profile-error states |
| `frontend/src/router.tsx` | `/contract` now renders `ContractUpload`; every other pillar still shows `ComingSoon` |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `common.or`; `contract.upload.*` (title, dropzone label/hint, take-photo, remove, 3 rejection messages, host country + hint, report language, analyzing, submitting, submit, poor-legibility, profile-load-error); `contract.result.*` (title, subtitle, score, 3 risk levels, 3 counts, complaint-pending, analyze-another) |
| `frontend/package.json`, `frontend/pnpm-lock.yaml` | `react-dropzone` `20.1.2` added |

## Decisions

1. **One client-side mutation for two backend calls.** The upload UI only needs a single "Check my contract" action; `useUploadAndAnalyzeContract` calls `POST /contracts` then `POST /contracts/{id}/analyze` back to back, mirroring the flow the NF-P2-007 runbook documents.
2. **`poor_legibility` is not an error.** When step 1 reports `legibility: "poor"`, the mutation resolves successfully with `analysis: null` instead of throwing; the page clears the file and shows a banner asking for a clearer photo, rather than routing it through the generic error path.
3. **Camera capture is a second control, not part of the dropzone.** `react-dropzone`'s own `<input>` has no way to set `capture="environment"` (it would also accept any file type on a phone's system picker), so "Take a photo" is a separate `<label>` wrapping a plain `<input type="file" accept="image/*" capture="environment">`.
4. **Client-side file checks mirror the backend, they don't replace it.** `ACCEPTED_TYPES` and `MAX_SIZE_BYTES` in `UploadDropzone.tsx` match `app/utils/validators.py` and `UPLOAD_MAX_BYTES` (`app/config.py`) so a bad file is rejected before a slow upload over a weak connection, but the backend's own check is what actually matters.
5. **Country and language each fall back independently.** `effectiveHostCountry` = the worker's pick this session, else `profile.host_country`, else the first `HOST_COUNTRIES` entry. `effectiveReportLanguage` = the worker's pick, else `profile.preferred_language` (if it's a supported code), else `"en"`. Neither fallback writes back to the profile; it only decides what the select shows and what gets submitted.
6. **The result card is a stand-in.** The commit message and code both call it temporary — score, badge, three counts, nothing else. NF-P2-010 added the processing steps in front of it; NF-P2-011 replaced the card itself with the full clause-by-clause report.

## Flow

```
Worker picks or drops a file (or takes a photo)
  client-side check: type in ACCEPTED_TYPES, size ≤ 10 MB → inline rejection message if not
Worker picks host country / report language (or keeps the profile defaults)
Submit
  POST /contracts (file)                → { contract_id, legibility, ... }
    legibility "poor"                   → clear the file, show the poor-legibility banner, stop
    else
  POST /contracts/{id}/analyze (choices) → ContractAnalysis
  result card: score, risk badge, safe/caution/danger counts
"Check another contract"                 → reset the form
```

## Manual test steps

From `frontend/`. In PowerShell, `pnpm.cmd` if `pnpm` is blocked by the execution policy.

### 1. Checks

```bash
pnpm install --frozen-lockfile
pnpm exec tsc -b
pnpm lint
pnpm exec prettier --check src
pnpm exec vitest run src
pnpm build
```

On Windows with CRLF checkouts, use `pnpm exec prettier --check --end-of-line auto src`.

### 2. Try it in the browser

A backend is only needed to see a real result; the form, file picker and validation can be checked against a plain `pnpm dev` with no backend running (the submit itself will fail with a network error, which is enough to see the form's own behavior).

1. `pnpm dev`, open the app, sign in, finish onboarding, go to **Check a contract** (Dashboard → Contract Shield, or `/contract` directly).
2. Drag a PDF onto the dropzone: it shows the file icon, name and size, with a remove (✕) button.
3. Pick an image instead: a thumbnail preview shows in place of the icon.
4. Drop a `.txt` file or a file over 10 MB: the matching rejection message appears (`badType` / `tooLarge`), the file is not accepted.
5. On a phone (or DevTools mobile emulation with camera access), "Take a photo" opens the camera directly rather than a file browser.
6. Change the host country and report language selects; reload the page (still signed in) and confirm they reset to the profile's own values (the session choice is not persisted).
7. With a backend running (see the NF-P2-010 runbook for the full emulator + backend setup), submit a real contract: the button shows "Checking…", disables the form, and either the result card or the poor-legibility banner appears.
8. DevTools → phone width (375 px): no sideways scroll; the dropzone, selects and button all stay full width.
9. Keyboard only: Tab reaches the dropzone (native input, focus ring), the remove button, both selects and the camera button.

## Verified results (re-run 2026-09-28, retroactively, on the current branch)

| Check | Result |
|---|---|
| `tsc -b` | Pass |
| `pnpm lint` (max warnings 0) | Pass |
| `prettier --check --end-of-line auto` | Pass |
| `vitest run src` | 36 passed (2 files — no test file was added for this task; see "Not covered here") |
| `pnpm build` | Pass |

These are the current branch's checks (`feature/contract-report-card`, which already carries NF-P2-010 and NF-P2-011 on top of this task), not a fresh checkout of commit `5df4388` alone — the two later tasks changed `ContractUpload.tsx` and the i18n files further. No separate live-browser pass was re-run for this retroactive write-up; the feature has been in `main` since PR #48 and exercised indirectly by every later contract-report session in this branch's own testing (NF-P2-010, NF-P2-011 runbooks).

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind + shadcn/ui (`Button`, lucide icons)
- [x] Fully mobile responsive (full-width controls, no fixed widths)
- [ ] Works on slow network: not separately recorded for this task; NF-P2-010's runbook covers slow-network behavior for the page built on top of it
- [x] Loading states: `LoadingSpinner` for the profile load and (at the time) an inline "Checking your contract…" line while the mutation ran — replaced by the step-by-step progress card in NF-P2-010
- [x] Error states: profile load failure (retry), poor legibility (banner, file cleared), a failed upload/analyze request (inline message)
- [x] i18n keys for all user-facing strings (6 languages)
- [ ] Screenshots added to PR: not recorded; PR #48 predates this runbook
- [x] Accessibility: native `<label>`/`<select>`/`<input>` elements, `aria-label` on the dropzone input and the remove button, `role="alert"` on rejection and error messages

## For teammates

- **Devam (NF-P2-010, processing animation):** superseded the inline "Checking your contract…" spinner with the step-by-step progress card; see that runbook.
- **Aditya (NF-P2-011, report card):** superseded the small result card here with the full clause-by-clause report; see that runbook.
- **Anyone touching `UploadDropzone.tsx`:** `ACCEPTED_TYPES` / `MAX_SIZE_BYTES` must stay in sync with the backend's `app/utils/validators.py` and `UPLOAD_MAX_BYTES` if either changes.

## Not covered here

- No component-level test file was added for `UploadDropzone` or `ContractUpload` (the first test file for this pillar, `pipelineProgress.test.ts`, came with NF-P2-010).
- The processing/progress UI, retry, full report, language switch, complaint letter: NF-P2-010 to NF-P2-013.
