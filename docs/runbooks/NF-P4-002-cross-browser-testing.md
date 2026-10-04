# NF-P4-002 — Cross-browser testing

## Summary

The app was run on the browsers a worker is likely to use, on the local emulators with demo data, and the rendering and behaviour bugs found were fixed.

**What was tested, and how real it is:**

| Browser | How | Real? |
|---|---|---|
| Desktop Chrome | Chromium 1280 px wide (Playwright) | Real engine |
| Desktop Firefox | **Your installed Firefox 143.0.1**, driven through Puppeteer (WebDriver BiDi) | Real browser |
| Desktop Safari | Playwright's WebKit, desktop viewport | The Safari engine, **not Apple's Safari** (a Windows build) |
| Safari on iPhone | Playwright's WebKit with the iPhone 15 viewport (393 px), touch and user agent | The Safari engine on a desktop PC, **not a real iPhone** |
| Chrome on Android | Chromium with the Pixel 7 profile (412 px), and the same at 360 px and 320 px | Emulation, **not a real phone** |

**Real iPhone and Android phones were not tested.** Several iOS-specific fixes below cannot be seen on a PC; they follow Apple's rules and are marked "needs a device". The checklist for the team's phones is further down.

**Each of the seven runs** signs a fresh worker in by phone code, onboards, loads demo data, and visits 23 screens in light and dark mode: sign-in, onboarding, dashboard, remittance comparison and trend chart, contract upload, history and report with letter, radar map, alerts, report form and business page, Financial Identity (dashboard, log, export), profile, and the Hindi, Bengali and Nepali languages. It also measures sideways overflow, field font sizes, tap-target sizes and the bottom nav, and records console errors and failed requests.

## Results

| Profile | Steps passed | Sideways overflow | Fields under 16 px |
|---|---|---|---|
| Chrome desktop | 29 / 29 | none | header pickers (desktop only, see decision 4) |
| Firefox 143 desktop | 29 / 29 | none | same |
| Safari engine, desktop | 29 / 29 | none | same |
| Chrome Android 412 px | 29 / 29 | none | none |
| Chrome Android 360 px | 29 / 29 | none | none |
| Chrome Android 320 px | 29 / 29 | none | none |
| Safari engine, iPhone 393 px | 24 / 29 | none (19 screens measured) | none |

The 5 iPhone steps that failed are screens that **did not load at all** (the contract report and four radar pages), because this PC's WebKit cannot hold Firestore's live connection to the local emulator (see Troubleshooting). That is a limit of the test setup, not a finding about the app, and it is why those screens are on the real-device checklist.

All seven showed the trend chart changing with 1M / 3M / 6M / 1Y (20 / 64 / 127 / 254 days). Six drew the radar map with its 15 markers (14 at 320 px); the iPhone-engine run could not load that page. Hindi and Bengali drew correctly (reviewed on screen; Nepali shares Hindi's script and was measured only). Chrome and Firefox logged no console error other than two known ones (a reCAPTCHA call the Auth emulator doesn't implement, and a 404 for "no exported report yet"); the two Safari-engine runs also logged the Firestore connection errors described below.

## What was found and fixed

