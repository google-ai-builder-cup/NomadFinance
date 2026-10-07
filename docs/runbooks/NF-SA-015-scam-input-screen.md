# NF-SA-015 — Scam check input screen and PWA share target

## Summary

`/scam-check` is now the screen where a worker hands in a message: paste it, upload or photograph a screenshot, or **share it from WhatsApp straight into the installed app**. All three fill the same form and leave through one function (`submit`) that calls `POST /api/v2/scam/analyze`. The "Coming soon" placeholder is gone. The verdict card is NF-SA-016, so the answer is shown by a plain interim panel.

The page is behind the `scam` feature flag, as before.

## What the worker sees

| Step | Screen |
|---|---|
| Choose | Two buttons, **Paste text** and **Screenshot** |
| Paste | A text box with a counter (`80 / 4000`). Over 4,000 characters the box turns red, says so, and the button stays off. The message is never cut: the payment request is often at the end |
| Screenshot | Drop zone, and a **Take a photo** button (`capture="environment"`). JPEG, PNG or WebP up to 5 MB, checked before upload; a preview with a remove button |
| Send | **Check this message**, disabled until there is something valid to send |
| Waiting | A spinner; after 8 s the text says a suspicious message can take up to a minute (the explainer has taken 15 to 40 s; the client allows **90 s**: see below) |
| Answer | A risk badge, the title, what the sender wants and 3 next steps (scam) or a reassurance and a tip (not a scam); a note when the explainer could not be written; **Check another message** |
| Failure | A red notice in plain words, with **Try again** only where trying again can help |

Failure messages by backend code (`utils/scamErrors.ts`):

| Backend | Message | Try again |
|---|---|---|
| 413 | Image too large | no |
| 415 | Use a JPEG, PNG or WebP | no |
| 422 `image_unreadable` | No message could be read; clearer screenshot or paste | no |
| 422 other | Message empty or too long | no |
| 429 | Used all checks this hour; **"about N min"** from `Retry-After` | no |
| 502, 503 `ai_*` | Checker busy | yes |
| 504, or the 90 s timer | Took too long | yes |
| no connection, 5xx, 401 | The shared `errors.*` messages | as `errors.ts` says |

A failed check keeps what the worker typed or chose. **Nothing retries by itself**: a retry spends one of the 20 checks an hour (`retry: false`).

## The share target

`vite.config.ts` adds to the manifest:

```json
"share_target": { "action": "/scam-check", "method": "GET", "params": { "title": "title", "text": "text", "url": "url" } }
```

After the app is installed, **Share → NomadFinance** in WhatsApp (or any app that shares text) opens `/scam-check?text=…`. The page joins `title`, `text` and `url` (leaving out a part another part already contains), puts the result in the paste box, shows "We added the message you shared", and cleans the address so a reload does not bring it back. **It does not send it**: a check spends the worker's hourly budget, so the worker reads it and taps Check.

A worker who is signed out is sent away from this address by `ProtectedRoute`. `main.tsx` therefore keeps the shared message in `sessionStorage` before the router runs, for 10 minutes and for that tab only (a shared phone must not show it to the next person). The check screen picks it up, once, when the worker opens it after signing in. See D-153.

## Files

| File | Purpose |
|---|---|
| `src/pages/scam/ScamCheckHome.tsx` | The screen: mode, form state, share arrival, the one `submit` |
| `src/components/scam/MessageInput.tsx`, `ScreenshotPicker.tsx`, `AnalyzingProgress.tsx`, `ScamErrorNotice.tsx`, `InterimResult.tsx` | The parts. `InterimResult` is replaced by NF-SA-016 |
| `src/hooks/useScamAnalyze.ts`, `src/services/scamService.ts`, `src/types/scam.ts` | Mutation, request (JSON or form, 90 s timer) and the answer's types |
| `src/utils/scamInput.ts`, `src/utils/scamErrors.ts` | Limits and counting, share parsing and the kept message; error code to message |
| `src/services/apiClient.ts` | Reads the **v2 error envelope** (`code`) when there is no v1 `detail`, and `Retry-After` (first step of D-99; v1 behaviour unchanged) |
| `src/main.tsx` | Keeps a shared message across the sign-in redirect |
| `vite.config.ts` | `share_target` in the manifest |
| `src/i18n/scam/*.json` (6) | New strings in en, hi, tl, id, ne, bn |
| tests (5 new files) | Below |

