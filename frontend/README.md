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

## Deploy

Manual deploy (until GitHub Actions lands in NF-P1-020): from `frontend/`, `pnpm build` then `firebase deploy --only hosting --project nomadfinance-prod`. `.env.local` must hold the real Firebase web config before `pnpm build`, or the deployed app shows a blank page.

Live URL: https://nomadfinance-prod.web.app

Full setup, verified commands and troubleshooting: [`docs/runbooks/NF-P1-008-firebase-hosting-deploy.md`](../docs/runbooks/NF-P1-008-firebase-hosting-deploy.md).
