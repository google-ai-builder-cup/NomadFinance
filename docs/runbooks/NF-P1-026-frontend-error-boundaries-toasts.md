# NF-P1-026 — Error Boundaries + Toast Notifications

## Summary

A crash no longer leaves a blank page. Pages that throw show a translated **"Something went wrong"** screen with **Try again** and **Go to home**. Inside the app shell the header and navigation stay, and Try again re-renders the page without a reload. Outside the shell (landing, sign-in, onboarding) the same screen fills the page. A root boundary catches anything outside the router and reloads on Try again.

A small **toast system** (`toast()` works anywhere, even outside React) shows short messages at the bottom of the screen: above the tab bar on phones, bottom-right on wider screens. Screen readers announce each one. Toasts close by themselves (6 s, errors 10 s), stay open while hovered or focused, and can carry one action button.

**TanStack Query errors** use it globally:
- a background refresh that fails while older data is on screen shows a toast with **Try again**
- a failed save shows a toast unless the page shows the error itself (`meta: { inlineError: true }`)
- messages are plain and translated: offline, server problem, too many requests, session ended
- 4xx answers are no longer retried automatically

Crashes are counted in Analytics (`exception`, error type and page path only).

Two PWA fixes found on the way (D-42):
- **The service worker cached almost nothing.** A typo in `globPatterns` meant only the 7 icons were cached, so the app did not open offline. It now caches the whole built app (33 files, about 1.3 MB).
- **The stale version after a deploy came from Firebase Hosting's default 1-hour cache on `index.html`.** Everything except `/assets/**` is now sent with `no-cache`.

When a new version is deployed, people see **"A new version of NomadFinance is ready. [Refresh]"** and choose when to load it; the app also checks every hour. The **install offer** is now a toast on every page, signed in or not:
- **Chrome, Edge and Android:** an **Install** button that opens the browser's own dialog.
- **iPhone and iPad (Safari, Chrome):** "tap Share, then Add to Home Screen" steps, because iOS has no install prompt.
- **Closing the offer** hides it for 14 days.

All text is in the six languages.

## Files

| File | Purpose |
|---|---|
| `frontend/src/hooks/useToast.ts` | Toast store: `toast()`, `dismissToast()`, `useToasts()` (same id replaces, max 3, `duration: null` = stays, `onDismiss` for the close button) |
| `frontend/src/components/common/Toast.tsx` | `Toaster`: the on-screen toasts, live region, pause on hover/focus, action and close buttons |
| `frontend/src/components/common/ErrorFallback.tsx` | The "Something went wrong" screen (inline or full screen) |
| `frontend/src/components/common/ErrorBoundary.tsx` | Root boundary (class component: React has no hook for this); Try again = reload |
| `frontend/src/components/common/RouteError.tsx` | Router `errorElement`; Try again = navigate to the same address (no reload) |
| `frontend/src/router.tsx` | A pathless root route with `RouteError fullScreen`, and one inside `AppShell` with `RouteError` |
| `frontend/src/utils/errors.ts` | `errorMessageKey(error)` (ApiError status / Firebase code → i18n key), `isRetryable(error)` |
| `frontend/src/lib/queryClient.ts` | Global `QueryCache`/`MutationCache` `onError` toasts, `meta.inlineError` typing, retry policy |
| `frontend/src/hooks/useUser.ts` | `meta: { inlineError: true }` on the onboarding and profile saves (they show errors inline) |
| `frontend/src/lib/analytics.ts` | `trackCrash(error, pathname)`: GA4 `exception` event, no error message (could hold personal data) |
| `frontend/src/main.tsx` | Mounts `ErrorBoundary`, `Toaster` and `InstallPrompt`; `registerSW` with `onNeedRefresh` toast and hourly update check |
| `frontend/src/components/layout/InstallPrompt.tsx` | Now renders nothing; drives the install toast (14-day "not now") |
| `frontend/src/components/layout/AppShell.tsx` | The old install banner removed from the shell |
| `frontend/src/hooks/useInstallPrompt.ts` | `promptInstall()` is stable (`useCallback`) and returns `"accepted"`, `"dismissed"` or `null` |
| `frontend/src/utils/platform.ts` | `canAddToIosHomeScreen()`; iPadOS (desktop user agent) now detected as iOS |
| `frontend/vite.config.ts` | `registerType: "prompt"`; `globPatterns: ["**/*.{js,css,html,svg,png,ico,webmanifest}"]` |
| `frontend/firebase.json` (shared, approved) | `Cache-Control: no-cache` for `**`, then the existing one-year `immutable` rule for `**/assets/**` |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | New `errors.*`, `toast.*`, `pwa.installOffer`, `pwa.installIos`, `pwa.updateAvailable`, `pwa.refresh`; removed the old banner keys `pwa.installTitle`, `pwa.installDescription`, `pwa.dismiss` |
| `docs/runbooks/NF-P1-012-frontend-pwa.md` | Note at the top: what NF-P1-026 changed |

