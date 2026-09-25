# NomadFinance — Frontend

React 18 PWA served via Firebase Hosting.

## Stack

- React 18 + Vite + TypeScript
- Tailwind CSS + shadcn/ui + Radix UI
- Zustand + TanStack Query
- Firebase Web SDK (Auth + Firestore + Storage + FCM)
- react-i18next (6 languages: EN, HI, TL, ID, NE, BN)
- vite-plugin-pwa (installable + offline)

## Structure

- src/pages/ — Route components (thin, per pillar)
- src/components/ — UI primitives + layout + shared + pillar-specific
- src/hooks/ — Custom React hooks (useAuth, useContract, etc.)
- src/services/ — Typed API client wrappers
- src/lib/ — 3rd-party clients (Firebase, i18n, Sentry, Analytics)
- src/store/ — Zustand global state
- src/types/ — TypeScript types (mirror backend Pydantic)
- src/i18n/ — UI label translations per language

## Local Dev

1. Copy .env.example to .env.local and fill in the Firebase web config (`firebase apps:sdkconfig WEB --project nomadfinance-prod`)
2. pnpm install
3. pnpm dev — serves at http://127.0.0.1:5173

Checks before every push: `pnpm lint`, `pnpm build`, `pnpm format:check`.

Bootstrap details (pinned versions and why, Tailwind/shadcn/ui setup, troubleshooting): [`docs/runbooks/NF-P1-007-frontend-bootstrap.md`](../docs/runbooks/NF-P1-007-frontend-bootstrap.md).

## Sign-in (Firebase Auth)

Google and phone (SMS code) sign-in, `useAuth()`, and `ProtectedRoute` for signed-in pages. To test without real accounts or SMS, run the Auth Emulator and the app in emulator mode:

1. `firebase emulators:start --only auth --project demo-nomadfinance`
2. `pnpm dev --mode emulator`, then open http://127.0.0.1:5173/sign-in (use `127.0.0.1`, not `localhost`)

Full flow, commands and troubleshooting: [`docs/runbooks/NF-P1-009-frontend-firebase-auth.md`](../docs/runbooks/NF-P1-009-frontend-firebase-auth.md).

## Onboarding

After the first sign-in, `RequireOnboarding` sends users to `/onboarding` until `users/{uid}` has `onboarding_completed_at`. Four questions (language, host country, home country, job type) are saved straight to Firestore; `firestore.rules` validates them. The allowed values live in `src/types/enums.ts` and must match the rules.

Details and how to test: [`docs/runbooks/NF-P1-022-user-onboarding.md`](../docs/runbooks/NF-P1-022-user-onboarding.md).

## App shell and navigation

Every signed-in page renders inside `AppShell` (header, footer, and a left sidebar on tablet and desktop or a bottom tab bar on phones). `/dashboard` shows the four pillar cards; `/remittance`, `/contract`, `/radar` and `/identity` show a "coming soon" page until their own tasks replace the route element in `src/router.tsx`. The nav items live in one list, `src/components/layout/navItems.ts`, so adding a pillar page means editing that list and the router only.

Full structure, how to test it, and how later tasks plug in: [`docs/runbooks/NF-P1-010-frontend-app-shell.md`](../docs/runbooks/NF-P1-010-frontend-app-shell.md).

## PWA

`vite-plugin-pwa` generates a web manifest and a Workbox service worker at build time (`pnpm build`, not `pnpm dev` — the service worker only registers against a built app). Every signed-in page shows a dismissible "Install NomadFinance" banner once the browser fires `beforeinstallprompt` (Chrome/Edge/Android only; iOS never fires it). Icons and manifest colors are real branding as of NF-P1-024.

Full setup, how to verify installability, and how later tasks (real icons, update-available toast) plug in: [`docs/runbooks/NF-P1-012-frontend-pwa.md`](../docs/runbooks/NF-P1-012-frontend-pwa.md).

## Brand assets

Color palette lives in `src/styles/tokens.css` as shadcn-style CSS variables (`--primary`, etc.) — every component already themes off these, so a palette change here needs no component edits. Logo sources are `public/brand/logo-full.svg` (lockup, for docs/pitch deck) and `public/brand/logo-mark.svg` (icon, source for every favicon/app icon). Every raster file — `favicon.ico`, `apple-touch-icon.png`, `public/icons/*`, `public/splash/*` — is generated from those two SVGs by `scripts/generate-brand-assets.sh`; re-run it after editing either source (needs `rsvg-convert`, see the script's header comment).

Full palette (hex values for the pitch deck), rationale, and the generation pipeline: [`docs/runbooks/NF-P1-024-brand-assets.md`](../docs/runbooks/NF-P1-024-brand-assets.md).

## Deploy

Manual deploy (until GitHub Actions lands in NF-P1-020): from `frontend/`, `pnpm build` then `firebase deploy --only hosting --project nomadfinance-prod`. `.env.local` must hold the real Firebase web config before `pnpm build`, or the deployed app shows a blank page.

Live URL: https://nomadfinance-prod.web.app

Full setup, verified commands and troubleshooting: [`docs/runbooks/NF-P1-008-firebase-hosting-deploy.md`](../docs/runbooks/NF-P1-008-firebase-hosting-deploy.md).