| # | Problem | Seen in | Evidence | Fix |
|---|---|---|---|---|
| 1 | **"Download as PDF" on the complaint letter** opened an empty tab and told the worker "Please allow pop-ups". The window was never printed. | Chrome desktop, Chrome Android, Firefox | `window.open(…, "noopener")` returns `null` in every browser; the code read `null` as "blocked". Its unit test used a fake window, so it never caught this. Before: window opened, message shown. After: window opened, `print()` called, no message, in all three | `utils/complaintActions.ts`: open without `noopener`, then cut the link back to the app (`opener = null`). 2 new tests |
| 2 | **The whole page scrolled sideways on an iPhone.** The dashboard was 603 px wide on a 393 px screen; the landing page was 416 px | Safari engine at 393 px only. Chrome at 412, 360 and 320 px was fine | The four dashboard cards are one implicit grid column, which in Safari grows to fit the long contract title. Found with a per-element diagnostic, fix tried live, then in code and re-measured: every loaded screen is exactly 393 px | `grid-cols-1` on the 8 grids that had no column on a phone (`Dashboard`, `Landing`, `Onboarding`, `RadarHeatmap`, `ScoreMeter`, `NotificationsForm`, `ClauseRow`, `ReportSkeleton`) |
| 3 | The landing page was still 23 px too wide after fix 2 | Safari engine | The header's icon-sized language and theme pickers hold text ("English") wider than their 36 px box; Safari counts it, Chrome clips it. Only clipping the select fixed it on fresh loads; three other ideas (including a rule for the hidden labels) did not and were dropped | `overflow-hidden` on `LanguageSelector` and `ThemeToggle` |
| 4 | **iPhone zooms the page** when the header's language or theme picker is tapped (font 14 px; iOS zooms below 16 px) | iOS (known behaviour); the 14 px measured on every screen | Header pickers were the only 2 fields under 16 px on any screen; every real form field was already 16 px | 16 px on touch screens only (`[@media(pointer:coarse)]:text-base`), so desktop looks the same. Measured: 14 px → 16 px on Chrome Android, all 23 screens |
| 5 | **Dark mode: native controls stayed light** (date picker icon, dropdown lists, scrollbars) | Computed `color-scheme` was `normal` in all browsers; the date icon is faint on the dark page in Chrome | The theme is a CSS class, so the browser cannot tell | `color-scheme: light` on the page, `dark` under `.dark` (`styles/globals.css`). Measured: `light` / `dark` follow the theme |
| 6 | **Installed iPhone app: header under the status bar and home indicator** (status bar style is `black-translucent`, but the page does not use the whole screen, so the safe-area insets stay 0) | **Needs a device** | Apple's rules; cannot be seen on a PC | `viewport-fit=cover` in `index.html`; header, sticky offsets and page sides use `env(safe-area-inset-*)`. No change where the insets are 0 |
| 7 | **Short pages scroll on iPhone Safari**: `100vh` is the tallest the viewport gets, with the toolbar hidden | **Needs a device** | Known iOS behaviour | `min-h-dvh` next to `min-h-screen` on the 8 full-height pages (browsers that don't know `dvh` keep `100vh`) |

Fixes 6 and 7 are small and don't change anything where the extra space is 0, but they are **not verified**: tick them on a real iPhone.

## Decisions

1. **Real Firefox, not Playwright's.** Playwright's bundled Firefox does not start on this PC ("side-by-side configuration is incorrect": a missing Visual C++ runtime). Installing system software was not worth it, and the installed Firefox is what a real user has, so it was driven through Puppeteer instead.
2. **No change to how Firestore connects.** Safari-engine runs on this PC lost Firestore's live connection to the emulator. A forced long-polling test helped a little (21 → 25 of 30 steps) but did not fix it, and the same code works in Chrome and Firefox. Changing the production connection based on a Windows-only WebKit build would be a guess, so it was reverted. A real iPhone must confirm live updates (checklist).
3. **Only measured problems were fixed.** An early code search guessed "about 40 small fields"; measuring found 2. Tap-target sizes (D-73) are a usability point, not a cross-browser one, so they are logged, not changed.
4. **Header pickers stay 14 px on desktop.** iOS zooms; desktop browsers don't. The touch-only rule keeps the desktop header unchanged.
5. **The test harness stays out of the repo.** It needs Playwright and Puppeteer as dev tools (`package.json` and the lockfile are shared files). It lives in the working folder; D-74 offers to add it.

## Files

| File | Change |
|---|---|
| `frontend/src/utils/complaintActions.ts`, `complaintActions.test.ts` | Print window opens without `noopener`; 2 tests |
| `frontend/src/pages/Dashboard.tsx`, `Landing.tsx`, `Onboarding.tsx`, `pages/radar/RadarHeatmap.tsx`, `components/fib/ScoreMeter.tsx`, `components/profile/NotificationsForm.tsx`, `components/contract/ClauseRow.tsx`, `ReportSkeleton.tsx` | `grid-cols-1` |
| `frontend/src/components/layout/LanguageSelector.tsx`, `ThemeToggle.tsx` | `overflow-hidden`; 16 px on touch screens |
| `frontend/src/styles/globals.css` | `color-scheme` per theme; side safe-areas |
| `frontend/index.html` | `viewport-fit=cover` |
| `frontend/src/components/layout/Header.tsx`, `Sidebar.tsx`, `components/contract/ReportCard.tsx` | Top safe-area padding; sticky offsets clear it |
| 8 full-height pages and components (`AppShell`, `Landing`, `SignIn`, `Onboarding`, `NotFound`, `RequireOnboarding`, `ErrorFallback`, `LoadingSpinner`) | `min-h-dvh` |
| `docs/deferred-items.md`, this runbook | D-72 (real-device pass), D-73 to D-76 |

No new package, no shared file changed.

## All commands, in order

### 1. Checks (from `frontend/`; `pnpm.cmd` in PowerShell if `pnpm` is blocked)

```bash
pnpm install --frozen-lockfile
pnpm exec tsc -b
pnpm lint
pnpm exec prettier --check src
pnpm exec vitest run src
pnpm build
```

On Windows with CRLF checkouts: `pnpm exec prettier --check --end-of-line auto src index.html`.

### 2. Try the fixes by hand (emulators, no tools needed)

Start the emulators, load the data, start the API and the app as in the NF-P4-001 runbook (steps 2 and 3), then open **http://localhost:5173**.

- **Print window (fix 1):** open a contract that has a letter (Contracts → Past checks), press **Download as PDF**. The print dialog opens, there is no "allow pop-ups" message, and no empty tab is left behind. Press **Copy letter**: "Letter copied to clipboard."
- **Phone layout (fixes 2 and 3):** DevTools → device toolbar → iPhone 14 (390 px) or "Responsive" at 360 px. Open the landing page and the dashboard: no sideways scroll. Firefox: Responsive Design Mode (`Ctrl+Shift+M`). Note that Chrome's emulation does **not** reproduce fixes 2 and 3; they only showed in the Safari engine.
- **Zoom (fix 4):** only on a real iPhone: tap the language picker; the page must not zoom.
- **Dark controls (fix 5):** switch the theme to Dark, open Identity → Log activity: the date picker's icon is light, and the dropdown lists are dark.

### 3. Repeat the browser matrix (optional, from a working folder outside the repo)

```bash
npm init -y
npm install playwright puppeteer-core
npx playwright install chromium webkit
```

This downloads a few hundred MB into the user cache. The harness is not in the repo (D-74); ask to have it added.

## Real-device checklist (needs a person with the phones)

Tracked as D-72 in `docs/deferred-items.md`.

**iPhone, Safari** (and then the same from the home screen: Share → Add to Home Screen):
- [ ] Landing, sign-in, dashboard: no sideways scroll, nothing cut off at the bottom
- [ ] Sign in with a phone code; Google sign-in (popup or redirect)
- [ ] Installed app: header sits below the clock; bottom bar sits above the home indicator (fix 6)
- [ ] Short pages (sign-in, profile): no needless scrolling (fix 7)
- [ ] Tapping the language and theme pickers does not zoom (fix 4)
- [ ] Rotate to landscape: content clear of the notch
- [ ] Contract upload from the **camera** and from a **HEIC photo**; analysis progress updates live; report opens; **Download as PDF** shows the print sheet; **Copy letter**
- [ ] Bill photo (Financial Identity → Bill); date fields look right in light and dark
- [ ] Radar map draws, pinch-zoom works; alerts and report form load
- [ ] The screens that did not load in the Safari engine here: contract report, radar map, alerts, report form
- [ ] Notifications: only offered after installing (iOS 16.4+)

**Android, Chrome:**
- [ ] Same list (without the iOS-only items), plus: the "install app" offer appears; share and copy work; notification permission

## Verified results (2026-10-04)

| Check | Result |
|---|---|
| `tsc -b`, `pnpm lint`, `prettier --check` | Pass |
| `vitest run src` | 198 passed (21 files; 2 new) |
| `pnpm build` | Pass |
| 7 browser profiles × 29 steps | 6 × 29/29; Safari engine at 393 px 24/29 (5 screens would not load, see above) |

**Not verified (needs a person and a phone):** real iPhone Safari and Android Chrome (checklist above); fixes 6 and 7; Firestore live updates in Apple's Safari; web push; Slow-3G throttling (not run).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Playwright's Firefox: `spawn UNKNOWN` | The Visual C++ runtime is missing (`firefox.exe` says "side-by-side configuration is incorrect"). Use the installed Firefox through Puppeteer, or install the Microsoft Visual C++ Redistributable |
| Safari-engine run on Windows: "Could not reach Cloud Firestore backend", pages show "We couldn't load your profile" | Playwright's WebKit for Windows is a different network stack from Apple's Safari and does not hold Firestore's streaming connection to the emulator. Chrome and Firefox do. Press "Try again", or test on a real iPhone |
| Vite shows a blank page for 10 s on the first load | It re-optimises dependencies after `pnpm install`; reload |
| An old overflow reading disappears after one change | Safari keeps a stale scroll width after the first style change; test each idea on a fresh page load |
| The date icon is faint in dark mode | Fix 5 is missing: `color-scheme` is not set |

## Definition of Done (Frontend Feature)

- [x] Tailwind and shadcn/ui only
- [x] Fully mobile responsive: 7 widths/engines, no overflow on any measured screen
- [ ] Works on slow network (throttled 3G): not run
- [x] Loading and error states unchanged
- [x] i18n: no new strings
- [ ] Screenshots in the PR: yours to add (iPhone-width dashboard, dark date field, print window)
- [x] Accessibility: no change to labels or roles; the print message no longer misleads

## For teammates

- **Nobody** needs a new package or a `.env.local` change.
- **Aditya:** the iPhone/Android checklist is yours, since the tracker lists this task for you; D-73 lists the buttons under 36 px.
- **Anyone writing a grid:** give it a column on phones (`grid grid-cols-1 sm:grid-cols-2`). A grid with only `sm:grid-cols-2` grows to its longest text in Safari.
- **Anyone using `window.open`:** do not pass `noopener` if you need the window back; it makes `window.open` return `null`.

## Commit and PR

Branch: `fix/cross-browser` (already checked out).

```bash
git add frontend docs
git status
```

```bash
git commit -m "fix(frontend): fix Safari overflow, letter print and dark controls" -m "Refs: NF-P4-002"
```

PR title: `fix(frontend): cross-browser fixes — Safari overflow, letter print window, dark-mode controls (NF-P4-002)`

## Not covered here

- Real-device runs (checklist), Slow-3G, performance (NF-P4-003), security (NF-P4-004)
- Tap-target sizes (D-73), putting the test harness in the repo (D-74), the Hindi/Bengali/Nepali link wording (D-76)
