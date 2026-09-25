# NF-P1-010 — App Shell and Navigation

## Summary

Every signed-in page now renders inside one **app shell**: a sticky header (brand, signed-in identity, sign-out), the page itself, a footer, and navigation. Navigation changes with screen size. On **phones (below 768 px)** it is a **bottom tab bar** with five items, easy to reach with a thumb. On **tablets and desktop (768 px and up)** it is a **left sidebar**. `/dashboard` is now the real dashboard: a greeting and four pillar cards (Remittance X-Ray, Contract Shield, Exploitation Radar, Financial Identity). The four pillar routes exist and show a "coming soon" page until their own tasks replace the route element. Unknown URLs show a 404 page. `/` redirects to `/dashboard` until the landing page (NF-P1-021) exists.

Nothing new was installed: it uses React Router, Tailwind, the existing `Button` and `lucide-react` icons. All text goes through `t()` keys in `src/i18n/en.json`.

## Routes

| Path | Shows | Access |
|---|---|---|
| `/` | Redirect to `/dashboard` (temporary, NF-P1-021 replaces it with the landing page) | Public |
| `/sign-in` | Sign-in page (NF-P1-009) | Public |
| `/dashboard` | Greeting and 4 pillar cards, inside the shell | Signed in |
| `/remittance`, `/contract`, `/radar`, `/identity` | "Coming soon" page for that pillar, inside the shell | Signed in |
| anything else | 404 page (no shell, so it also works when signed out) | Public |

Signed-out visitors to a protected path go to `/sign-in` and come back to that path after signing in (existing behaviour of `ProtectedRoute`).

## Files

| File | Purpose |
|---|---|
| `frontend/src/components/layout/navItems.ts` | **The single nav list**: `HOME_ITEM`, `PILLAR_ITEMS` (path, icon, label key, name key, description key) and `NAV_ITEMS`. The sidebar, tab bar, dashboard cards and router all read it. |
| `frontend/src/components/layout/AppShell.tsx` | Layout route: skip link, header, sidebar, `<main>` with `<Outlet />`, footer, tab bar |
| `frontend/src/components/layout/Header.tsx` | Sticky top bar: "NomadFinance" link, name/email/phone (hidden on very small screens) and a sign-out icon button |
| `frontend/src/components/layout/Sidebar.tsx` | Left navigation, tablet and desktop only. Highlights the current page. |
| `frontend/src/components/layout/BottomNav.tsx` | Phone tab bar, fixed to the bottom, 5 tabs, each at least 56 px tall |
| `frontend/src/components/layout/Footer.tsx` | Tagline and copyright line |
| `frontend/src/components/common/EmptyState.tsx` | Icon, title, description and optional action; used by the coming-soon and 404 pages |
| `frontend/src/pages/Dashboard.tsx` | Replaces the NF-P1-009 placeholder: greeting and the four cards |
| `frontend/src/pages/ComingSoon.tsx` | Stand-in for a pillar page (takes the pillar item as a prop) |
| `frontend/src/pages/NotFound.tsx` | 404 page |
| `frontend/src/router.tsx` | New tree: `ProtectedRoute` → `AppShell` → pages, plus `/`, `/sign-in` and `*` |
| `frontend/src/i18n/en.json` | New `nav`, `layout`, `pillars`, `dashboard`, `comingSoon` and `notFound` keys; the two `dashboard.placeholder.*` keys were removed |
| `frontend/src/App.tsx` | **Deleted.** It was the NF-P1-007 bootstrap page ("Replaced by the real app shell in NF-P1-010") and nothing used it any more. |
| `frontend/README.md` | Short "App shell and navigation" section |
| `docs/runbooks/NF-P1-009-frontend-firebase-auth.md` | Two lines updated so they no longer call the dashboard a placeholder |

Not touched on purpose: `LanguageSwitcher.tsx` (NF-P1-011), `Profile.tsx` (NF-P1-023), `ErrorBoundary.tsx` and `Toast.tsx` (NF-P1-026), `Landing.tsx` (NF-P1-021), and all shared files (`package.json`, `tsconfig*.json`, `firebase.json`).

