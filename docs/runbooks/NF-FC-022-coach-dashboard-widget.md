# NF-FC-022 — Coach dashboard card, check-in sheet and push handler

## Summary

Three things a worker sees now, and the one thing the server needed so the third could work.

| Part | What it does |
|---|---|
| **The dashboard card** | The Coach's card on the signed-in home says **Start my interview**, **Continue my interview** (with the step, "Step 4 of 6", and when they last answered) or **View my plan** (with the score and its band), from `GET /api/v2/coach/overview`. A worker with a plan and an interview under way sees both, the interview first. While the overview loads, or if it cannot be read, the card is the plain pitch with a link to the Coach, so a failed read never takes the way in away |
| **The check-in sheet** | `/coach/checkin/:planId?m=30` (or 60, 90): the link the NF-FC-016 reminder carries. Three questions, one at a time, each a closed list of choices (nothing typed): did you send money home as in your plan, did you save as in your plan, is your employer paying in full and on time. Sent once at the end; a failure keeps the answers and sending again is one tap. The thank-you points to the plan when sending or saving is behind, and to the Radar report when pay is late, short or missing |
| **The push handler** | A push that arrives while the app is open shows a "Your Coach check-in is ready" toast whose **Answer** button opens the check-in (any other push is the Radar toast as before). A tap on a system notification opens the link: in a window that is already open (the worker posts the link and the app follows it) or in a new one. `coach_checkin` is a `NotificationType` now (D-232) |
| **The answers route** (backend) | `PUT /api/v2/coach/plans/{id}/checkins/{milestone}` stores the three choices on the plan, **once per milestone** (the first answers are kept, a second call changes nothing and gets them back). Open from the milestone's day. This was D-233: no tracker row owned it, and Devam chose to build it inside this task |

The reminder job (NF-FC-016) is not changed.

## Files

**Backend** (one commit, can be a PR of its own)

