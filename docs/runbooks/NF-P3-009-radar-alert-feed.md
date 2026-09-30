# NF-P3-009 — Radar: Alert Feed

Originally assigned to Aditya; picked up on your confirmation.

## Summary

The notification feed (`users/{uid}/notifications`): read/unread state, tap-to-open deep links, reachable from a new "Alerts" button on the heatmap. Plus the piece nothing in the app had built yet — actually requesting notification permission and registering an FCM push token, so NF-P3-004's alert cron has something to push to.

Everything this task needed was already provisioned in `firestore.rules` (owner-read on `notifications`, owner-update on exactly `read`/`read_at`, `fcm_tokens` already an allowed, size-capped profile field) — **no backend or rules changes**. This task is 100% frontend, using direct Firestore reads/writes, the same pattern the heatmap and profile forms already use.

## Files

| File | Change |
|---|---|
| `types/notification.ts` (new) | `AppNotification` — `users/{uid}/notifications/{id}` |
| `services/notificationService.ts` (new) | `listNotifications`, `markNotificationRead` |
| `services/userService.ts` | `saveFcmToken` (`arrayUnion`, not a plain write — see decisions) |
| `lib/firebase.ts`, `.env.example`, `vite-env.d.ts` | `messagingSenderId` + the two new push env vars, both optional |
| `lib/messaging.ts` (new) | `requestPushToken`, `listenForPushes`, `pushPermission`, `isPushConfigured` — every path gracefully no-ops, never throws |
| `public/firebase-messaging-sw.js` (new) | Background push handler, registered on its own scope |
| `vite.config.ts` | Excludes the new service worker from the PWA plugin's precache list (see decisions) |
| `hooks/useNotifications.ts` (new) | `useNotifications`, `useMarkNotificationRead`, `usePushPermission`, `useEnablePush`, `usePushSync` |
| `components/radar/AlertItem.tsx` (was an empty stub) | One feed row |
| `pages/radar/RadarAlerts.tsx` (was an empty stub) | The feed page |
| `router.tsx` | `/radar/alerts` |
| `pages/radar/RadarHeatmap.tsx` | New "Alerts" button next to "Report a problem" — there was no bell icon or other entry point anywhere yet |
| `components/layout/AppShell.tsx` | `usePushSync()` — one line, mirrors `useAnalytics()` in the same file |
| `components/profile/NotificationsForm.tsx` | New `PushStatus` sub-component: permission state + an "Enable" button, in the existing notification-settings section |
| `i18n/{en,hi,tl,id,ne,bn}.json` | New `radar.alerts.*`, `radar.heatmap.alerts`, `profile.notifications.push*` keys, all 6 languages |

## Decisions

1. **Background push (closed/backgrounded tab) is built but not live-verified.** Getting a token at all needs a registered service worker, so `firebase-messaging-sw.js` is real and correct — but confirming an actual push arrives while the tab is backgrounded needs a real VAPID key and a real FCM send, neither of which I have. The feed itself works from Firestore regardless of whether push ever succeeds, same as NF-P3-004 already assumes.
2. **The VAPID key is a real credential I can't generate** (Firebase console → Project settings → Cloud Messaging → Web Push certificates). `isPushConfigured` requires both `VITE_FIREBASE_MESSAGING_SENDER_ID` and `VITE_FIREBASE_VAPID_KEY`; either missing, and every push code path silently no-ops — confirmed live (see Verified results).
3. **The service worker registers on its own scope** (`/firebase-cloud-messaging-push-scope`), not `/` — this app already has `vite-plugin-pwa`'s own service worker controlling `/`, and two workers both claiming the same scope would fight over which one answers fetch events. Firebase's own docs use this same coexistence pattern.
4. **`vite.config.ts` now excludes `firebase-messaging-sw.js` from the PWA plugin's precache manifest.** Caught this myself while checking the build output (35 precached entries where I expected 34): a service worker script must never be precached by a *different* service worker, or the browser's own update check for it (a plain network fetch) would be served a stale cached copy instead of fresh bytes. Confirmed by rebuilding: precache count back to 34, the file itself still served as a static asset.
5. **A foreground push shows a generic toast, not the push's own title/body.** The existing toast system (`hooks/useToast.ts`) takes an i18n `messageKey`, translated live on a language switch; a push's title/body already arrives pre-translated, real text from the backend — showing it would need a second, parallel "raw text" toast shape built just for this one caller. The toast prompts "You have a new alert" with a button to the feed, which shows the real content.
6. **`saveFcmToken` uses `arrayUnion`, not the existing generic `updateProfile`/`ProfileChanges` path.** A person may have several browsers or devices; the generic profile-edit mechanism does a flat overwrite per field (right for the checkbox/corridor preferences it was built for), which would silently drop every other device's token. Mirrors the backend's own `ArrayRemove` for a dead token (NF-P3-004).
7. **The "Enable notifications" control lives in `NotificationsForm.tsx` (Profile page), not on the Alert Feed page.** That's already the established home for every other notification-related setting (which alerts, which corridors) — adding a second, separate permission prompt on the feed page would split one concern across two places for no reason.
8. **`usePushSync()` is called once, from `AppShell`,** not from the alert feed page: a push can arrive while the person is on any page, and `AppShell` is the one component every signed-in, onboarded route already passes through (confirmed by `useAnalytics()` living in exactly the same file, called the same way).

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `tsc --noEmit`, `pnpm lint` (`--max-warnings 0`) | Clean |
| `pnpm exec prettier --write .` | Clean (3 files needed reformatting) |
| `pnpm exec vitest run src` | 124 passed, no regressions — this frontend still has no `.test.tsx` component-test convention; verification is the project's own Frontend DoD (live browser), same as NF-P3-008 |
| `pnpm build` | Clean; confirmed `firebase-messaging-sw.js` is excluded from the PWA precache manifest (34 entries, not 35) but still present as a plain static file in `dist/` |

