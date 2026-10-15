# Regression suite C (Pranjal) — Exploitation Radar, Remittance → Coach handoff, PWA install / offline / push

Task NF-HR-006, run 2026-10-13 on `fix/regression-suite-c`. This is the test sheet and the bug log. The task document is `docs/runbooks/NF-HR-006-regression-pranjal-suite.md`.

**Verdict.** One P1 found and fixed (signing out left the browser's push token on the worker's profile, so on a shared phone the last worker's alerts and Coach reminders kept arriving for the next person). Two P2/P3 found and fixed with tests (a double tap stored two Radar reports; a business name of only symbols was accepted and then lost). Three P2 filed with a recommended fix (concurrent reports lose count updates, a transfer is dated by the UTC day, a cold open offline shows nothing but "could not load your profile"). No P0. After this branch merges there are **no open P0 or P1** from this suite. Nothing was run against production, a real phone, or a real push service (see "Not covered").

## How it was run

| Part | What |
|---|---|
| Stack | Firebase Auth, Firestore and **Storage** emulators; the **real API** (`create_app()`, real routes, services, repositories, middleware, rate limiter); the **real frontend** (dev server for most Radar runs, a production build served by `vite preview` for every cross-browser, PWA and push run) |
| Gemini | **A stand-in**, so runs repeat and cost no quota. For Radar it answers the three report steps (who, spam / abuse / personal data, violation type) by simple rules on the text, and the alert text. What the model *says* is not tested here |
| Data | The Radar demo seed (18 reports, 8 businesses, 6 routes) and 14 seeded workers (each SG→IN with a finished Coach plan, six logged transfers and five scam checks) |
| Engines | Chromium, Firefox and WebKit, each as a desktop window (1280×800) and as a phone (Chromium: Pixel 5; WebKit: iPhone 13; Firefox has no mobile emulation, so its "phone" is a 393×727 window) |
| Push | The app's own code, the Firebase library and the app's own push service worker are real, loaded in Chromium. Google's two token servers are answered by a stand-in, and a push is delivered to the worker through the browser's debugging interface. **A device token cannot be had** in Playwright's Chromium (see P-32) |
| Production | Not touched |

## Baseline and after

| Suite | Result |
|---|---|
| Backend unit, after | **3,236 passed**, 1 skipped (3 new cases in `test_radar_intake.py`) |
| Backend integration, Radar (`-k radar`, emulators) | **40 passed** |
| Frontend unit, after | 147 files, **1,699 passed** (new: `RadarReport.send.test.tsx`; cases added to `authService.signOut.test.ts` and `lib/messaging.test.ts`) |
| Frontend end-to-end, default projects, after | **246 passed** (22 new in `e2e/radar.spec.ts`, 12 in `e2e/pwa.spec.ts`; 212 before) |
| Frontend end-to-end, opt-in `firefox` and `webkit-iphone`, Radar and PWA specs | **31 passed**, 3 skipped on iPhone by design (iOS shows the Share steps, not a dialog) |

## Test sheet

`P` = passed, `F` = failed (bug in the notes), `N` = not run (reason in the notes). Columns are Chromium desktop and phone (C, C📱), Firefox (F, F📱), WebKit (W, W📱); each shows the final run, after the fixes, and a bug id says where a case failed before one. "Auto" cases are in the repo and run in CI.

### Exploitation Radar (scripted RD-01…RD-31)

| ID | Case | C | C📱 | F | F📱 | W | W📱 | Notes |
|---|---|---|---|---|---|---|---|---|
| RD-01 | Heatmap opens with the title, filter and the six routes with their counts | P | P | P | P | P | P | Auto |
| RD-02 | Filter by type narrows the routes; "All types" brings them back | P | P | P | P | P | P | |
| RD-03 | A route opens its businesses; a business opens its profile | P | P | P | P | P | P | Auto |
| RD-04 | Profile: risk, rating, reports with their source, back to the map | P | P | P | P | P | P | |
| RD-05 | An unknown business says so and leaves a way back | P | P | P | P | P | P | Auto |
| RD-06 | The report list holds no reporter and no model scores | P | P | P | P | P | P | |
| RD-07 | Each step asks for its answer with a message | P | P | P | P | P | P | Auto. The route is pre-filled from the profile, so "Choose where it happened" appears only after clearing it |
| RD-08 | A report goes through; confirmation shows type and summary; one report stored | P | P | P | P | P | P | |
| RD-09 | Two quick taps on Send report store one report | P | P | P | P | P | P | **QA-C-01**. Stored 2 before the fix. Auto |
| RD-10 | Spam is refused with its words, nothing stored | P | P | P | P | P | P | |
| RD-11 | Threats are refused, nothing stored | P | P | P | P | P | P | |
| RD-12 | A phone number is refused, nothing stored | P | P | P | P | P | P | |
| RD-13 | AI busy (503) and slow (504): plain words, what was written is kept | P | P | P | P | P | P | Auto |
| RD-14 | An employer report asks for the country, not the route | P | P | P | P | P | P | |
| RD-15 | Evidence: a PNG attaches and counts; a text file and an 11 MB file are refused | P | P | P | P | P | P | Needs the Storage emulator: without it "Files that could not be attached" is the (correct) answer |
| RD-16 | Alerts page: route section, feed and a link to choose routes | P | P | P | P | P | P | |
| RD-17 | No sideways scroll on the four Radar pages | P | P | P | P | P | P | Auto |
| RD-18 | No uncaught page errors during the run | P | P | P | P | P | P | |
| RD-19 | The four pages in `hi`, `tl`, `id`, `ne`, `bn`: no raw key, no overflow, `lang` set | P | P | P | P | P | P | |
| RD-20 | An alert on the worker's route shows business, count, severity and route | P | — | — | — | — | — | |
| RD-21 | Dashboard counts unread alerts; opening one marks it read and the count drops | P | — | — | — | — | — | |
| RD-22 | A read row stays read after a reload | P | — | — | — | — | — | |
| RD-30 | A business reported twice is flagged on Remittance, and the advice names the next one | P | — | — | — | — | — | Wise reported twice → "Community flagged"; advice names InstaReM |
| RD-31 | That business's Radar page lists the reports and says it is flagged | P | — | — | — | — | — | |

Also run: the alert job, with the stand-in for the notification text, creates the alerts once (5 alerts and 14 notifications; then 1 for reports filed in between) and, run again with no new reports, creates **none**.

### API and data (scripted A-D, A-E, A-L, A-C: 37 checks)

| Group | Result |
|---|---|
| Report: no body, `{}`, description 9 or 2,001 characters, name 201 characters, unknown corridor, a UAE corridor and host country, language `xx`, `scam_type` as entity type, non-text description, invalid JSON, `text/plain` | 422 each, never 5xx |
| Report: no token, a junk token | 401 |
| Report: a `violation_type` sent by the caller | Ignored; classified fresh (A-D13b) |
| Report: markup and an instruction in the description | Stored as text / still a valid classification |
| Evidence: another worker's report | 403; no such report 404; id of the wrong shape 422; empty file 400; a text file 415; 11 MB 413; a sixth file 422; no token 401 |
| Entity reports: unknown slug | 200 with an empty list; a bad slug 422; no token 401; another worker reads them: no reporter, no scores |
| Six reports at once about one business | All stored (201) but the business's `report_count` is **2**: **QA-C-02** |
| Business names: Devanagari, Bengali, Nepali, Arabic, Chinese, `24/7`, `&`, apostrophe, markup, one letter | Stored |
| Business names of only symbols or emoji (`???`, `💸💸💸`) | Stored with an empty slug and no profile before the fix: **QA-C-06**; now 422 |

### Remittance → Coach handoff (HO-01…HO-08; C, C📱, F, W📱)

| ID | Case | C | C📱 | F | W📱 | Notes |
|---|---|---|---|---|---|---|
| HO-01 | The plan's sending card names a monthly amount, a service, and links to Remittance with both | P | P | P | P | |
| HO-02 | The link opens Remittance with corridor and amount filled and compares once | P | P | P | P | |
| HO-03 | The plan's "cheapest service" is the top-ranked, unflagged service on the Remittance screen for that amount | P | P | P | P | InstaReM, both |
| HO-04 | "What we already know" offers the monthly amount worked out from the last 90 days of logged transfers | P | P | P | P | 400 SGD, as of the newest transfer's date; recomputed independently from Firestore |
| HO-05 | A transfer logged in Remittance is stored once, with the comparison's amount | P | P | P | P | See QA-C-03 for its date |
| HO-06 | The interview that is already open keeps the answers it was offered | P | P | P | P | |
| HO-07 | A new interview offers the average that includes the new transfer | P | P | P | P | 400 → 644.33 SGD for one more of 733 |
| HO-08 | The finished plan is still there after a new interview starts | P | P | P | P | |

Not walked through the screens: a plan made *by the live interview* writing `goals` into Financial Identity (the seeded plans were not made by the service). That path is covered by `test_plan_goals.py` and `test_cross_pillar_regression.py`.

### PWA install, offline and push

| ID | Case | C | C📱 | F | F📱 | W | W📱 | Notes |
|---|---|---|---|---|---|---|---|---|
| P-01 | Manifest: name, standalone, scope, start URL, colours, three icons that exist at their size, one maskable | P | P | P | P | P | P | Auto (Chromium) |
| P-02 | `index.html` links the manifest and carries the iOS and theme tags | P | P | P | P | P | P | |
| P-03 | The worker registers and activates; the app shell is cached; it controls the next load | P | P | P | P | N | N | WebKit: activates, but Playwright's WebKit never reports a controlling worker, so not checked there |
| P-04 | Offline, a signed-in page opens the app and says what failed | P | P | P | P | N | N | WebKit: Playwright cannot navigate while offline. Firefox takes 6.7 s to say it (Chromium 1.6 s) |
| P-04b | Offline cold open: what the worker sees | P | P | P | P | N | N | **QA-C-04**: "We couldn't load your profile" on every signed-in page |
| P-04c | Back online, "Try again" opens the page without a reload | — | P | P | P | N | N | |
| P-05 | A page that is open when the signal goes: plain "No internet connection" | P | P | P | P | P | P | Auto |
| P-06 | Back online, the same action works without a reload | P | P | P | P | P | P | |
| P-07 | A message shared into the app (`/scam-check?text=`) fills the box and sends nothing | P | P | P | P | P | P | |
| P-10 | The install event shows the offer after a few seconds, with an Install button | P | P | P | P | P | N | Auto. iPhone: iOS shows Share steps (P-16) |
| P-11 | Install opens the browser's dialog once; the offer goes; nothing remembered on "accepted" | P | P | P | P | P | N | Auto |
| P-12 | Closing the offer hides it two weeks, also after a reload; it returns after 14 days | P | P | P | P | P | N | Auto |
| P-13 | "Dismissed" in the browser's dialog is remembered | P | P | P | P | P | N | Auto |
| P-14 | The installed event removes the offer | P | P | P | P | P | N | Auto |
| P-15 | A signed-out visitor on the landing page gets the offer | P | P | P | P | P | N | |
| P-16 | iPhone Safari: Share steps, no Install button | P | P | P | P | P | P | Auto |
| P-17 | iPhone, already on the home screen: no offer | P | P | P | P | P | P | |
| P-18 | Instagram's in-app browser on iPhone: no offer | P | P | P | P | P | P | |
| P-19 | Chrome on iPhone (`CriOS`): Share steps | P | P | P | P | P | P | |
| P-20 | The offer is in Hindi when the app is in Hindi | P | P | P | P | P | N | |
| P-30 | Notifications blocked in the browser: how to unblock, no button | P | P | — | — | — | — | |
| P-31 | Not asked yet, the prompt is closed: "not turned on", no token | P | P | — | — | — | — | |
| P-31b | The worker blocks it: the page says so | P | P | — | — | — | — | |
| P-32 | The worker says yes but the browser's push service refuses | P | P | — | — | — | — | Playwright's Chromium cannot subscribe ("Registration failed - permission denied"): a plain note, no token, no crash. The token path itself is covered by `lib/messaging.test.ts` |
| P-34 | The push worker registers on its own scope and activates (the Firebase library loads) | P | P | — | — | — | — | |
| P-35 | A push while the app is open and visible: a toast, and "View" opens the alerts | P | P | — | — | — | — | |
| P-36 | A Coach check-in push while open: its own toast; the action opens that check-in | P | P | — | — | — | — | |
| P-37 | A push whose link leaves the app (`https://…`, `//…`, `javascript:`): the worker stays in the app | P | P | — | — | — | — | |
| P-38 | No open app window: the push becomes a system notification carrying its link | N | N | — | — | — | — | The worker's own permission reads "denied" in this headless browser |
| P-39 | A tap on a system notification: the app's handler opens an in-app path and replaces an off-site one | P | P | — | — | — | — | Run with the real worker code and stand-in window calls; a real tap cannot be made headless |
| P-40 | No uncaught page errors during the run | P | P | — | — | — | — | |

## Bugs

Severity: **P0** blocker (a main path is broken, data is lost or exposed, a wrong money or legal answer is shown with no sign), **P1** major (a feature's main path fails for a real group of workers, or one worker's data reaches another), **P2** minor, **P3** cosmetic or rare. Filed in this file; no GitHub issues were created.

| ID | Sev | Where | What | Repro | Status |
|---|---|---|---|---|---|
| **QA-C-05** | **P1** | Sign-out, push | Signing out never released the browser's push token: it stayed in `fcm_tokens` on the worker's profile and with FCM. Phones are shared (the app's own sign-out comments say so), so the last worker's Radar alerts and Coach check-in reminders kept arriving on that browser for whoever signed in next. If the next worker turns push on in the same browser, the browser's one token would end up on two profiles | Worker A turns browser notifications on (profile → Notifications), signs out; any alert for A's route is pushed to that browser; B signs in there and receives it. Found by reading the code (no `deleteToken`, no removal anywhere); not reproduced with a real push (D-327) | **Fixed**: `signOut` releases the token at FCM (`releasePushToken`), removes it from `fcm_tokens` (`removeFcmToken`) and only then signs out, best effort and never more than 3 s. Tests: 6 unit (sign-out) and 3 (`lib/messaging`) |
| QA-C-01 | P2 | Radar report | Two taps on **Send report** in the same instant stored two reports: `pending` only updates after a render, and the second tap passed it. A duplicate counts twice towards a business's report count and flag | Double-tap Send report on the last step | **Fixed**: the page holds the form for the length of the call and lets go when it ends, so a failed send can be tried again. Tests: 2 unit, 1 browser |
| QA-C-06 | P3 | Radar report | A business name with no letters or digits (`???`, an emoji) was accepted with a thank-you, stored with an empty slug, and never reached a business profile (the profile write failed in the log: `radar_entity_update_failed slug=`) | Report a business called `???` | **Fixed**: the API refuses it (422 "Could not tell who this report is about. Add a business name."). Tests: 3 unit |
| QA-C-02 | P2 | Radar aggregation | Reports about one business that land at the same instant lose count updates: the profile is read, changed and written back without a transaction (the code says so). Six at once left `report_count` at 2 although all six are stored; the next report repairs it. The alert job reads the reports themselves, so alerts are not affected | Post six reports about one new business in parallel; read `radar_entities/{slug}.report_count` | **Filed** (D-328) with the fix: do it in a transaction, or use an increment |
| QA-C-03 | P2 | Remittance → Financial Identity | "I used this" stores the transfer under the **UTC** day (the app sends no `entry_date`). For a worker in Singapore (UTC+8) that is yesterday from midnight to 08:00 local time; in Sydney (UTC+11) before 11:00; on the 1st it lands in the previous month, which moves the Coach's "money you send in a month" and the identity timeline. The income, bill and savings forms default their date the same way (`new Date().toISOString()`) | Log a transfer at 07:00 in Singapore; open its date in Financial Identity | **Filed** (D-329). Not a one-line fix: sending the local date is right, but the Coach's 90-day window ends "today UTC", so a transfer dated today locally would be left out for hours. Both sides together |
| QA-C-04 | P2 | PWA, offline | A signed-in worker who opens the app with no signal sees the shell, then on **every** page "We couldn't load your profile" with Try again: the profile is read from the network before any signed-in page can show, and Firestore keeps no copy on the phone. The install offer says "it opens faster and works offline"; that is true of the shell and of the Coach answer queue for a session already open, not of opening the app on a bus | Install or visit once, go offline, open `/dashboard` | **Filed** (D-330) as a decision: keep a local copy of the profile (persistent Firestore cache), or reword the offer. Neither is a regression-task change |

## Not covered

- **Real phones and real push.** No iPhone, no Android phone, no real FCM message. WebKit with an iPhone 13 profile stands in for Safari on iOS; Chromium with a Pixel 5 profile for Chrome on Android. The sign-out fix (QA-C-05) is proved by unit tests against stand-ins, not by a real token being deleted (D-327).
- **What the model writes.** The stand-in answers for it: whether the real model screens, names and classifies a Radar report well, and the alert text in each language, are for the live evals.
- **The contract report's flagged parties** (NF-P3-023) were not walked in this run; NF-HR-004 covered the report itself.
- **Screens in the five other languages beyond the four Radar pages**: the report confirmation and the Coach in each language belong to NF-HR-004.
- **The app update toast** ("A new version is ready" with Refresh): needs two builds; unit-tested only.
- **A signed-in production run** (D-274), and the real Cloud Run service.

## Checks

See the task document: it carries the results of the chains run for this branch.