## Flow

```
A page throws while rendering
  ├─ inside AppShell (dashboard, profile, pillars) → RouteError in <main>; header + nav stay
  │     Try again → navigate(sameLocation, replace) → page renders again, no reload
  ├─ outside AppShell (/, /sign-in, /onboarding)   → RouteError full screen
  └─ outside the router (providers, LanguageSync)  → ErrorBoundary full screen → Try again reloads
  (all three: trackCrash → Analytics "exception", only when analytics is on)

A TanStack query fails
  ├─ first load (no data yet)          → the page shows its own inline error + Retry (unchanged)
  └─ refetch while data is on screen   → error toast, [Try again] → refetchQueries(that key)
     automatic retry: once, only for network errors, 408 and 5xx (never 4xx, never 429)

A mutation (save) fails
  ├─ meta.inlineError: true            → nothing global (onboarding, profile forms)
  └─ otherwise                         → error toast, no Retry (repeating a write is the form's job)

New deploy
  sw.js changes → browser installs the new service worker → it waits
  → toast "A new version of NomadFinance is ready. [Refresh]" (stays until chosen)
  → Refresh → SKIP_WAITING → page reloads on the new version
  (closing the toast: the new version loads once all NomadFinance tabs are closed)

Install offer (every page, 3 s after load)
  ├─ Chrome/Edge/Android: beforeinstallprompt → toast [Install] → browser dialog
  │     accepted → gone; cancelled or toast closed → hidden 14 days
  ├─ iPhone/iPad in Safari or Chrome → toast with Share → Add to Home Screen steps
  └─ already installed, in-app browsers (Facebook, Instagram, LINE), desktop Safari → nothing
```

## Using it in later tasks

```ts
import { toast } from "@/hooks/useToast";
import { errorMessageKey } from "@/utils/errors";

toast({ messageKey: "contract.uploaded" });                                  // info, 6 s
toast({ messageKey: errorMessageKey(error), variant: "error" });             // error, 10 s
toast({ id: "sync", messageKey: "...", duration: null,
        action: { labelKey: "common.retry", onClick: retry } });             // stays, one button
```

- A **query** needs nothing: a first-load error is the page's job (show `errorMessageKey(query.error)` and a Retry button), and refresh failures toast by themselves.
- A **mutation** whose page shows the error next to the form sets `meta: { inlineError: true }`; otherwise the toast appears by itself.
- Messages are **i18n keys**, translated when shown; add every new key to all six files.
- Don't toast what is already on screen, and don't use toasts for anything the person must read before continuing (use inline text).

## All commands, in order

Run from `frontend/`. PowerShell uses `pnpm.cmd` (the NVM `pnpm.exe` shim is broken on some machines); bash uses `pnpm`.

### 1. Checks

```powershell
pnpm.cmd exec tsc -b
pnpm.cmd lint
pnpm.cmd exec prettier --check --end-of-line auto .
pnpm.cmd build
pnpm.cmd test:rules
pnpm.cmd exec vitest run src/lib/analytics.test.ts
```

```bash
pnpm exec tsc -b && pnpm lint && pnpm format:check && pnpm build && pnpm test:rules
```

On Windows, `--end-of-line auto` avoids the CRLF false alarms (D-21); CI runs the plain `format:check` on Linux. After `test:rules` on Windows, free the Firestore emulator ports if they stay busy (D-34):

```powershell
Get-NetTCPConnection -LocalPort 8085,9150 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess }
```

The build must print `precache  33 entries` (or close to it). A single-digit count means `globPatterns` is broken again.

### 2. Try the error screens (emulators, no real accounts)

Terminal 1 (emulators) and terminal 2 (app):

```bash
firebase emulators:start --only auth,firestore --project demo-nomadfinance
```

```bash
pnpm dev --mode emulator --host 127.0.0.1
```

Open http://127.0.0.1:5173, sign in with any phone number (the code is in the Emulator UI at http://127.0.0.1:4000/auth, or in the terminal), and finish onboarding. To see a crash screen, add this line as the first line of a component, temporarily, and **remove it afterwards**:

```tsx
if (sessionStorage.getItem("crash") === "yes") throw new Error("test crash");
```

- In `pages/Dashboard.tsx`: in the browser console run `sessionStorage.setItem("crash","yes")`, go to Profile, then Home. The crash screen appears inside the page and the header and navigation stay. Run `sessionStorage.removeItem("crash")` and click **Try again**: the dashboard is back, with no reload.
- In `pages/Landing.tsx`: set the flag and open `/`. The full-screen version appears.
- In `components/common/LanguageSync.tsx`: set the flag and reload. The root boundary appears; clear the flag and **Try again** reloads the app.

