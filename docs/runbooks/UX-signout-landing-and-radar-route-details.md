# Sign-out to the landing page, and report details on the Radar routes

Two changes found while using the app. Neither has a tracker ID.

## Summary

1. **Signing out, or deleting an account, now ends on the landing page.** Before, sign-out ended on the sign-in page, and a signed-out person had no way back to the landing page except editing the address.
2. **Each money route on the Radar page opens to show who was reported and what was reported.** The map is unchanged.

## 1. Signed out means landing page

**Cause.** The header did `await signOut(); navigate("/")`. The moment Firebase reports "nobody signed in", the page being left (`ProtectedRoute`) redirected to `/sign-in`, before the `navigate("/")` line ran. A code comment said that redirect was what the line prevented; it did not.

**Change.** `ProtectedRoute` itself now sends a signed-out visitor to `/`:

| Situation | Before | Now |
|---|---|---|
| Sign out from the header or the onboarding page | sign-in page | landing page |
| Delete account | sign-in page | landing page |
| Open a link to a signed-in page while signed out | sign-in page | landing page |
| Session expired while using the app | sign-in page | landing page |

From the landing page, "Get started" opens sign-in.

**The "account deleted" message** used to be shown on the sign-in page. It now shows at the top of the landing page, once, and is gone after a reload.

**Things to know.**
- A link to a signed-in page (for example `/radar/alerts`) used to remember where the person was going and return there after sign-in. It no longer does: after sign-in they land on the dashboard.
- A signed-in person who opens `/` still goes straight to the dashboard, as before.

## 2. Route details on the Radar page

"By money route" is now a list of rows (one per route, most reports first). A row opens to show:

- **the businesses reported on that route**, most reports first: name, type, risk level, "Community flagged" if it is, and its report count (the same counts the route total adds up);
- **each business's reports**: kind of problem, date, the summary (or the original text when there is none), and where it came from;
- **a footer** with "Show all N reports" when there are more than 3, and "View business profile".

Details:
- More than 5 businesses on a route: the first 5, then "Show N more businesses".
- A route with no business says so and offers "Report a problem".
- Reports load when a row is opened and are kept for a minute, so opening the business page afterwards is instant. No backend change: it uses the same call as the business page.
- A business's report count is not split by route (the existing map note says the same), so a business seen on two routes shows all its reports under both. A report about a different route says "Route: …" so the list is not confusing.
- The list is one column, not two. In a two-column grid, opening one row stretched its neighbour into an empty tall box.
- Rows are buttons: keyboard (Enter, Space), `aria-expanded`, 44 px tall to tap.
- Six languages. The five translations are written by the team, not a translator: have a native speaker read them (`radar.heatmap.*`, the new keys at the end).

## Files

| File | Change |
|---|---|
| `frontend/src/components/common/ProtectedRoute.tsx`, `.test.tsx` (new) | Signed out goes to `/` |
| `frontend/src/components/profile/DeleteAccount.tsx`, `src/services/accountService.ts` | Deleting goes to `/` |
| `frontend/src/pages/Landing.tsx` | Shows the "account deleted" message |
| `frontend/src/components/layout/Header.tsx` | Comment only |
| `frontend/src/components/radar/CorridorDetails.tsx`, `.test.tsx` (new) | The openable route row |
| `frontend/src/components/radar/EntityReportList.tsx` | A compact look and a per-report note |
| `frontend/src/pages/radar/RadarHeatmap.tsx` | Uses the new rows |
| `frontend/src/utils/radarMap.ts`, `.test.ts` | `entitiesOnCorridor` |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | 8 new strings each |

No shared file was changed.

## Verified

- `tsc`, `eslint`, `prettier` clean; **238 tests pass** (16 new); the build passes.
- `ProtectedRoute` test checked by putting the old destination back: it fails.
- In a real browser on the emulators (signed in by phone code, radar demo data loaded): sign out → landing page; `/dashboard` and `/radar` while signed out → landing page; "Get started" → sign-in → sign in again works; `/` while signed in → dashboard; deleting an account → landing page with the message, gone after reload. All 10 checks passed.
- Radar page looked at on desktop (1280 px) and phone (375 px) in light and dark, in Hindi, with two rows open at once and with the empty route: no sideways scroll, text wraps, nothing overlaps. Rows open and close by click, Enter and Space.

## How to try it (emulators and `pnpm dev --mode emulator` running; see the NF-P1-001 runbook)

1. Sign in, then use the sign-out icon in the header. You should land on the landing page, not sign-in.
2. Signed out, open `http://localhost:5173/dashboard`. Landing page again.
3. Sign in, open **Exploitation Radar**, scroll to "By money route", tap a route. Open several; close with the same tap.
4. Change the filter above the map to "Employer": every route says "No business has been reported on this route yet."
5. Switch the language in the header to Hindi and open a route.

Radar demo data: `python -m src.loaders.radar_seed` from `data-scripts/`, with the emulator variables set (see its README).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| A route row opens and shows a spinner that never ends | The backend is not running, or `/api` is not reached | Start the backend; check the Vite proxy |
| "We could not load these reports." with Retry | The report call failed (offline, or the server) | Retry; the rest of the page still works |
| A route shows a total but few reports | The total adds each business's full count, and some reports are about another route | Expected; those reports carry a "Route: …" line |

## Commit and PR

Branch: `fix/signout-landing-radar-details` (already checked out).

```bash
git add frontend docs
git status
```

```bash
git commit -m "fix(frontend): sign out to landing page; add report details to radar routes"
```

PR title: `fix(frontend): signed-out visitors go to the landing page, and Radar routes open to show reports`

## Not covered here

- A native-speaker check of the five translations.
- A real phone: the layout was checked at phone width in Chromium only (D-72 covers real devices).
- Remembering the page a person was going to when they are sent to sign in (see D-96).