**Live browser (Firestore emulator, a real signed-in test user, seeded notification docs)**
- Feed renders both a seeded unread alert (dot + highlighted border) and a seeded read one (plain) correctly, dates formatted per-locale
- Clicking the unread alert: navigated to its `deep_link` (`/radar/entity/example-remit`) **and** the Firestore write actually landed — reloading the feed showed it as read, no direct DB inspection needed to confirm
- "Alerts" button appears correctly on the heatmap page, next to "Report a problem"
- Mobile viewport (375×812): no horizontal overflow, confirmed via `scrollWidth === clientWidth`, not just a screenshot
- Hindi: page chrome (title, subtitle) renders translated; individual alert title/body stay in whatever language they were written in — correct, that's real per-notification content, not app-authored UI text
- Profile page's `PushStatus`: confirmed it renders **nothing** when push isn't configured (no `VITE_FIREBASE_VAPID_KEY`/`VITE_FIREBASE_MESSAGING_SENDER_ID` set) — the intended graceful no-op, not a bug. No `firebase-messaging-sw.js` network activity was attempted, confirming `isPushConfigured` gated correctly before touching the Notification API or the service worker at all.

**Not live-verified, and can't be without a real VAPID key from you:** requesting permission, receiving a real token, a real foreground toast, a real background push while the tab is closed.

## Manual test steps (once you have a real VAPID key)

bash / PowerShell (same commands):
```bash
# 1. Add both to frontend/.env.local (get the VAPID key from Firebase console → Project
#    settings → Cloud Messaging → Web Push certificates; the sender id is in the same
#    sdkconfig output .env.example already points to):
#      VITE_FIREBASE_MESSAGING_SENDER_ID=...
#      VITE_FIREBASE_VAPID_KEY=...

# 2. Run the app for real (not the emulator — FCM needs real Firebase project infra):
pnpm dev

# 3. Open /profile, find "Notifications", click "Turn on browser notifications", accept the
#    browser's permission prompt. Check the Firestore console: users/{uid}.fcm_tokens should
#    now have one entry.
# 4. Trigger a real alert (NF-P3-004's cron, or POST /api/v1/internal/aggregate-radar by
#    hand) against an account with that token. With the tab open and focused: expect a toast
#    ("You have a new alert" / View). With the tab backgrounded or closed: expect a system
#    notification; clicking it should open /radar/entity/<slug> or /radar/alerts.
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Turn on browser notifications" button never appears | Check both `VITE_FIREBASE_MESSAGING_SENDER_ID` and `VITE_FIREBASE_VAPID_KEY` are set — `isPushConfigured` requires both, by design |
| Permission granted but `getToken()` fails | Check `/firebase-messaging-sw.js` is reachable at the site root and registered — open DevTools → Application → Service Workers; a 404 there usually means a deploy didn't include `public/` correctly |
| A push notification's click doesn't open the right page | Check `payload.data.deep_link` was actually set by the backend (NF-P3-004's `notify.py`) — the service worker falls back to `/radar/alerts` when it's missing |
| The alert feed is empty but you know alerts exist | Check you're looking at the right uid's `users/{uid}/notifications` — this reads directly from Firestore with no backend involved, so there is no server-side "it didn't sync" failure mode, only "wrong account" or "genuinely empty" |

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind, matching existing conventions (shadcn-style cards, reused `Button`/`EmptyState`/`LoadingSpinner`); no new dependency (`firebase/messaging` is part of the already-installed `firebase` package)
- [x] Mobile responsive — verified live at 375×812, no overflow
- [ ] Slow network — not tested throttled
- [x] Loading states (`LoadingSpinner`, matching every other page's pattern)
- [x] Error states (load-error + retry) handled gracefully
- [x] i18n keys added for all user-facing strings, all 6 languages, verified live in Hindi
- [x] Screenshots — captured during live verification; available on request
- [x] Accessibility: unread state exposed via `aria-label` (not just a colored dot), keyboard-reachable feed items and buttons, `role="alert"` on the error state

## Commit and PR

Branch: `feature/radar-alert-feed` (already checked out).

```
feat(radar): add alert feed and fcm push registration
Refs: NF-P3-009
```

PR title: `feat: exploitation radar alert feed and push registration (NF-P3-009)`

## Noticed, not fixed

- No unread-count badge on the "Alerts" button/nav — the feed itself shows read/unread per item, which is what the task asked for; a badge is a natural follow-up, not built here to keep scope tight.
- No "mark all as read" action — fine at the expected per-user alert volume (a handful at a time, per NF-P3-004's own dedup design).
- Background push is code-complete but not live-verified (decision 1) — needs a real VAPID key, which only you can generate.
