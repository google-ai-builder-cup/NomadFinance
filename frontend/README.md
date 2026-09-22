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
1. Copy .env.example to .env.local
2. pnpm install
3. pnpm dev

## Deploy
Automatic on merge to main via GitHub Actions.