Toasts, from the browser console (dev server only):

```js
const { toast } = await import("/src/hooks/useToast.ts");
toast({ messageKey: "errors.offline", variant: "error", action: { labelKey: "common.retry", onClick: () => console.log("retry") } });
toast({ messageKey: "pwa.updateAvailable", duration: null });
```

Install offer (Chrome does not fire the real event on the dev server), in the console:

```js
localStorage.removeItem("nomadfinance.installOfferDismissedAt");
const e = new Event("beforeinstallprompt", { cancelable: true });
e.prompt = async () => console.log("native dialog would open");
e.userChoice = Promise.resolve({ outcome: "dismissed" });
window.dispatchEvent(e);
```

After 3 seconds the toast "Install NomadFinance: it opens faster and works offline. [Install]" appears.

### 3. Try the "New version available" toast (your own Chrome)

Needs a production build: service workers don't run on the dev server.

```powershell
pnpm.cmd build
pnpm.cmd preview --host 127.0.0.1 --port 4173
```

1. Open http://127.0.0.1:4173 in Chrome. DevTools → Application → Service workers: `sw.js` is **activated**; Cache storage → `workbox-precache-v2-…` holds about 33 entries.
2. Stop the preview (Ctrl+C) and build a different version. `vite preview` indexes files at start, so restart it after the build:

```powershell
$env:VITE_API_BASE_URL = "http://127.0.0.1:8080"; pnpm.cmd build; Remove-Item Env:VITE_API_BASE_URL
pnpm.cmd preview --host 127.0.0.1 --port 4173
```

```bash
VITE_API_BASE_URL=http://127.0.0.1:8080 pnpm build
pnpm preview --host 127.0.0.1 --port 4173
```

3. Reload the Chrome tab once. The toast "A new version of NomadFinance is ready. [Refresh]" appears, and DevTools shows the new worker as **waiting to activate**.
4. Click **Refresh**. The page reloads and the new worker is active.
5. Offline: DevTools → Network → **Offline**, reload. The app still opens.

### 4. After merge (CI deploys the frontend)

Merging to `main` runs `frontend-deploy.yml` (build + Hosting). Then check the headers:

```bash
curl -sI https://nomadfinance-prod.web.app/ | grep -i cache-control
js=$(curl -s https://nomadfinance-prod.web.app/ | grep -oE '/assets/index-[^"]+\.js' | head -1)
curl -sI "https://nomadfinance-prod.web.app$js" | grep -i cache-control
```

```powershell
curl.exe -sI https://nomadfinance-prod.web.app/ | Select-String -Pattern "cache-control"
$js = ((curl.exe -s https://nomadfinance-prod.web.app/) | Select-String -Pattern '/assets/index-[^"]+\.js').Matches[0].Value
curl.exe -sI "https://nomadfinance-prod.web.app$js" | Select-String -Pattern "cache-control"
```

Expected: `Cache-Control: no-cache` for `/`, and `public, max-age=31536000, immutable` for the asset. Firebase applies header rules in the order they are written, so the later `/assets/**` rule wins for assets (docs: "Configure headers"). The Hosting emulator ignores custom headers, so this can only be checked live.

Then open the live site in a browser that visited before. It shows "A new version… [Refresh]" **once**, because it is moving off the old service worker. That's expected; click Refresh. DevTools → Application → Cache storage should now hold about 33 entries, where before the deploy it held 7 icons.

## Verified results (2026-09-26 / 27)