| File | Change |
|---|---|
| `backend/app/api/v2/coach_checkins.py` (new), `router.py` | The route, flag-guarded like every coach route; registered in the v2 router |
| `backend/app/services/coach/checkin_answers.py` (new) | The rules: plan exists, milestone is due (UTC date), store once. No model call |
| `backend/app/repositories/coach_session_repo.py` | `CoachPlanRepository.checkin_state` (reads two fields, not the whole plan) and `answer_checkin` (a transaction, written by field path so the reminder's `due_on` and `notified_at` stay) |
| `backend/app/schemas/coach_checkin.py` | `CheckinAnswers`, `CheckinAnswerRequest`, `CheckinAnswerResponse` |
| `backend/tests/unit/services/test_coach_checkin_answers.py`, `tests/integration/api/test_coach_checkin_answers.py`, `tests/integration/repositories/test_coach_checkin_answers.py` (new), `tests/fixtures/coach_checkins.py` | 12 service tests, 9 API tests, 6 emulator tests; the fake plan store learns the two methods |
| `docs/mocks/coach/checkin-*.json` (4, new), `backend/tests/unit/test_coach_mocks.py`, `tests/fixtures/coach_mocks.py` | The samples, and the drift test that holds them to the models |

**Frontend**

| File | Change |
|---|---|
| `components/dashboard/CoachWidget.tsx`, `utils/coachCardState.ts` (new), `pages/Dashboard.tsx` | The card and the rule that picks its state; the dashboard uses it for the `coach` module |
| `components/coach/checkin/CheckinSheet.tsx`, `CheckinDone.tsx`, `pages/coach/CoachCheckinPage.tsx`, `CoachCheckinRoute.tsx` (new), `router.tsx` | The sheet, the page, and the flag-guarded lazy route (own chunk of 6.6 kB) |
| `types/coachCheckin.ts`, `services/coachCheckinService.ts`, `hooks/useCoachCheckin.ts`, `utils/coachCheckin.ts` (new) | Types, the `PUT`, the mutation (marks the reminder read in the feed), the questions and the error words |
| `utils/appLinks.ts` (new), `lib/messaging.ts`, `hooks/useNotifications.ts`, `types/notification.ts` | `safeAppPath`, the foreground toast with the push's link, the tap listener, `coach_checkin` |
| `public/firebase-messaging-sw.js` | The tap handler (see "The push worker" below) |
| `lib/analytics.ts` | `/coach/checkin/:planId` is reported without the plan id |
| `hooks/useCoachPlan.ts` | `useCoachOverview` reads again when the dashboard mounts (`refetchOnMount: "always"`) |
| `i18n/<lang>.json` and `i18n/coach/<lang>.json` (12) | The card and the toast (shared strings), the sheet (the Coach's) |
| tests (14 files) | Listed under Results |

**Docs:** `docs/api/v2-coach.md` (the route, the error code, open point 4 resolved), `docs/data-model/collections/coach.md` (the answers), `docs/mocks/README.md`, `docs/mermaid/financial-coach-pipeline.mmd`, `docs/runbooks/NF-FC-016-coach-checkin-reminders.md` (one line), `docs/deferred-items.md`, and this file.

**No shared file was touched** (`package.json`, lockfile, `firebase.json`, rules, `tsconfig*`, workflows).

## Choices that were not in the task text

| # | Choice | Why |
|---|---|---|
| 1 | **The three questions** (money sent home, saving, pay in full and on time), each a fixed choice | D-233 left them undecided. Devam accepted this set on 2026-10-09. Fixed choices store nothing a worker typed (no guardrail work, nothing sensitive) and translate cleanly. The pay question is the one that matters most: it is the signal Exploitation Radar exists for |
| 2 | **The backend route was built here**, not as its own task | D-233 said a backend task should come first; none existed. Devam chose to add it. It is its own commit |
| 3 | **A routed page styled as a sheet, not a modal** | The repo has no dialog component; Radix Dialog means editing `package.json` and the lockfile (shared files). A deep link lands on a route anyway |
| 4 | **First answers win** | A check-in records how it was on that day; and it makes a retry, a second tap and a second phone harmless without a key |
| 5 | **Open from the milestone's day** (UTC date) | The job reminds at 02:00 UTC on that date, so a worker with the link has always reached it; it stops a call from answering day 90 on day 5 |
| 6 | **Untouched session = Start** | Opening the Coach page creates a session; "Continue" for a worker who answered nothing would be wrong |
| 7 | **The card's strings are the shared ones** | The dashboard must not download the whole Coach namespace for one card. The three band names exist twice for it (D-249) |
| 8 | **The mark-as-read of the reminder is not awaited** | Firestore holds a write until the server has it; the thank-you must not wait for it. Found while planning the browser check |
| 9 | **The check-in's error words** are its own, with the shared `errors.*` for connection and server problems | The chat's ("the coach is busy", "your last message") are wrong here |

### The push worker (read this one)

`firebase-messaging-sw.js` is shared with Radar's alerts. Reading `@firebase/messaging` (0.13.3, `index.sw.esm.js`) showed that, with the app in the background and a push that carries a `notification` (ours does), **the library shows the notification itself** (`onPush`), and the old worker then showed **a second one** from `onBackgroundMessage`. The library's copy has no link, so its click handler (`onNotificationClick`) closes it and opens nothing, and it stops every handler registered after it. So the old behaviour was two notifications, one of them dead. The worker now (1) registers its own click handler **before** `firebase.messaging()` creates the library's, (2) handles both kinds (its own copy: `data.deep_link`; the library's: `data.FCM_MSG.data.deep_link`), (3) shows a push itself only when it has no `notification`, (4) opens the link only if it is a path inside the app, and (5) focuses a window that is already open and posts it the link, because the push worker does not control the app's window and cannot navigate it. All of this is tested in Node against stand-ins; the real library calling the hooks was **read, not run** (D-246).

## Configs checked, nothing to change

| Config | Result |
|---|---|
| `frontend/firebase.json` (hosting) | The `**` rewrite serves `/coach/checkin/...` as the app; `firebase-messaging-sw.js` is a static file and `no-cache` applies, so a new worker is fetched. No change |
| `frontend/firestore.rules` | A worker can read their `coach_plans` and update only `read` and `read_at` of a notification: the sheet's mark-as-read is allowed, and the answers must go through the API (no client write to `coach_plans`) |
| `frontend/firestore.indexes.json` | The `coach_plans.departure_date` group index (NF-FC-016) is the only one the feature needs. The new route reads one document by id: no index |
| `frontend/.env.example` | `VITE_FIREBASE_MESSAGING_SENDER_ID` and `VITE_FIREBASE_VAPID_KEY` are already there; push is off when unset, and the card and sheet do not need them |
| `frontend/vite.config.ts` | `firebase-messaging-sw.js` is already out of the precache, so the new worker is always fetched fresh |
| `infra/cloud-scheduler/coach-checkins.yaml` | The daily job is as NF-FC-016 left it (D-231 still open: nobody has seen it run in production) |
| `lib/analytics.ts` | **Changed**: the plan id in the check-in link no longer reaches Google Analytics (a test scans the router for `:param` routes and failed until it was listed) |
| Backend rate limit | The API-wide 60 a minute applies (middleware); the route needs no Gemini budget |

## Results

| Check | Result |
|---|---|
| Backend `black --check`, `ruff`, `mypy app` (238 files), `mypy --strict app/services` (105) | Clean |
| Backend tests, new | 12 service, 9 API, 1 mock agreement in the drift suite (which now has 95; the three files together are 116) |
| Backend `tests/unit` and `tests/integration/api` | 3,424 passed, 95 skipped, **2 failed, neither this task's**: `test_scam_history` (flaky, passed 2 of 3 runs of the same file) and `test_coach_question_bank::test_the_file_is_utf8_json_with_a_final_newline` (the file is CRLF on this checkout). Both logged, D-248 |
| Emulator: `tests/integration/repositories/test_coach_checkin_answers.py` + `test_coach_checkins.py` | **13 passed** (6 new, 7 NF-FC-016's). The concurrency test tolerates the emulator's lock timeout, which the route answers as `409 request_in_progress` |
| Frontend `eslint --max-warnings 0` | Clean |
| Frontend `tsc -b` | Clean apart from the 4 errors in `src/mocks/axe.ts` (`axe-core` is not installed here) |
| Frontend `check-i18n` | OK, 6 languages, 1,253 English keys |
| Frontend `vitest` (125 files) | **1,317 tests passed; 5 files fail to load** (`axe-core` missing, all of them import `src/mocks/axe.ts`, none touched by this task, D-248). The 13 test files of this task: **183 tests passed** |
| `prettier` on this task's files only | Clean (`--end-of-line crlf` for the existing ones) |
| `vite build` | Builds. `CoachCheckinPage` and `CoachCheckinRoute` are their own chunks (6.6 kB and 0.8 kB); the main chunk holds none of the sheet's strings |
| Browser pane, 360 × 740 (a throwaway page with the API and the signed-in user stubbed, deleted afterwards) | The card in 5 states; the sheet through all 3 questions and the thank-you; the request the sheet sent (`{"answers":{"remittance":"on_track","savings":"behind","pay":"not_paid"}}` to `.../checkins/d30`); Hindi, with the not-open-yet error and the answers kept; no sideways scroll (scrollWidth = 360) |

Frontend tests of this task (110 in 11 files): `CoachWidget.msw` (9), `CheckinSheet.msw` (10), `CoachCheckinPage.msw` (7), `CoachCheckinRoute` (2), `coachCardState` (12), `coachCheckin` (21), `appLinks` (15), `usePushSync` (7), `messaging` (9), `firebaseMessagingSw` (14), `Dashboard.flags` (4, one new); and added cases in `analytics.test.ts` (the two coach routes, `/coach`) and `coach.msw.test.ts` (2, the check-in mocks).

**Not verified**

- **A real push on a real device** (D-246). The browser pane cannot receive one. This is the one that decides whether "tapping a reminder push opens the check-in sheet" holds on a phone.
- **The answers route against real Firestore in production**; only the emulator was used.
- **Slow 3G** (the Frontend DoD asks for it): the browser pane has no throttle. The new code is 7 kB and one `PUT`; the card shows the plain pitch while the overview loads.
- **Axe** on the new screens (not installed here); the full pass is NF-FC-023. Keyboard and structure were checked by hand: real radio inputs in a `fieldset` with a `legend`, focus moves to the next question, the thank-you is a `role="status"`, the error a `role="alert"`.
- **The wording** in hi, tl, id, ne and bn (D-245).

## Manual test

**1. Tests (no emulator).** From `backend/`:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/services/test_coach_checkin_answers.py tests/integration/api/test_coach_checkin_answers.py tests/unit/test_coach_mocks.py -q
```

```bash
.venv/Scripts/python.exe -m pytest tests/unit/services/test_coach_checkin_answers.py tests/integration/api/test_coach_checkin_answers.py tests/unit/test_coach_mocks.py -q
```

Expect `116 passed`. From `frontend/`:

```bash
npx vitest run src/components/dashboard/CoachWidget.msw.test.tsx src/components/coach/checkin src/pages/coach/CoachCheckinPage.msw.test.tsx src/pages/coach/CoachCheckinRoute.test.tsx src/hooks/usePushSync.test.tsx src/lib/messaging.test.ts src/lib/firebaseMessagingSw.test.ts src/utils/coachCardState.test.ts src/utils/coachCheckin.test.ts src/utils/appLinks.test.ts
```

**2. The route against the Firestore emulator.** From `frontend/` (the script runs through `cmd`, so Windows paths):

```powershell
firebase emulators:exec --only firestore --project demo-nomadfinance "cd ..\backend && .venv\Scripts\python.exe -m pytest tests/integration/repositories/test_coach_checkin_answers.py -v"
```

```bash
firebase emulators:exec --only firestore --project demo-nomadfinance "cd ..\\backend && .venv\\Scripts\\python.exe -m pytest tests/integration/repositories/test_coach_checkin_answers.py -v"
```

Expect `6 passed`. On Windows the emulator's `java.exe` keeps running afterwards and holds port 8085 (D-235 point 7): stop it before the next run, `Get-NetTCPConnection -LocalPort 8085 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess }` (PowerShell).

**3. The whole thing in the browser.** Set up as in NF-FC-021 ("Locally": the emulators, the API with the `coach` variables, `frontend-emulator`), seed a worker, turn the `coach` flag on for them (`config/feature_flags.flags.coach.enabled`), and store a plan for them whose `departure_date` is 30 or more days ago (a plan document with `departure_date: "YYYY-MM-DD"`).

1. **The card.** Open `/dashboard` at 360 px. With no session and no plan the Coach card says **Start my interview**. Open the Coach, answer one question, go back: **Continue my interview, Step N of 6**. With the plan stored: **View my plan**, the score and band; with both, both links.
2. **The sheet.** Open `/coach/checkin/<planId>?m=30`. Answer the three questions; **Send my answers**. Expect "Thank you". In the Firestore emulator UI (`http://127.0.0.1:4000/firestore`) the plan has `checkins.d30.answers` and `answered_at`. Open the link again and answer differently: the thank-you says "You already answered this check-in" and the stored answers are the first ones.
3. **Not open yet.** Open `?m=90` for a plan that is 30 days in: after the three questions the sheet says "This check-in is not open yet" and keeps the answers.
4. **A link that is not complete** (`?m=45`, or no `m`): "This check-in link is not complete" and a link to the Coach. With the flag off for the worker, any `/coach/checkin/...` goes to the dashboard.
5. **The feed.** If the plan's reminder notification exists (`users/{uid}/notifications/coach_checkin_{planId}_d30`, written by the NF-FC-016 job), it is marked read after sending.
6. **A push** (D-246): see that item; it needs a real phone and a real token.

## Definition of Done (Frontend feature, and Backend endpoint for the route)

- [x] Component built with Tailwind and the existing shadcn `Button`
- [x] Fully mobile responsive (checked at 360 × 740 in the browser pane; no sideways scroll)
- [ ] Works on slow network (throttled 3G): not run, no throttle in the browser pane
- [x] Loading, error and empty states: the card (loading and failed read: the plain pitch with a way in; empty: Start), the sheet (sending, every failure with its words, a link that is not complete)
- [x] i18n keys for every string, 6 languages, `check-i18n` green
- [ ] Screenshots added to the PR: take them from step 3 above (the browser-pane screenshots were not saved into the repo)
- [x] Accessibility by hand (keyboard, semantic HTML, focus, live regions); [ ] axe not run here (D-248), full pass is NF-FC-023
- [x] Endpoint with Pydantic models, token check (via the coach router), specific status codes, rate limit (API-wide)
- [x] Manual test of the route against the emulator, and tests at every level
- [x] API contract updated (`docs/api/v2-coach.md`), data model updated (`coach.md`), mocks and the drift test updated
- [x] Strict types, lint and format clean; tests added for every part; no shared file touched
- [ ] Real push on a real phone (D-246); wording read by native speakers (D-245)
- [ ] Reviewed by a teammate (Devam reviews; Pranjal owns the task)

## Commit

Branch: `feature/NF-FC-022-coach-dashboard-widget` (already checked out).

The change is larger than the 400-line guideline (about 900 changed lines and about 2,700 new, more than half of them tests, plus 12 translation files). It splits cleanly into three commits, in this order:

```bash
# 1. backend/, docs/api/v2-coach.md, docs/data-model/collections/coach.md, docs/mocks/, docs/mermaid/, docs/runbooks/NF-FC-016-...
git commit -m "feat(coach): add check-in answers route for day 30, 60 and 90" -m "Refs: NF-FC-022"

# 2. frontend/public/firebase-messaging-sw.js, src/lib/messaging*.ts, src/hooks/useNotifications.ts, src/hooks/usePushSync.test.tsx, src/types/notification.ts, src/utils/appLinks*.ts, src/lib/firebaseMessagingSw.test.ts
git commit -m "feat(push): open Coach check-in links from push notifications" -m "Refs: NF-FC-022"

# 3. everything else under frontend/, docs/runbooks/NF-FC-022-..., docs/deferred-items.md
git commit -m "feat(coach): add dashboard card and check-in sheet" -m "Refs: NF-FC-022"
```

Or as one commit: `feat(coach): add dashboard card, check-in sheet and answers route` with `Refs: NF-FC-022`.

PR title: `feat(coach): dashboard card, check-in sheet and push handler (NF-FC-022)`

PR description:

```
The Coach card on the home dashboard now says Start, Continue or View plan from
GET /api/v2/coach/overview. A tap on a day 30/60/90 reminder opens a three-question
check-in at /coach/checkin/:planId?m=30, and the answers are stored on the plan.

Why the backend route is here: the check-in had nowhere to send answers (D-233) and
no task owned it, so it is built in this PR as its own commit:
PUT /api/v2/coach/plans/{id}/checkins/{d30|d60|d90}. The first answers are kept, the
milestone is open from its day, and the contract, data model and mocks are updated.

The three questions are fixed choices (money sent home, saving, pay in full and on
time), so nothing a worker types is stored.

Push: a push with a notification payload was shown twice in the background (the
Firebase library's copy, which cannot be tapped, and the worker's own). The worker
now registers its tap handler first, shows only pushes the library does not, and
opens the link in an open window or a new one. This also affects Radar alerts.

Not done / to check: a real push on a real phone (D-246), native-speaker review of
the new wording (D-245), axe (not installed locally), slow 3G.

Checks: black, ruff, mypy, eslint, tsc, prettier, check-i18n clean; 13 emulator
tests; 183 new and changed frontend tests. Five frontend suites cannot load here
because axe-core is not installed (D-248); two backend tests fail here for reasons
unrelated to this change (D-248).

Refs: NF-FC-022
```

Not marked Done in the tracker; the owner does that after the merge.
