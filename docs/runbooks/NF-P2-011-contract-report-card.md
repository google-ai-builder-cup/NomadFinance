# NF-P2-011 — Contract Shield: Report Card UI

## Summary

The upload page's small result card (score, badge, three counts) is now the full Contract Health Report: every assessed clause, with its 🟢🟡🔴 flag and a side-by-side view of the clause against the labor law.

- **`ReportCard`** (new): the score header (moved out of `ContractUpload.tsx`, D-61), the plain-language summary, the pending-complaint note, then a "Clause by clause" section.
- **`ClauseRow`** (new): one clause — a colored flag dot (sr-only text carries the same words as the header badge: "Looks safe" / "Some concerns" / "Serious concerns"), its category, a `Clause {{number}} · page {{page}}` reference, then **what the contract says** next to **what the law says** (`law_reference`, or "Not tied to a specific law section" when there is none, plus the explanation and, if any, a recommendation).
- **Side by side on `md:` and up** (a shared column legend above the list), **stacked with inline labels on a phone** — each `ClauseRow` carries its own `md:hidden` labels so a stacked clause is still legible on its own.
- **The full report is read straight from Firestore**, not a new API call: `POST .../analyze` already writes `reports/{language}` before it answers (`docs/pipelines/contract-shield.md`), and `firestore.rules` already lets the owner read `contracts/{id}/reports/{language}` directly (same pattern `watchContractProgress` uses for the progress document). No backend change, no new AI-rate-limited call.
- **Loading and error states** for that read: `ReportSkeleton` (adjusted to hint at the two-column shape) while pending, an inline retry on a Firestore error, and a distinct "not ready yet" message for the one edge case where `analysis` says `completed` but the report document isn't there yet (race, should not happen given the pipeline's write order).
- The result and progress views widened from `max-w-lg` to `max-w-3xl` (still inside the app shell's `max-w-4xl`) so the side-by-side columns have room; the upload form itself stays `max-w-lg`.
- All texts in the 6 languages, including the 15 labor-law categories (`contract.category.*`) and the new `contract.report.*` strings. No backend change, no new package, no shared file changed.

## Files

| File | Change |
|---|---|
| `frontend/src/types/contract.ts` | `ClauseCategory`, `ReportClause`, `ComplaintChannel`, `ContractComplaint` (typed for NF-P2-013, not yet rendered), `ContractReport` |
| `frontend/src/services/contractService.ts` | `getContractReport()`: one-shot `getDoc` on `reports/{language}` |
| `frontend/src/hooks/useContract.ts` | `useContractReport()`: `useQuery`, `staleTime: Infinity` (same pattern as `useUserProfile`) |
| `frontend/src/utils/contractRisk.ts` (new) | `RISK_BADGE_CLASSES`, `RISK_DOT_CLASSES` — the risk→color map, pulled out of `ContractUpload.tsx`'s old inline `RISK_STYLES` so `ReportCard` and `ClauseRow` share it |
| `frontend/src/components/contract/ReportCard.tsx` (was a stub) | Score header, summary, complaint-pending note, clause list |
| `frontend/src/components/contract/ClauseRow.tsx` (was a stub) | One clause: flag, category, reference, side-by-side text |
| `frontend/src/components/contract/ReportSkeleton.tsx` | The three placeholder rows now hint at the two-column shape instead of a single line |
| `frontend/src/pages/contract/ContractUpload.tsx` | Inline result card replaced by `<ReportCard>`; `result` (and the fields it needs) moved above the `profile` early returns so `useContractReport` can be called unconditionally (Rules of Hooks); result/progress views widened to `max-w-3xl`. 293 lines (was 306; D-61's guideline is satisfied as a side effect, though the log already marked it won't-fix) |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `contract.result.reportLoadError`, `contract.result.reportMissing`; `contract.report.*` (heading, column labels, no-law-reference fallback, recommendation label, clause reference templates); `contract.category.*` (the 15 curated categories + other) |
| `docs/pipelines/contract-shield.md` | New "How the app shows the report" section; "Not covered here" note updated |

## Decisions

1. **Read the report from Firestore, not `POST .../reports/{language}`.** That endpoint exists for the language switcher (NF-P2-012, translate-on-demand) and is rate-limited as an AI call. The report the analysis already wrote is a plain owner-readable document, so the report card reads it the same way the progress card already reads `users/{uid}/contracts/{id}` (NF-P2-010). NF-P2-012 will still need the endpoint for a language that has no stored report yet.
2. **No expand/collapse, no sticky columns, no language toggle, no letter preview.** NF-P2-023 (paired, interactions & polish) and NF-P2-012/NF-P2-013 own those; this task renders every clause in a plain list and stays inside its own scope.
3. **The per-row mobile labels ("What the contract says" / "What the law says") repeat under `md:hidden`,** rather than relying only on the shared legend above the list, because a stacked clause card should be legible on its own without scrolling back up to the legend.
4. **`ReportClause`/`ContractReport` are typed in full**, including `complaint` (`ContractComplaint`), even though nothing renders it yet — it's real API-response shape (`contracts.md`), and NF-P2-013 can use the type directly instead of re-deriving it.
5. **The "report missing" state is separate from "report failed to load."** A Firestore error is retried the same as any other network hiccup; a `null` document (analysis says `completed` but the report Firestore should already hold isn't there) says so plainly, since it points at a real inconsistency rather than a transient failure — both offer the same retry button.

## Manual test steps

No backend or Gemini needed: this task only reads a Firestore document the pipeline already writes, so the fastest check is to seed that document directly, the same way the NF-P2-010 runbook verified its success path "without Gemini."

**PowerShell**

```powershell
firebase emulators:start --only auth,firestore --project demo-nomadfinance
```

**bash** (same command)

```bash
firebase emulators:start --only auth,firestore --project demo-nomadfinance
```

Second terminal, from `frontend/`:

```bash
pnpm dev --mode emulator
```

1. Open **http://localhost:5173** (not `127.0.0.1`), sign in with any phone number (the emulator shows the code in the first terminal), finish onboarding.
2. Open the Emulator UI (http://localhost:4000 → Firestore) and under `users/{your uid}/contracts` create a document with `status: "completed"`, `health_score`, `risk_level`, `clause_counts`, `host_country`, `job_type`, `report_languages: ["en"]` (see `docs/data-model/collections/contracts.md` for the shape).
3. Under that contract's `reports` subcollection, create document id `en` with `language: "en"`, `is_source: true`, `summary`, and a `clauses` array covering at least one `safe`, one `caution` and one `danger` clause, one clause with `law_reference: null`, and one with `recommendation: null` (see the same doc for the shape).
4. Go to **Check a contract**; since the page only shows a result after its own upload/analyze mutation runs, the fastest way to see the card render against seeded data is to temporarily point `contractId`/`result` at the seeded ids (or re-run the actual upload flow once a backend is available) — this task's own verification used a throwaway fixture route rendering `<ReportCard>` directly with equivalent data (see "Verified results" below); either path exercises the same component.
5. Check: the score, badge and three counts at top; the summary paragraph; each clause shows the right colored flag, category, `Clause N · page P` (or just `Page P` when `number` is null), the clause text, then the law reference (or the fallback text) and explanation, and the recommendation only when one exists.
6. DevTools → phone size (375 px): clauses stack, each with its own "What the contract says" / "What the law says" labels, no sideways scroll.
7. Desktop width: the shared column legend appears above the list and each clause becomes two equal columns.
8. Unplug the emulator or delete the `en` report document after the contract still says `completed`, reload: the "report isn't ready" message and its Retry button appear.

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| `tsc -b` | Pass |
| `pnpm lint` (max warnings 0) | Pass |
| `prettier --check --end-of-line auto` | Pass |
| `vitest run src` | 36 passed (2 files; unchanged — no new test file, see "Not covered here") |
| `pnpm build` | Pass (PWA precache 33 entries) |

**Live, in the browser** — a temporary route rendered `<ReportCard>` directly with fixture data (3 safe, 1 caution, 1 danger; one clause with `law_reference: null`; one with a `recommendation`; `complaint_pending: true`), then the route and its fixture file were removed before committing:
- Header, badge, three counts, summary and the pending-complaint note all rendered correctly.
- At the pane's natural (narrow) width: each clause stacked with its own "WHAT THE CONTRACT SAYS" / "WHAT THE LAW SAYS" labels, correct flag color per clause, and the `law_reference: null` clause showed "Not tied to a specific law section" instead of a blank.
- At 375 px: `document.documentElement.scrollWidth === window.innerWidth` (no horizontal scroll).
- At 1100 px (above the `md:` breakpoint): confirmed via computed styles, not a screenshot (the pane scales an emulated width down to fit, which made a wide screenshot misleading) — the legend and every clause's grid became two ~345 px columns, and the mobile-only labels became `display: none`.
- `sr-only` risk text read correctly per clause via `get_page_text` ("Looks safe", "Some concerns", "Serious concerns").

**Not run:** the real upload → analyze → report flow end to end (would need the backend, Firestore-backed repos and either scripted or live Gemini answers, as NF-P2-008 and NF-P2-010 used). The component reads a plain Firestore document regardless of how it got written, so this is a low-risk gap, but it should be exercised once during NF-P2-008-style regression testing or whenever the pipeline is next run live end to end.

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind + shadcn/ui (`Skeleton`, `Button`)
- [x] Fully mobile responsive (375 px, no sideways scroll; verified)
- [ ] Works on slow network: not separately simulated for this task (no new network call — the report read is a single Firestore `getDoc`; NF-P2-010's slow-network coverage of the surrounding page still applies)
- [x] Loading states: `ReportSkeleton` while the report document loads
- [x] Error states: Firestore read failure (retry) and the missing-document edge case (retry, distinct message)
- [x] i18n keys for all user-facing strings (6 languages), including the 15 law categories
- [ ] Screenshots added to PR: take them when opening the PR (header, clause list narrow and wide, missing-report state)
- [x] Accessibility: semantic `<ul>/<li>`, `<dl>` for the counts, `<h2>` section heading, sr-only risk words reusing `contract.result.riskLevel.*`, native `role="alert"` + `Button` for the error states

## For teammates

- **Pranjal (NF-P2-012, language switch):** the language toggle should call `getContractReport` (or the `POST .../reports/{language}` endpoint for a language with no stored document yet) and can reuse `useContractReport`'s query key shape (`["contractReport", uid, contractId, language]`) — invalidate/refetch it per language rather than inventing a new cache.
- **Pranjal (NF-P2-023, report polish, paired):** `ReportCard`/`ClauseRow` render every clause in a plain list with no interactivity yet — expand/collapse, the risk-score tooltip and sticky columns all still need to land here.
- **Aditya (NF-P2-013, letter):** `ContractReport.complaint` is already typed (`ContractComplaint`, `ComplaintChannel`) and present on the document `useContractReport` reads; `ComplaintPreview.tsx` is still an empty stub.
- **Pranjal (NF-P3-023, radar warning on the report):** nothing here reads `radar_entities/`; the report card has no employer/agency display yet to hang a badge on (that data is on the contract document's `extracted` map, not the report).
- **Everyone:** the report is only fetched once analysis has produced a `contract_id` and `report_language` (`useContractReport`'s `enabled` guard) — it will not fire during the upload/progress phase.

## Commit and PR for this task

Branch: `feature/contract-report-card` (already checked out).

```bash
git add frontend/src docs/runbooks/NF-P2-011-contract-report-card.md docs/pipelines/contract-shield.md
git status
```

```bash
git commit -m "feat(contracts): add clause-by-clause report card with law comparison" -m "Refs: NF-P2-011"
```

PR title: `feat(contracts): clause-by-clause report card with side-by-side law comparison (NF-P2-011)`

## Not covered here

- Language switch, complaint letter preview/download: NF-P2-012, NF-P2-013
- Expand/collapse, risk-score tooltip, sticky side-by-side columns, final mobile tuning: NF-P2-023 (paired)
- Radar "community flagged" badge on the report: NF-P3-023
- A component-level test file for `ReportCard`/`ClauseRow` (none of the other contract components have one yet either, only `pipelineProgress.ts`'s pure functions do)
