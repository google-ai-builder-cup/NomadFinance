# NF-P1-025: Firebase Analytics

Usage tracking for the pitch: how many people open each pillar, sign in, finish onboarding
and analyze a contract. Built on Firebase Analytics (Google Analytics 4), which is free.

## What is measured

| Event | Sent when | Parameters |
| --- | --- | --- |
| `page_view` | every route change inside the signed-in app | `page_path` (pathname only, never the query string) |
| `pillar_used` | a person enters a pillar (`/remittance`, `/contract`, `/radar`, `/identity`) | `pillar_name` |
| `contract_analyzed` | a contract finishes analysis. **Helper only**: Contract Shield calls `trackContractAnalyzed()` when it is built | `host_country` |
| `login` | Google popup or phone code accepted | `method` (`google` or `phone`) |
| `onboarding_completed` | the last onboarding question is saved | none |

Moving between pages of the same pillar counts as one `pillar_used`. The signed-in shell is
the only place page views come from, so the landing and sign-in pages are not counted, and
a Google sign-in that finishes by full-page redirect (popup blocked) sends no `login` event.

**User properties** (set once the profile loads, cleared on sign-out because phones are
shared): `host_country`, `home_country`, `job_type`, `preferred_language`.

**Never sent:** name, email, phone number, uid, contract text, or any URL query string.
`setUserId` is deliberately not used.

## When it is on

`lib/analytics.ts` sends events only when `VITE_FIREBASE_MEASUREMENT_ID` is set and the
Auth emulator is not in use. Otherwise every call is a silent no-op and the SDK is never
downloaded. It also stays off in browsers that cannot run it (`isSupported()`), and a
failure to load is logged with `console.warn` and never breaks the app.

The SDK is loaded on first use as its own chunk, not in the main bundle.

## One-time setup

1. Firebase Console → Project settings → Integrations → Google Analytics: **Enabled**.
2. `firebase apps:sdkconfig WEB --project nomadfinance-prod` now lists a `measurementId`
   (`G-...`). It is a public identifier, like the API key.
3. GitHub → Settings → Secrets and variables → Actions → **Variables** →
   `VITE_FIREBASE_MEASUREMENT_ID`.
4. `.github/workflows/frontend-deploy.yml` passes the variable to `pnpm build`:
   `VITE_FIREBASE_MEASUREMENT_ID: ${{ vars.VITE_FIREBASE_MEASUREMENT_ID }}`.
   It is not part of the "Check build settings" step, so a missing variable turns
   Analytics off instead of failing the deploy.

## Try it locally (DebugView)

```bash
cd frontend
# add your measurement ID to .env.local:  VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX
pnpm dev
```

Dev builds set `debug_mode`, so their events go to DebugView and stay out of the reports.
Open Firebase Console → Analytics → DebugView, sign in, open the pillars and finish
onboarding with a new account. Expect `page_view`, `pillar_used`, `login` and
`onboarding_completed`, and the four user properties on the device. Remove the line from
`.env.local` afterwards.

With the ID left out (or with `pnpm dev --mode emulator`) nothing is sent: DebugView stays empty.

Unit tests (no network): `pnpm exec vitest run src/lib/analytics.test.ts`.

## After deploy: check the live site

Firebase Console → Analytics → Realtime. Open https://nomadfinance-prod.web.app, sign in
and click the pillars: events appear within a minute. Reports (Events, Engagement) fill
in after roughly 24 hours.

## Pitch screenshots

- **Analytics → Events**: count of `pillar_used`, `login`, `onboarding_completed`,
  `contract_analyzed`.
- **Analytics → Realtime**: users by country and by page.
- To break events down by `pillar_name`, `host_country` or the user properties, register
  them first: Analytics → Admin → Custom definitions → Create custom dimension (scope
  *Event* for `pillar_name` and `host_country`, scope *User* for the four properties). A
  dimension only reports data collected after it is registered, so do this early.

## Adding an event later

Add a typed function next to the others in `lib/analytics.ts`, call it from the feature,
and keep parameters coarse (enums, counts). GA4 keeps event names to 40 characters and
allows 500 distinct events on the free tier.

## Turn it off

Delete the GitHub variable `VITE_FIREBASE_MEASUREMENT_ID` and re-run "Frontend deploy".
No code change is needed.