Not touched: `package.json`, the lock file, `tsconfig*`, workflows (react-dropzone, MSW and Testing Library were already dependencies). No backend change.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Share target scope | Text and links only (GET). An image share needs a POST target and a custom service worker; see D-153 |
| 2 | Answer view | A plain interim panel on the same page, so the flow works end to end before NF-SA-016 |
| 3 | Language | The language the app is shown in (profile language, or the quick switch for this tab), if it is one of the six, else English. The explainer is written in it |
| 4 | Corridor | The profile's host and home country as `SG-IN`, only when that is one of the six corridors; otherwise left out (the backend takes none) |
| 5 | The `File` name | Sent explicitly in the form: a part without a file name is read as a text field |
| 6 | Camera photos | `capture` does not enforce a type or size, so the same checks run on them. An iPhone photo that arrives as HEIC is told to use JPEG, PNG or WebP (the backend's own 415) |
| 7 | Client timeout | **90 s, not the contract's 60 s.** On 2026-10-07, with the free-tier Gemini key rate-limited, one check took 73 s (verdict retry, then the explainer's fallback also limited, then the 40 s step budget) and still answered `200` with `explainer: null`; at 60 s the screen had already shown "took too long". A fix on the backend side (billing on the key) makes this rare |

## Manual test

Dev server with the emulators and the API as in `NF-F0-005-backend-feature-flags.md`, signed in, with the `scam` flag on for the test user. Without a Gemini key the answer is a 5xx and the failure state shows; for the full path use the tests.

1. Open `http://localhost:5173/scam-check`. Paste text, watch the counter, check the button is off when empty and over 4,000 characters.
2. Switch to **Screenshot**, choose a PNG, remove it, choose another. Try a `.gif`: it is refused before upload.
3. **Share, desktop**: open `http://localhost:5173/scam-check?text=Pay%20800%20SGD%20today`. The box is filled, the notice shows, the address becomes `/scam-check`, and nothing is sent until you tap the button.
4. **Share, Android** (not possible in CI): deploy or tunnel an HTTPS build, open it in Chrome, **Install app**, then in WhatsApp long-press a message → Share → **NomadFinance**. The installed app opens on the check screen with the message in the box. If the app is not in the share sheet, uninstall and reinstall it: Chrome reads the manifest at install.
5. Throttle to Slow 3G and check the waiting text, then offline and check the failure notice.

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `tsc -b`, `eslint --max-warnings 0`, `prettier --check`, `node scripts/check-i18n.mjs` | clean (850 English keys, 6 languages) |
| `vitest run src` | **430 passed** (52 files); 44 are new: 15 on the screen against the mock API, 5 on the service, 3 on the API client, 21 on input and error rules |
| `pnpm build` | passes; `dist/manifest.webmanifest` contains the `share_target` |
| Browser preview of every state at 375 px (box, over the limit, picker, waiting, both failure notices, answer) | rendered correctly (checked in a throwaway page, removed) |
| What the page tests prove | paste sends JSON with the language and corridor; a screenshot sends a form; a share fills the box, cleans the address and sends nothing; all three reach the same route; 429 shows the wait and no retry; unreadable image; busy then Try again repeats the same request; explainer missing; a kept message is used once |

**Not verified:** sharing from WhatsApp on a real Android phone with the installed PWA, a real Gemini answer, a screen reader pass, and a Playwright end-to-end test of this screen (it needs sign-in).

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind and the shared UI kit
- [x] Mobile responsive (375 px checked in the browser pane)
- [ ] Slow network (3G throttled in DevTools): the waiting text is built for it; the throttled run is a manual step above
- [x] Loading state: spinner and the slow-answer text
- [x] Error states: every backend code, offline and timeout
- [x] i18n keys in all 6 languages
- [ ] Screenshots in the PR (take them from the manual test)
- [x] Keyboard and semantic: real buttons and labels, `aria-pressed`, `role="alert"` and `role="status"`
- [ ] Reviewed by a teammate

## Commit

Branch: `feature/NF-SA-015-scam-input-screen`.

```bash
git commit -m "feat(scam): add check screen with upload, camera and share target" -m "Refs: NF-SA-015"
```

PR title: `feat(scam): scam check input screen and PWA share target (NF-SA-015)`
