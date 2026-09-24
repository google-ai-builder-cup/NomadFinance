# NF-P1-008 — Deploy Skeleton to Firebase Hosting

## Summary

The frontend (bootstrapped in NF-P1-007) now deploys to **Firebase Hosting** as a static SPA. `frontend/firebase.json` declares only a `"hosting"` key — `public: "dist"` (Vite's build output), a catch-all `rewrites` rule sending every path to `/index.html` (so React Router's client-side routing works on a hard refresh or direct link), and a long-lived immutable `Cache-Control` header for `**/assets/**` (Vite content-hashes those filenames, so caching them for a year is safe — a new build gets new filenames). `frontend/.firebaserc` pins the project alias `default` → `nomadfinance-prod`, so plain `firebase deploy` never needs `firebase use` first. No `"firestore"` or `"storage"` keys yet — `infra/firebase/firestore.rules` and `frontend/firestore.rules`/`storage.rules` are still empty stubs owned by NF-P1-014; adding those keys before real rules exist would make `firebase deploy` try to publish nothing/empty rules.

Live URL: **https://nomadfinance-prod.web.app** (hosting site `nomadfinance-prod`, already provisioned under the `nomadfinance-prod` Firebase/GCP project by NF-P0-005 — nothing new to create here, unlike NF-P1-003 which had to create its own Artifact Registry repo and service account).

Deploy is manual via the developer's own `firebase login` session (same account as the rest of the team, `aibuildercup23@gmail.com`), matching NF-P1-003's approach of proving the pipeline by hand before GitHub Actions automates it (NF-P1-020).

## Files

| File | Purpose |
|---|---|
| `frontend/firebase.json` | Hosting config: public dir, SPA rewrites, cache headers |
| `frontend/.firebaserc` | Project alias — `default` → `nomadfinance-prod` |
| `frontend/README.md` | Deploy section: short version of this runbook |

Cloud resources used (already existed, none created by this task):

| Resource | Name | Notes |
|---|---|---|
| Firebase project | `nomadfinance-prod` | Same project as backend/Firestore (NF-P0-004/NF-P0-005) |
| Hosting site | `nomadfinance-prod` | Default site, auto-created when Hosting was enabled in NF-P0-005 |

## Flow

```
pnpm build
  └─ dist/  (index.html, hashed JS/CSS in assets/, copies of public/*)
firebase deploy --only hosting
  └─ uploads dist/ contents  ──►  Firebase Hosting (CDN + SSL)
  └─ new release, 100% traffic immediately (no gradual rollout on Hosting)
public request ──► Firebase Hosting CDN ──► rewrites unmatched paths to /index.html ──► React Router takes over client-side
```

## All commands, in order

Run from `frontend/`. Commands are the same in PowerShell and bash unless noted.

### 0. Prerequisites

```bash
firebase --version
firebase login:list
```

Expected: a CLI version prints, and the team account (`aibuildercup23@gmail.com`) shows as logged in. If not: `firebase login`.

```bash
firebase projects:list
```

Expected: `nomadfinance-prod` appears in the list.

### 1. Build

```bash
pnpm build
```

Expected: `dist/index.html` plus hashed JS/CSS under `dist/assets/`, plus whatever's in `public/` copied verbatim (favicon, manifest, robots.txt — currently placeholder/empty files from other tasks).

### 2. Deploy

```bash
firebase deploy --only hosting --project nomadfinance-prod
```

`--only hosting` is deliberate: once NF-P1-014 adds `"firestore"`/`"storage"` keys to `firebase.json`, a bare `firebase deploy` would try to publish those too — scoping this command to `hosting` keeps this task's deploy from touching anything else, now or later.

Expected, ending with:
```
+  Deploy complete!

Project Console: https://console.firebase.google.com/project/nomadfinance-prod/overview
Hosting URL: https://nomadfinance-prod.web.app
```

### 3. Verify the public URL

**Windows PowerShell**
```powershell
Invoke-RestMethod https://nomadfinance-prod.web.app/ | Select-Object -First 5
```

**bash**
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://nomadfinance-prod.web.app/
curl -s https://nomadfinance-prod.web.app/ | head -20
```

Expected: `200`, and the HTML `<script>`/`<link>` tags reference the exact hashed filenames `pnpm build` just produced (confirms the live site isn't serving a stale build).

Check the SPA rewrite (any unknown path should still serve `index.html`, not a Hosting 404):

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://nomadfinance-prod.web.app/some/unknown/route
```

Expected: `200`.

Check the asset caching header:

```bash
curl -sI https://nomadfinance-prod.web.app/assets/<hashed-filename>.js | grep -i cache-control
```

Expected: `Cache-Control: public, max-age=31536000, immutable`.

Open `https://nomadfinance-prod.web.app/` in a browser: same placeholder screen as `pnpm dev` (NF-P1-007) — "NomadFinance" heading, "Frontend bootstrap — NF-P1-007" subtext, one working shadcn `Button`, no console errors.

## Verified results (2026-09-24, commit `78fecc6`)

| Check | Result |
|---|---|
| `firebase login:list` / `projects:list` | Logged in as `aibuildercup23@gmail.com`; `nomadfinance-prod` visible |
| `firebase hosting:sites:list` | Default site `nomadfinance-prod` already existed (from NF-P0-005) |
| `pnpm build` | `dist/index.html` 0.54 kB, `assets/index-*.css` 9.73 kB, `assets/index-*.js` 261.17 kB (84.47 kB gzip) |
| `firebase deploy --only hosting` | `found 8 files in dist`, upload complete, release complete |
| `GET /` | `200`, HTML references the exact hashed filenames from this build |
| `GET /assets/<hash>.js` | `200`, 261172 bytes (matches build), `Content-Type: text/javascript` |
| `GET /assets/<hash>.css` | `200`, 9727 bytes (matches build) |
| `Cache-Control` on `/assets/**` | `public, max-age=31536000, immutable` — the `headers` rule in `firebase.json` took effect |
| SPA rewrite (`GET /some/unknown/route`) | `200` — served `index.html`, not a Hosting 404 |
| Visual check in a browser | Not captured this session — the browser tool returned "Policy check temporarily unavailable" for this live external URL; the `curl` checks above independently confirm the exact same build output that renders correctly under `pnpm dev` (NF-P1-007) is what's being served live. Worth a quick manual look when convenient. |

## Definition of Done

- [x] `firebase.json` configured (hosting only — firestore/storage keys deferred to NF-P1-014)
- [x] `firebase deploy` run successfully against `nomadfinance-prod`
- [x] Public URL verified: loads (200), serves the current build's exact assets, SPA rewrite works, cache headers applied
- [x] Documented here and in `frontend/README.md`
- [x] No secrets in the repo (deploy uses the developer's own `firebase login` session, not a committed key)
- [ ] Visual (non-curl) confirmation in a browser — recommended follow-up, browser tool was unavailable this session
- [ ] Reviewed by at least one teammate
- [ ] Committed to the repo

## Commit

Branch: `chore/frontend-firebase-hosting`

```bash
git add frontend/firebase.json frontend/.firebaserc frontend/README.md docs/runbooks/NF-P1-008-firebase-hosting-deploy.md
git commit -m "chore(frontend): deploy skeleton to Firebase Hosting" -m "Refs: NF-P1-008"
```

Before pushing, run `git status` and confirm nothing else is staged.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Error: Failed to get Firebase project nomadfinance-prod` | Not logged in, or logged in as the wrong account. `firebase login`, then `firebase login:list` to confirm. |
| `Error: Specified public directory 'dist' does not exist` | Run `pnpm build` first — Hosting deploys whatever's already in `dist/`, it doesn't build for you. |
| Deployed site shows an old version | Browser cache, not a Hosting problem — Hosting always serves the latest release. Hard-refresh, or check `Cache-Control` isn't being applied to `index.html` itself (only `**/assets/**` has the long-cache header; `index.html` is served with Hosting's default short cache). |
| `firebase deploy` also tries to deploy Firestore rules/indexes | `firebase.json` picked up a `"firestore"`/`"storage"` key somewhere (e.g. after NF-P1-014 lands) and you ran a bare `firebase deploy`. Use `--only hosting` to scope it, as this runbook's commands do. |
| Unknown route returns a Hosting 404 instead of the app | `rewrites` in `firebase.json` is missing or wrong — needs `{ "source": "**", "destination": "/index.html" }`. |
| `(node:...) [DEP0040] DeprecationWarning: The punycode module is deprecated` | Harmless Node warning from inside the `firebase-tools` CLI itself, not this project. Ignore it. |

## Not covered here

- Firestore/Storage security rules and their own deploy: NF-P1-014
- Automated deploy on merge to main via GitHub Actions (OIDC, no JSON keys): NF-P1-020
- Firebase Auth, sign-in flows: NF-P1-009
- PWA install prompt / offline support: NF-P1-012
- Custom domain (if any) — not needed for a hackathon submission; `*.web.app` is the demo URL