## Flow

```
main.tsx → <AuthProvider> → <RouterProvider>
  ├─ /                  → <Navigate to="/dashboard">   (until NF-P1-021)
  ├─ /sign-in           → SignIn
  ├─ <ProtectedRoute>                                  (signed-out → /sign-in, remembers the page)
  │    └─ <AppShell>
  │         ├─ Header                                   (all sizes)
  │         ├─ Sidebar                                  (md and up, 768 px+)
  │         ├─ <main id="main-content"> <Outlet/> </main>
  │         │      ├─ /dashboard   Dashboard (4 pillar cards)
  │         │      └─ /remittance /contract /radar /identity   ComingSoon
  │         ├─ Footer
  │         └─ BottomNav                                (below 768 px)
  └─ *                  → NotFound

navItems.ts ──► Sidebar, BottomNav, Dashboard cards, router pillar routes
```

## Design choices worth knowing

- **Two navs, one list.** The sidebar and the tab bar are separate components that are shown or hidden by CSS (`md:hidden` / `hidden md:block`), so only one is ever visible or announced by a screen reader. Both render `NAV_ITEMS`, so they cannot drift apart.
- **Why a tab bar on phones:** most users are on phones, and a bottom bar is reachable with one thumb. A hamburger menu hides the four pillars behind an extra tap.
- **Footer clears the tab bar.** The content column has `pb-16` below 768 px so the footer is never hidden behind the fixed bar.
- **Greeting.** Only a Google account name is used ("Welcome, Priya"). Email or phone accounts get "Welcome to NomadFinance", because a phone number reads badly as a name. The header still shows the full identifier.
- **Route element swap.** A pillar task replaces `<ComingSoon pillar={pillar} />` in `router.tsx` with its own page. The nav, cards and path stay as they are.
- **No new dependencies.** The mobile menu is CSS only. State libraries and new shadcn components were not needed.

## How later tasks plug in

| Task | What to do |
|---|---|
| NF-P1-011 (language selector) | Add `<LanguageSwitcher />` inside `Header.tsx`, next to the sign-out button. Put the other 5 languages' text in the `hi/tl/id/ne/bn` JSON files using the same keys as `en.json`. |
| NF-P1-021 (landing page) | Replace the `/` redirect element in `router.tsx` with the landing page. |
| NF-P1-023 (profile) | Add a `/profile` route inside the `AppShell` children. Link to it from `Header.tsx`. |
| NF-P1-026 (error boundary and toasts) | Wrap the router or `AppShell`; the shell has no error handling of its own. |
| A pillar page (NF-P2-…) | Put the page in `src/pages/<pillar>/`, then swap the route element. Nested paths such as `/remittance/history` go under the same route. Give a sub-page its own nav link only if the design needs one. |
| Adding or renaming a pillar | Edit `PILLAR_ITEMS` in `navItems.ts` and add its `nav.*` and `pillars.*` keys. The router picks it up automatically. |

## All commands, in order

Run from `frontend/` unless a step says otherwise.

### 0. Prerequisites

Node 20 or newer, pnpm 10 (see the pnpm and NVM notes in `NF-P1-009-frontend-firebase-auth.md` if `pnpm` fails on Windows), and Java 11 or newer for the Auth Emulator (`java -version`).

### 1. Install

```bash
pnpm install
```

No new packages, so `pnpm-lock.yaml` does not change.

### 2. Checks

```bash
pnpm lint
pnpm build
pnpm format:check
```

Expected: lint prints nothing (0 warnings), build ends with `✓ built in …` (JS bundle about 403 kB, 128 kB gzipped; it was 390 kB before routing and icons), and `All matched files use Prettier code style!`.

### 3. Run the app against the Auth Emulator

Terminal 1:

```bash
firebase emulators:start --only auth --project demo-nomadfinance
```