| Check | Result |
|---|---|
| `tsc -b`, `pnpm lint`, Prettier (`--end-of-line auto`), `pnpm build` | Pass. Precache went from 7 icon files to 33 entries (1286 KiB), including `index.html` and all JS/CSS |
| `pnpm test:rules` (`firebase.json` changed) | 2 files, 99 tests passed |
| `vitest run src/lib/analytics.test.ts` (`analytics.ts` changed) | 6 passed |
| Built `sw.js` | `skipWaiting()` only inside the `SKIP_WAITING` message handler, no `clientsClaim`, so a new version waits for Refresh |
| Crash in Dashboard (emulator, signed in) | Screen inside `<main>`, header and 10 nav links still there; Try again recovered with no reload |
| Crash in Landing | Full-screen `<main role="alert">`; Try again recovered with no reload |
| Crash in LanguageSync (outside router) | Root boundary full screen; toast region still present; Try again reloaded and the app came back |
| Toasts | Live region `aria-live="polite"`; action ran and closed the toast; auto-close at the set duration; focus held a toast open, and it closed after blur; close button ran `onDismiss`; switching to Hindi translated open toasts and the close label |
| Refresh failure (real `apiRequest`, local backend stopped) | 5xx retried once, then "Our server had a problem…" [Try again], old data kept; ApiError 0 showed "No internet connection…"; Retry refetched, got fresh data and closed the toast; 429 not retried, "Too many requests…" |
| Mutation failure | With `inlineError`: no toast. Without: "Your session has ended…" for a 401 |
| Firestore offline | The profile refetch is answered from Firestore's local cache (`fromCache: true`), so no toast. Good for people; the toast path matters for API calls |
| Phone width (375 × 812) | Toast has 16 px side margins, sits above the tab bar, no sideways scroll |
| Install offer (simulated `beforeinstallprompt`) | Nothing at 1 s, toast at 3.5 s; Install called the native `prompt()` once; a cancelled dialog was remembered; no offer while remembered; close button remembered; `appinstalled` removed an open offer |
| `canAddToIosHomeScreen()` | iPhone Safari true, iPhone Chrome true, iPad (desktop user agent) true, Facebook in-app false, Mac Safari false, Android false |
| Firebase header order | Docs: rules "are applied in the order they are defined". The Hosting emulator applies no custom headers, so the live check in step 4 confirms it |

Not verified here:
- **The update toast end to end.** The test browser refuses to register a service worker on a local `http://127.0.0.1` address. Step 3 in your own Chrome covers it, and step 4 after the merge.
- **A real `beforeinstallprompt` on an Android phone, and the iOS toast on a real iPhone.**
- **Hover pause.** The code path is the same as focus.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| React Router's own "Unexpected Application Error!" page | The route isn't under one of the two `errorElement` routes in `router.tsx`. New routes go inside the existing `children` arrays |
| A toast shows a raw key like `errors.server` | The key is missing from that language file; add it to all six |
| Two error messages for one failed save | The page shows the error inline but the mutation lacks `meta: { inlineError: true }` |
| No "New version available" after a deploy | The browser checks on page load and every hour. Check that `sw.js` changed (new revision in `precache`) and DevTools → Application → Service workers shows "waiting" |
| Precache count in the build is single digits | `globPatterns` in `vite.config.ts` is broken; it must be `**/*.{…}` |
| `Cache-Control: max-age=3600` on `/` after deploy | The `**` header rule is missing from `firebase.json` or the deploy didn't include it |
| The install toast never appears in Chrome | Chrome decides when `beforeinstallprompt` fires (valid manifest and service worker, some engagement), or it was closed less than 14 days ago: `localStorage.removeItem("nomadfinance.installOfferDismissedAt")` |
| Install toast on iPhone inside Facebook/Instagram | By design it doesn't show there: in-app browsers have no "Add to Home Screen" |

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind + shadcn/ui (`Button`, `EmptyState`, lucide icons, theme tokens)
- [x] Mobile responsive: checked at 375 × 812 (above the tab bar, 16 px margins, no sideways scroll)
- [x] Slow network: error toasts for offline and 5xx, one automatic retry for transient failures; the whole app is precached, so repeat visits don't depend on the network
- [x] Loading states: unchanged (no new async screens); Refresh reloads the page
- [x] Error states handled: crash screens at three levels, refresh and save failures, offline, 429, 401
- [x] i18n keys in all 6 languages (native review: D-41)
- [ ] Screenshots added to PR: take them in step 2 (crash screen, error toast, install toast) and step 3 (update toast). Screenshots weren't possible in the test browser.
- [x] Accessibility: `role="alert"` on crash screens, toast live region with a labelled `<section>`, real buttons with `aria-label`/`title` on close, keyboard reachable, toasts stay open while focused, `motion-reduce` respected

## Commit and PR for this task

Branch: `feature/frontend-error-boundaries` (already checked out). **First undo the stray local edits to the two `.env.example` files** (not part of this task):

```bash
git restore backend/.env.example frontend/.env.example
```

```bash
git add frontend/src frontend/vite.config.ts frontend/firebase.json docs/runbooks
git status
```

```bash
git commit -m "feat(frontend): add error boundaries, toasts and PWA update prompt" -m "Refs: NF-P1-026"
```

PR title: `feat(frontend): error boundaries, global toasts, PWA update and install toasts (NF-P1-026)`

## Not covered here

- Sentry or remote error logging (`lib/sentry.ts`, `lib/logger.ts` stubs): no tracker task; crashes are counted in Analytics
- Offline banner: not asked for
- CORS and `VITE_API_BASE_URL` in production: NF-P1-027 (D-44)
- Code-splitting the 1 MB bundle: NF-P4-003 (D-45)
- Removing `i18next-browser-languagedetector`: D-43, needs the team's OK
