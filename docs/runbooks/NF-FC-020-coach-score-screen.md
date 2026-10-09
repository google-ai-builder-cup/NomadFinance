# NF-FC-020 — Coach preparedness score screen (and the review step it needed)

## Summary

When a worker has confirmed their answers, the Coach now shows their **preparedness score**: a ring with the total, the band in words, one card for each of the five factors with what it means and how to improve it, and the button that makes the 90-day plan.

It needed one thing that did not exist: **nothing moved a session from `review` to `plan`**. `confirm_review` and `request_correction` (NF-FC-008) were never called, and the turn endpoint read no answer at the review, so "Yes, that is right" changed nothing and no worker could ever reach the score. That is fixed here, in the backend, first.

| Part | What it does |
|---|---|
| **Review step (backend)** | The worker's reply at `review` goes to the usual turn route. One fast-tier call (`coach/review.v1`) reads it into *confirm*, *change* (and which answer) or *other*; code decides what moves. A sure yes goes to `plan`; a change that names an answer goes back to its question; "I want to change something" makes the coach ask which; anything else changes nothing |
| **Score screen (frontend)** | Shown at stage `plan`, in place of the small "answers are in" box. Reads `GET /sessions/{id}` (the score is there, not in the stream). The ring has a text alternative ("Preparedness score: 57 out of 100, Getting ready") and the band is always written, so colour is never alone. A score that cannot be worked out right now (`null`) is told in words with a Try again button |
| **Plan button** | `POST /sessions/{id}/plan`; a progress line ("up to a minute", then "still working"); failures in words (not confirmed, still being made, busy, timeout, a missing rate) with Try again; success shows the plan's summary. Pressing again returns the same plan |

## Files

