# NF-P1-021 — Landing Page + Emotional Hook

## Summary

`/` was a bare redirect straight to `/dashboard` (a placeholder left by NF-P1-010, with a
`TODO(Aditya): replace this redirect with the landing page NF-P1-021` in `router.tsx`). It's now
a real public marketing page: a hero, a "Meet Priya" emotional-hook section, previews of all 4
pillars, and two sign-in CTAs, all mobile-first. A signed-in visitor never sees it — they're sent
straight to `/dashboard`, the same pattern `SignIn.tsx` already uses.

No new UI library or dependency was needed: everything is built from pieces NF-P1-009/010/011
already shipped (`Button`, `Footer`, `LanguageSelector`, `PILLAR_ITEMS`, `useAuth`, `useI18n`).

## Files

| File | Purpose |
|---|---|
| `frontend/src/pages/Landing.tsx` | The page (was an empty stub) |
| `frontend/src/router.tsx` | `/` now renders `<Landing />` instead of `<Navigate to="/dashboard" />`; TODO removed |
| `frontend/src/i18n/*.json` (all 6) | New `landing` key block: `brand`, `hero.*`, `story.*`, `pillars.*`, `finalCta.*` |

## Flow

```
"/"
  └─ useAuth()
       ├─ loading   → <LoadingSpinner fullScreen />
       ├─ user set  → <Navigate to="/dashboard" replace />   (same as SignIn.tsx)
       └─ signed out → hero → "Meet Priya" story → 4 pillar preview cards → final CTA → Footer

Each pillar card and every CTA → <Link to="/sign-in" state={{ from: { pathname: pillar.to } }}>
  → SignIn.tsx already reads location.state.from.pathname and redirects there post sign-in
    (through RequireOnboarding first if the profile isn't finished yet, NF-P1-022)
```

## Design choices worth knowing

- **No new dependency.** The page reuses `Footer`, `LanguageSelector`, `PILLAR_ITEMS`, and the
  existing `Button`/card markup from `Dashboard.tsx`, so it themes itself automatically once
  NF-P1-024 (brand colors) replaces the placeholder shadcn slate tokens in `tokens.css` — nothing
  on this page hardcodes a color.
- **Pillar cards link to `/sign-in`, not to the pillar route directly.** Signed-out visitors can't
  reach a protected pillar page anyway; sending the intended destination through
  `location.state.from.pathname` (already consumed by `SignIn.tsx`) means clicking "Contract
  Shield" and then signing in lands you on `/contract` (today, `ComingSoon`) instead of the
  generic dashboard.
- **"Meet Priya" is marketing copy, not tied to a real account.** The seeded demo persona
  (`data-scripts/data/seed/users/priya_sg_domestic.json`) is still an empty stub — that's
  NF-P3-021, Week 3. The story here is written to match her established facts (India → Singapore,
  domestic worker) used elsewhere in the repo (`uid_priya_demo` in the data-model docs, "Signed in
  as Priya Sharma" in the NF-P1-009 runbook), but it doesn't read from or write to any user data.
- **Translations are best-effort, not reviewed by a native speaker** — same caveat NF-P1-011
  already flagged for the other 5 languages; worth a review pass before the demo.

## All commands, in order

Run from `frontend/`.

```bash
pnpm lint
pnpm build
pnpm dev
```

Open `http://localhost:5173/`:

1. Signed out: the landing page renders — hero, "Meet Priya", 4 pillar cards, final CTA, footer.
2. Click "Get started", a pillar card, and the final "Sign in" button — all three land on
   `/sign-in`.
3. Switch languages with the selector top-right — the whole page updates instantly, no reload
   (checked at 375px width too, including Bengali, the longest script in use).
4. Sign in, then navigate back to `/` — redirected straight to `/dashboard`, the landing page
   never shows again for a signed-in visitor.

## Verified results (2026-09-27, browser pane)

| Check | Result |
|---|---|
| `pnpm lint` | Clean |
| `pnpm build` | Clean (`tsc -b && vite build`) |
| `/` signed out, desktop | Hero, story, 4 pillar cards, final CTA, footer all render |
| `/` signed out, 375px width | No overflow or wrap on any section, including the hero heading and Bengali script |
| Language switch to Bengali (longest script) | Whole page updates instantly, no reload, no layout break |
| Clicking a pillar card | Navigates to `/sign-in` |
| Signed-in visitor navigates to `/` | Redirected to `/dashboard`, landing page never renders |

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind + shadcn/ui (reused, no new UI dependency)
- [x] Fully mobile responsive (checked at 375px)
- [ ] Works on slow network (throttled 3G): not tested — nothing here is network-dependent beyond
      the initial bundle, which NF-P1-012's PWA setup already caches
- [x] Loading states: `useAuth()`'s `loading` flag shows `LoadingSpinner` before deciding whether
      to render the page or redirect
- [x] Error states: n/a, no data fetching on this page
- [x] i18n keys added for all user-facing strings, all 6 languages
- [ ] Screenshots added to the PR
- [x] Accessibility: skip-to-content link (same pattern as `AppShell`), semantic `<section>` /
      `<h1>`/`<h2>` structure with `aria-labelledby`, all interactive elements keyboard-reachable
      with a visible focus ring

## Commit

Branch: `feature/frontend-landing-page`.

```bash
git add frontend/src/pages/Landing.tsx frontend/src/router.tsx frontend/src/i18n/*.json \
  docs/runbooks/NF-P1-021-landing-page.md
git commit -m "feat(frontend): add landing page with Meet Priya story" -m "Refs: NF-P1-021"
```

## Not covered here

- Brand colors, logo, favicons: NF-P1-024
- Seeding a real Priya demo account: NF-P3-021 (Week 3)
- Native-speaker accuracy review of hi/tl/id/ne/bn translations