Terminal 2:

```bash
pnpm dev --mode emulator
```

Open **`http://127.0.0.1:5173/dashboard`** (use `127.0.0.1`, not `localhost`). It redirects to `/sign-in`. Sign in with a fake phone as described in `NF-P1-009-frontend-firebase-auth.md` step 3:

1. Choose `MY +60`, type `012-345 6789`, press **Send code**.
2. Read the fake SMS code:
   - **bash:** `curl -s http://127.0.0.1:9099/emulator/v1/projects/demo-nomadfinance/verificationCodes`
   - **PowerShell:** `Invoke-RestMethod http://127.0.0.1:9099/emulator/v1/projects/demo-nomadfinance/verificationCodes | Select-Object -ExpandProperty verificationCodes`
3. Enter the code. You land on the dashboard.

Stop both terminals with `Ctrl+C` when you are done.

### 4. Manual test checklist

Do this in the browser's DevTools device toolbar (**Ctrl+Shift+M**, or **Cmd+Shift+M** on Mac).

**Phone, 375 × 812**

1. The header shows "NomadFinance" and a sign-out icon. The four cards are stacked in one column.
2. A tab bar with Home, Remittance, Contracts, Radar and Identity is fixed at the bottom. Home is highlighted.
3. Scroll to the bottom: the footer is fully visible above the tab bar.
4. There is no horizontal scroll at any point.
5. Tap **Radar**: the page title is "Exploitation Radar", the tab is highlighted, and a "Coming soon" card shows.
6. Tap a dashboard card: it opens the same pillar page.

**Tablet, 768 × 1024**

7. The sidebar appears on the left, the tab bar is gone, and the cards form a 2 × 2 grid. The current page is highlighted in the sidebar.

**Desktop, 1280 px wide**

8. Same as tablet, with the content centred and at most about 900 px wide.

**Keyboard**

9. Press **Tab** once on a fresh page load: a "Skip to main content" link appears at the top left. Press **Enter**: focus moves to the page content and the URL gets `#main-content`.
10. Keep pressing **Tab**: focus goes through the brand link, sign-out, the sidebar links, then the cards, with a visible focus ring each time.

**Guard and edges**

11. Click the sign-out icon: you land on `/sign-in`, and `/dashboard` sends you back to `/sign-in`.
12. While signed out, open `/remittance`, sign in, and you return to `/remittance`.
13. Open `/no-such-page`: the "Page not found" page shows with a "Go to home" button.

**Emulator banner note.** In emulator mode the red "Running in emulator mode" banner from NF-P1-009 sits over the bottom of the screen, so on a phone it covers the tab bar. That only happens in emulator mode. To see the bar during testing, run `document.querySelector(".firebase-emulator-warning")?.remove()` in the DevTools console, or test with real Firebase.

### 5. Screenshots for the PR

Take these and attach them to the pull request: dashboard at 375 px (with the tab bar visible, see the note above), dashboard at 768 px or wider (with the sidebar), a pillar "coming soon" page, and the 404 page.

## Verified results (2026-09-25, Auth Emulator, Chrome via the desktop app's browser pane)

| Check | Result |
|---|---|
| `pnpm lint` / `pnpm build` / `pnpm format:check` | All pass; bundle 402.99 kB (127.63 kB gzip) |
| Signed-out `/dashboard` | Redirects to `/sign-in` |
| Phone sign-in through the emulator | Lands on the dashboard; header shows `+60123456789` |
| 375 px | No horizontal scroll (page width 375); sidebar hidden; tab bar shown; 4 cards in one column |
| Tab bar targets | 5 tabs, each 75 × 56 px |
| Footer vs tab bar (scrolled to the end) | Footer ends at 748 px, tab bar starts at 755 px: no overlap |
| Tap on the Radar tab | `/radar`, page title "Exploitation Radar", tab marked as the current page |
| 768 px | Sidebar shown, tab bar hidden, 2-column card grid, no horizontal scroll |
| Desktop | Sidebar, header and 2 × 2 cards; one header, one main, one footer, one visible nav |
| Sidebar link click | `/remittance`, link marked as the current page, "Coming soon" card |
| Skip link | First Tab stop; Enter puts focus on `main#main-content`, no page reload |
| Sign-out | Back to `/sign-in`, shell gone |
| Signed-out `/remittance` | Redirects to `/sign-in` and remembers `/remittance` |
| Unknown URL | "Page not found" page |
| Browser console | No errors in a clean tab across sign-in, dashboard, skip link, sign-out and 404. One `501` resource error appeared once in a long-lived tab and could not be reproduced; the failing URL was not captured. |