| File | Change |
|---|---|
| `backend/app/schemas/coach_review.py`, `app/prompts/coach/review.v1.yaml`, `app/services/coach/review_reader.py` (new) | The model's reading, its prompt, and the checks (`decide`: quoted words in the message, 0.85 to confirm) |
| `backend/app/services/coach/session_review.py` (new), `session_service.py`, `turn_types.py`, `turn_prompt.py`, `turn_service.py`, `slot_extractor.py` | The move applied inside the turn's own write; the reply is told the plan stage or asked to ask which; the extractor calls the reader at `review` |
| `frontend/src/types/coach.ts`, `services/coachService.ts`, `utils/coachScore.ts`, `utils/coachErrors.ts` | The full score type, `getCoachSession`, `createCoachPlan` (90 s allowance, `504 ai_timeout`), levels and bands, plan errors |
| `frontend/src/hooks/useCoachScore.ts`, `useMakeCoachPlan.ts` | The two calls |
| `frontend/src/components/coach/score/` (new), `CoachChat.tsx` | `ScoreScreen`, `ScoreGauge` (Recharts), `FactorBars`, `PlanButton`; wired in at stage `plan`, the conversation shrinks to its last lines |
| `frontend/src/i18n/coach/*.json` | About 75 keys in 6 languages (the factor copy and the screen's phrases) |
| `docs/api/v2-coach.md`, `docs/deferred-items.md` | The review step; D-215 (4) closed; D-226 |

No shared file (`package.json`, lockfile, `firebase.json`, workflows) was touched; `recharts` was already a dependency.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | The review step | Built here (backend), since the screen could not be reached without it |
| 2 | When the score shows | At stage `plan` (after the worker confirms), not at `review` |
| 3 | After the button | The plan's summary is shown inline; the plan page and PDF are NF-FC-021's |
| 4 | The words | Chosen by factor and level (strong from 70, fair from 40, weak below), written plainly with no product advice; not read by native speakers (D-226) |
| 5 | A very low factor | A note says why 74 points is only "Getting ready" (the rubric's floor rule) |
| 6 | Axe found a real fault | Recharts draws its ring sectors as `role="img"` without text; the drawing is now hidden from assistive technology inside the one labelled picture |

## Results

**Backend (2026-10-09):** 3,414 tests pass (163 skipped, the live ones); `black`, `ruff`, `mypy app` and `mypy --strict app/services` clean.

| Check | Result |
|---|---|
| The decision | A sure yes with its words in the message confirms; a weak yes, words not in the message, or "other" moves nothing; a change names an answer given, or none (the coach asks which) |
| The reply and the saved turn | A yes projects to `plan` with no next question and the reply is told the plan stage; a named change goes back to its stage with the answer reopened; a change naming none stays at the review with a "which answer?" instruction; a move outside the review changes nothing; each is one write |
| Through the API | A yes ends the turn at `plan` with every answer confirmed; a change to the pay ends it at `income` with `next_slot: monthly_salary`; a reply that moves nothing leaves the review |
| Break the rules on purpose | 4 breaks (a weak yes confirms, the quoted words not checked, a yes that does not confirm, the reply not told the plan stage): each failed a test |

**Frontend:** 1,254 tests pass (107 files); `tsc`, `eslint`, `prettier`, the i18n check (1,133 keys × 6 languages) and the build are clean.

| Check | Result |
|---|---|
| The three bands | Rendered from `session-04/05/06` as "Getting ready" 57, "Needs more preparation" 7 and "Well prepared" 91, each with its text alternative and the band written |
| The five factors | One card each, with a bar, the points as a number and in words, the level, and the words of that factor at that level (a strong factor in a weak score reads strong); an unknown band is shown neutrally |
| Cannot be shown | `score: null` says so and Try again reads it again; a failed read says so |
| The button | Sends the language, shows the summary; waits with a busy button and a status line; each refusal in words (not confirmed, in progress, bad answer, missing rate) with Try again where it helps; a second press gets the plan; a call over the allowance ends as a timeout |
| Six languages | Every factor × level × part exists in all six, and differs from English; each language renders with no raw key, digits 0–9 only, and passes axe |
| Accessibility | axe (serious and critical) passes in every band and language; the chart has a text alternative |
| In the chat | The score is read only once the stage is `plan`; the answer box is gone; the plan button works from the chat |

**In the emulator (the real backend and a real Gemini key, data loaded from the source files, a worker seeded at stage `plan`):**
- The score was **22 out of 100, "Needs more preparation"**, exactly persona 1's hand-computed value, with five real factor cards, on a 375 px phone with no sideways scroll.
- "Make my 90-day plan" showed the busy button and the wait line; the plan call then failed with the free-tier daily quota (`503`), and the screen said "The coach is busy right now… Try again" with the button (error path seen).
- With the session put back at `review`: **"Yes, that is right" moved it to the plan stage** and the score and button appeared; **"I want to change something"** made the coach ask "Please tell me which answer you want to change…" and stayed at Review.

**Not verified:** the plan being made live (quota; success path covered by tests with the recorded plan); the review reply in languages other than English and for "yes, but…" (D-226); the wording by native speakers.

## Manual test

```bash
cd backend && pytest tests/unit/services/test_coach_review.py tests/integration/api/test_coach_turns_review.py
cd ../frontend && pnpm vitest run src/utils/coachScore.test.ts src/components/coach
```

Locally: emulators plus `backend-api-live` and `frontend-emulator` (`.claude/launch.json`); load `cost_baselines`, `labor_laws` and `rates_cache` into the Firestore emulator, seed a worker and a session at `review`, set `config/feature_flags.flags.coach.enabled` to true, open `/coach` and press "Yes, that is right". In production the score needs `cost_baselines` loaded (D-216), or the screen shows "We cannot work out your score right now".

## Definition of Done (Frontend)

- [x] Renders all 3 bands from the mocks
- [x] Factor copy fully translated (6 languages, checked in a test)
- [x] The chart has a text alternative; axe clean in every band and language
- [x] The button makes the plan, with progress and failures in words
- [x] Strict types, lint and format clean, no shared file touched, tests added
- [x] Checked in the emulator with the real backend
- [ ] The plan made live (quota) and the plan view (NF-FC-021)
- [ ] Wording read by native speakers (D-226)
- [ ] Reviewed by a teammate (Devam)

## Commit

Branch: `feature/NF-FC-020-coach-score-screen` (already checked out).

```bash
git commit -m "feat(coach): add preparedness score screen and the review-to-plan step" -m "Refs: NF-FC-020"
```

PR title: `feat(coach): preparedness score screen and the review-to-plan step (NF-FC-020)`
