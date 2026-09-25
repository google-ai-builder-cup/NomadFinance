# NF-P1-012 — PWA Setup

## Summary

The app is now a real installable PWA: `vite-plugin-pwa` generates a web manifest and a Workbox service worker at build time, and a small custom banner offers the native "Install" prompt on Chrome/Edge/Android. The service worker precaches the built app shell (HTML/JS/CSS/icons) so it loads offline after a first visit, and updates itself silently on the next load (`registerType: 'autoUpdate'`) — there's no "new version available" toast yet, because the toast system (NF-P1-026) doesn't exist.

The manifest, favicons and app icons used here are **placeholders**: a plain "N" monogram on the current shadcn slate-900 theme color (`src/styles/tokens.css`'s `--primary`), generated with a throwaway Python/Pillow script (not committed). NF-P1-024 (brand assets) replaces every file under `public/icons/`, `public/apple-touch-icon.png`, `public/favicon.ico` and `public/favicon.svg` with real artwork — the manifest's `theme_color`/`background_color` should move to real brand colors at the same time.

## Files

| File                                                                               | Purpose                                                                                                                                                                                                                                     |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/vite.config.ts`                                                          | `VitePWA()` plugin: manifest fields, icon list, `registerType: 'autoUpdate'`, `injectRegister: false` (we register the SW ourselves), Workbox `generateSW` with a glob covering the built app shell                                         |
| `frontend/src/main.tsx`                                                            | Registers the service worker via `virtual:pwa-register` (`registerSW({ immediate: true })`)                                                                                                                                                 |
| `frontend/src/vite-env.d.ts`                                                       | Added `/// <reference types="vite-plugin-pwa/client" />` so `virtual:pwa-register` type-checks                                                                                                                                              |
| `frontend/src/hooks/useInstallPrompt.ts`                                           | Wraps `beforeinstallprompt` / `appinstalled`; exposes `canInstall` and `promptInstall()`. Chrome/Edge/Android only — iOS Safari never fires this event.                                                                                     |
| `frontend/src/components/layout/InstallPrompt.tsx`                                 | Dismissible banner: icon, title/description, Install button, dismiss (X). Renders nothing until `canInstall` is true; dismissal is remembered in `localStorage` (`nomadfinance.installPromptDismissed`) so it doesn't reappear every visit. |
| `frontend/src/components/layout/AppShell.tsx`                                      | Mounts `<InstallPrompt />` above `<Outlet />`, so it shows on every signed-in page                                                                                                                                                          |
| `frontend/index.html`                                                              | Added `theme-color`, `description`, and the iOS `apple-mobile-web-app-*` / `mobile-web-app-capable` meta tags Safari needs independently of the manifest                                                                                    |
| `frontend/src/i18n/*.json`                                                         | New `pwa.installTitle` / `pwa.installDescription` / `pwa.install` / `pwa.dismiss` keys, all 6 languages                                                                                                                                     |
| `frontend/public/icons/pwa-192x192.png`, `pwa-512x512.png`, `maskable-512x512.png` | New placeholder icons (maskable one keeps the mark inside the ~66%-diameter safe zone)                                                                                                                                                      |
| `frontend/public/apple-touch-icon.png`, `favicon.ico`, `favicon.svg`               | Replaced empty (0-byte) stub files with the placeholder mark — these were broken before this task, unrelated to PWA-ness specifically                                                                                                       |
| `frontend/public/manifest.webmanifest`                                             | **Deleted.** It was an empty stub; the plugin now generates the real one into `dist/manifest.webmanifest` at build time from the `vite.config.ts` config.                                                                                   |
| `frontend/package.json`, `pnpm-lock.yaml`                                          | Added `vite-plugin-pwa` and `workbox-window` as devDependencies (the latter is a peer dependency of the former that pnpm won't hoist automatically — Rollup fails to resolve `virtual:pwa-register` without it declared directly)           |

Not touched: `public/splash/` (Apple splash screens) — optional, not required for installability, left for NF-P1-024 alongside real branding. `firebase.json` was not touched; Firebase Hosting's default headers work fine here, and the browser always revalidates the service worker script's bytes on its own regardless of HTTP caching.

## Flow

```
vite build
  ├─ vite-plugin-pwa reads the `manifest` + `workbox` config in vite.config.ts
  ├─ emits dist/manifest.webmanifest
  └─ emits dist/sw.js + dist/workbox-<hash>.js (Workbox generateSW, precaches the app shell)

main.tsx
  └─ registerSW({ immediate: true })   (virtual:pwa-register, only active in a built/served app — no dev-mode SW)

AppShell (every signed-in page)
  └─ <InstallPrompt />
       ├─ useInstallPrompt() listens for `beforeinstallprompt` (Chrome/Edge/Android)
       ├─ canInstall = false  → renders nothing
       └─ canInstall = true   → banner: Install button calls promptInstall() → native prompt
                                dismiss (X) → localStorage flag, hidden from then on
```

## Design choices worth knowing

- **`injectRegister: false` + manual `registerSW()`.** The plugin can auto-inject its own registration script into `index.html`, but we wanted a custom install-prompt UI driven by our own hook, so registration is explicit in `main.tsx` instead — doing both would register the service worker twice.
- **`autoUpdate`, not `prompt`.** `registerType: 'prompt'` would need a "reload to update" UI, which needs the toast system from NF-P1-026 (not built yet). `autoUpdate` just takes over silently on the next navigation — the safer default until that exists.
- **Custom banner instead of relying on the browser's own install UI.** Chrome/Edge already show an install icon in the address bar once a page is installable, but that's easy to miss. The banner is optional polish, dismissible, and never blocks the page.
- **No iOS install UI.** iOS Safari never fires `beforeinstallprompt` — there's no programmatic way to trigger "Add to Home Screen" there. The iOS meta tags in `index.html` make manual "Add to Home Screen" behave correctly (standalone display, status bar style) if a user does it themselves, but there's no in-app nudge for it. Worth a custom instructional banner later if iOS install rate matters for the pitch.
- **Only the app shell is precached.** `globPatterns` covers built JS/CSS/HTML/icons/the manifest, not API responses or Firestore data. Deeper offline behavior (e.g. viewing a previously-loaded contract report with no network) is a per-pillar decision for later, not blanket-applied here.
- **Placeholder icons, not real branding.** Every icon is generated from one script (see Summary) since NF-P1-024 hasn't landed. The `TODO(Aditya)` comment in `vite.config.ts` marks exactly what to swap.

## How later tasks plug in

| Task                                 | What to do                                                                                                                                                                                                                                               |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NF-P1-024 (brand assets)             | Replace every file under `public/icons/`, `apple-touch-icon.png`, `favicon.ico`, `favicon.svg` with real artwork at the same filenames/sizes, and update `theme_color`/`background_color`/`name` in the `VitePWA()` manifest config in `vite.config.ts`. |
| NF-P1-026 (toasts)                   | Switch `registerType` to `'prompt'` and use the `onNeedRefresh`/`onRegisteredSW` callbacks of `registerSW()` in `main.tsx` to show a "New version available, reload" toast instead of updating silently.                                                 |
| Any pillar wanting true offline data | Add `runtimeCaching` rules to the `workbox` block in `vite.config.ts` for that pillar's API/Firestore calls — not needed generally, so left out here.                                                                                                    |

## All commands, in order

Run from `frontend/` unless noted otherwise.

### 1. Install

```bash
pnpm install
```

Adds `vite-plugin-pwa` and `workbox-window`.

### 2. Checks

```bash
pnpm lint
pnpm build
```

Expected: lint prints nothing (0 warnings). Build ends with `✓ built in …`, followed by:

```
PWA v1.3.0
mode      generateSW
precache  18 entries (513.41 KiB)
files generated
  dist/sw.js
  dist/workbox-<hash>.js
```

### 3. Verify installability locally

The service worker only registers against a built app — `pnpm dev` does not run it.

```bash
pnpm build
pnpm preview
```

Open `http://localhost:4173`. In Chrome DevTools → **Application** tab:

- **Manifest**: shows "NomadFinance", the three icons, no errors/warnings
- **Service Workers**: one worker, status "activated and is running"

Chrome's own install heuristics (an address-bar install icon, or a `beforeinstallprompt` event) need real engagement signals and don't always fire in a fresh local session — that's normal, not a bug. To exercise the custom banner directly, run this in the DevTools console on any signed-in page:

```js
const evt = new Event("beforeinstallprompt", { cancelable: true });
evt.prompt = () => Promise.resolve();
evt.userChoice = Promise.resolve({ outcome: "accepted" });
window.dispatchEvent(evt);
```

The banner should appear above the page content with Install/dismiss buttons.

### 4. Verify on Android (real installability signal)

1. Deploy or serve the built app over HTTPS (or use `pnpm preview` and a tunnel) and open it in Chrome for Android, signed in.
2. Chrome's menu should show "Install app" (or the mini-infobar appears automatically). Tap it.
3. Confirm the app opens standalone (no browser chrome/URL bar) from the home screen icon.
4. Turn on airplane mode, relaunch from the home screen icon: the app shell still loads (offline precache).

### 5. Manual test checklist

1. Sign in, land on `/dashboard`. If a `beforeinstallprompt` fires (or is simulated per step 3), the banner appears between the header and the page content.
2. Click **Install** → the native browser install dialog appears; accepting it removes the banner.
3. Reload without installing, click the **X** on the banner → banner disappears and does not come back on further reloads (check `localStorage.getItem('nomadfinance.installPromptDismissed')` is `"true"`).
4. At 375 px width, the banner's icon, text, Install button and dismiss button all fit on one row with no overflow or wrapping.
5. Switch the language selector — the banner's own text (title/description/buttons) translates along with the rest of the page.

## Verified results (2026-09-26, browser pane, production build via `pnpm preview`)

| Check                                                                               | Result                                                                                                                                                           |
| ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm lint` / `pnpm build`                                                          | Clean / clean. Bundle ~488.6 kB JS (155.1 kB gzip) + 5.75 kB workbox-window chunk; `dist/manifest.webmanifest`, `dist/sw.js`, `dist/workbox-<hash>.js` generated |
| `dist/manifest.webmanifest` content                                                 | Correct name, icons, `theme_color`/`background_color`, `display: standalone`                                                                                     |
| `navigator.serviceWorker.getRegistrations()` after load                             | One registration, `active: true`                                                                                                                                 |
| `<link rel="manifest">` fetch                                                       | 200, matches the built manifest                                                                                                                                  |
| `favicon.svg`, `apple-touch-icon.png`, the three `icons/*.png`, `favicon.ico`       | All 200 with correct content-types (previously these were 0-byte stub files serving nothing)                                                                     |
| Simulated `beforeinstallprompt` (desktop width)                                     | Banner appears with correct copy; clicking Install calls the event's `prompt()` and the banner clears afterward                                                  |
| Simulated `beforeinstallprompt` + dismiss (X)                                       | Banner hides immediately; a second simulated event after dismissal stays hidden (localStorage flag respected)                                                    |
| Simulated `beforeinstallprompt` at 375 px width                                     | Banner fits on one row, no overflow/wrap, sits correctly above the dashboard cards                                                                               |
| `pnpm lint` after adding `react-hooks` violation (`setState` in a bare `useEffect`) | Caught by `eslint-plugin-react-hooks` 7.1.1; fixed by moving the `localStorage` read into `useState`'s lazy initializer instead                                  |

Not tested: real `beforeinstallprompt` on a real Android device (no such device in this environment — simulated via a synthetic event instead, which exercises the same React code path); iOS "Add to Home Screen" manual flow; Lighthouse PWA score.

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind + the existing shadcn/ui `Button`; no new UI library
- [x] Fully mobile responsive (banner checked at 375 px)
- [ ] Works on slow network (throttled 3G): not tested this session
- [x] Loading states: n/a, nothing async in the banner itself
- [x] Error states: n/a, banner simply doesn't render without a valid install event
- [x] i18n keys added for all 6 languages
- [ ] Screenshots added to the PR
- [x] Accessibility: banner icon `aria-hidden`, dismiss button has `aria-label`/`title`, Install/dismiss are real `<button>`s, keyboard-operable

## Commit

Branch: `feature/frontend-pwa`.

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/vite.config.ts frontend/index.html \
  frontend/src/main.tsx frontend/src/vite-env.d.ts frontend/src/hooks/useInstallPrompt.ts \
  frontend/src/components/layout/InstallPrompt.tsx frontend/src/components/layout/AppShell.tsx \
  frontend/src/i18n frontend/public/icons frontend/public/apple-touch-icon.png \
  frontend/public/favicon.ico frontend/public/favicon.svg frontend/README.md \
  docs/runbooks/NF-P1-012-frontend-pwa.md
git add -u frontend/public/manifest.webmanifest
git commit -m "feat(frontend): configure vite-plugin-pwa with install prompt" -m "Refs: NF-P1-012"
```

`frontend/public/manifest.webmanifest` is a deletion; `git add -u` (or naming it directly) stages that. Before pushing, run `git status` and confirm nothing else is listed.

## Troubleshooting

| Symptom                                                                              | Fix                                                                                                                                                                                                                       |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Rollup failed to resolve import "workbox-window"` during `pnpm build`               | `workbox-window` isn't installed directly (pnpm doesn't hoist a plugin's peer dependency by default). Confirm it's in `package.json` devDependencies and re-run `pnpm install`.                                           |
| Install banner never appears, even on a real installable page                        | `beforeinstallprompt` needs real engagement heuristics Chrome tracks itself (time on site, HTTPS, valid manifest+SW) — it doesn't fire on every load. Use the DevTools console snippet in step 3 to test the UI directly. |
| Old content/old icons still show after a rebuild                                     | The previous service worker's cache is still active. In DevTools → Application → Service Workers, click "Unregister", then Application → Storage → "Clear site data", and reload.                                         |
| `pnpm dev` shows no service worker at all                                            | Expected — the SW only registers against a production build (`pnpm build && pnpm preview`), not the Vite dev server.                                                                                                      |
| ESLint error `Avoid calling setState() directly within an effect` on a new component | Read the initial value with `useState(() => ...)`'s lazy initializer instead of `useState(default)` + a `useEffect` that immediately calls the setter.                                                                    |
| Manifest icon shows a broken image in DevTools → Application → Manifest              | Check the icon actually exists at that exact path under `public/` and that `pnpm build` was re-run after adding it — `public/` files are only copied into `dist/` at build time.                                          |

## Not covered here

- Real brand icons, app name styling, splash screens: NF-P1-024
- "New version available" update toast (currently silent `autoUpdate`): NF-P1-026
- Per-pillar offline data caching (Firestore/API runtime caching rules): later, per pillar, if needed
- iOS-specific "how to install" instructional UI: no task currently owns this