Not tested: throttled 3G in DevTools (the shell adds no network calls of its own), real devices, real Google or SMS sign-in.

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind and the existing shadcn/ui `Button`; no new component library
- [x] Fully mobile responsive (375, 768 and desktop widths checked in the browser pane)
- [ ] Works on slow network (throttled 3G): not tested. The shell is static and makes no requests of its own.
- [x] Loading states: nothing new is asynchronous here; the sign-in loading spinner stays in `ProtectedRoute`
- [x] Error states: unknown URLs handled by the 404 page; there is no data to fail yet
- [ ] i18n keys for all 6 languages: English keys added; the other 5 files are still empty and belong to NF-P1-011
- [ ] Screenshots added to the PR: take them with step 5
- [x] Accessibility: skip link, one header/nav/main/footer landmark each, labelled nav, current page marked, sign-out has a label, keyboard order checked

## Commit

Branch: `feature/frontend-app-shell`. No shared files were changed.

```bash
git add frontend/src/components/layout frontend/src/components/common/EmptyState.tsx \
  frontend/src/pages/Dashboard.tsx frontend/src/pages/ComingSoon.tsx frontend/src/pages/NotFound.tsx \
  frontend/src/router.tsx frontend/src/App.tsx frontend/src/i18n/en.json frontend/README.md \
  docs/runbooks/NF-P1-009-frontend-firebase-auth.md docs/runbooks/NF-P1-010-frontend-app-shell.md
git commit -m "feat(frontend): add app shell, navigation and pillar dashboard" -m "Refs: NF-P1-010"
```

`frontend/src/App.tsx` is a deletion; naming it in `git add` stages that. Before pushing, run `git status` and confirm nothing else is listed.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Everything redirects to `/sign-in` | You are signed out (or the emulator was restarted, which clears its users). Sign in again. |
| Tab bar not visible on a phone-sized screen | In emulator mode the red banner covers it. See the emulator banner note in step 4. |
| Both the sidebar and the tab bar are missing | The window is between the breakpoints or the CSS did not build. Restart `pnpm dev`, then hard-reload. |
| `Failed to resolve import "@/App"` | Something still imports the deleted `App.tsx`. Nothing in the repo should; search for `@/App`. |
| A translated string shows as its key (for example `nav.radar`) | The key is missing from `en.json`. Add it; `t()` shows the key when a string is missing. |
| A pillar card or tab opens "Coming soon" | Expected until that pillar's task replaces the route element in `router.tsx`. |
| Clicking the skip link changes the URL to `…#main-content` | Expected; the hash only marks where focus went. |
| `pnpm lint` fails with `react-refresh/only-export-components` on a new file | Keep constants (like the nav list) in a separate `.ts` file from the component, as `navItems.ts` does. |
| The pane's page jumps to other routes while you test | Someone else is clicking in the same browser tab. Test in your own tab. |

## Not covered here

- Language selector and translations for the other 5 languages: NF-P1-011
- Landing page at `/`: NF-P1-021
- Profile page and account settings: NF-P1-023
- Error boundary and toasts: NF-P1-026
- The real pillar pages, brand colours, logo and PWA install: later tasks (NF-P1-024, NF-P1-012)
- Dark mode toggle: the dark tokens exist but nothing switches them yet
