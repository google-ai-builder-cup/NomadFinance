# NF-FC-002 — Coach API contract and mocks

## Summary

The routes of the Financial Coach are now specified, with a sample of every answer (including ten streamed turns) and tests that keep the samples honest. The frontend can build the chat, score and plan screens (NF-FC-017, -020, -021) against the mock API before any backend exists, and the backend tasks (NF-FC-008 to -014) implement against models that are already written. Nothing is built: no endpoint, no Gemini call, no Firestore write, no screen.

| Route | Does |
|---|---|
| `POST /api/v2/coach/sessions` | Start the interview, or resume the open one (201 / 200) |
| `GET /api/v2/coach/sessions/{id}` | The answers so far, the transcript, the next question, the score |
| `POST /api/v2/coach/sessions/{id}/messages` | One turn, answered as a stream of Server-Sent Events |
| `POST /api/v2/coach/sessions/{id}/plan` | Make the 13-week plan from the confirmed answers (201 / 200) |
| `GET /api/v2/coach/plans/{id}` | A stored plan in one language |
| `GET /api/v2/coach/plans/{id}.pdf` | The plan as a PDF file |
| `GET /api/v2/coach/overview` | The active session and the newest plan, for the dashboard card |

The contract is `docs/api/v2-coach.md`. The executable form is `backend/app/schemas/coach_session.py` and `coach_plan.py` (Pydantic models and the rules that can be checked). The mocks are in `docs/mocks/coach/` (30 JSON files and 10 streams).

## The flow

```
POST /sessions ──► POST /messages (no text: the coach speaks first)
                        │
       ┌────────────────▼───────────────────────────────────────────────┐
       │ POST /messages (the worker answers) ► token… slot_update… done │  repeat, stage by stage:
       └────────────────┬───────────────────────────────────────────────┘  intro, income, obligations, debt, savings
                        │ the last answer
                        ▼
              stage `review`: the coach says what it understood
                        │ the worker says yes
                        ▼
              stage `plan`: GET /sessions/{id} has the score ──► POST /plan ──► GET /plans/{id} and /plans/{id}.pdf
```

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Routes live under **`/api/v2`**. | The task row and the merged conventions (NF-F0-002) say so. The standing instructions' "all endpoints under `/api/v1/`" predates them. |
| 2 | **Where the `Idempotency-Key` lives (closes D-126 for the Coach):** `last_turn` on the session document, `{key, body_hash, state, started_at, turn}`. A replay is rebuilt from the transcript and the slots stamped with that turn. | The turn route needs a key (conventions, section 4) and no storage existed. This needs no new collection, goes away with the session, and the same field stops a second turn starting while one runs. Only the latest turn can be replayed, which is all a dropped connection needs. |
| 3 | Two routes the tracker did not list: **`GET /coach/overview`** and **`restart: true`** on session create. | The dashboard card (NF-FC-022) must say Start, Resume or View plan without creating a session. A worker needs a way out of a full (200 messages) or unwanted session. Both can be dropped later without breaking anything. |
| 4 | **A turn with no `text`** means "the coach speaks": the opening question of a new session, or the current question again after a change of language. | One streaming path for the greeting and for a language switch (NF-FC-018), and session create makes no Gemini call. |
| 5 | **The PDF comes through the API** as bytes, not as a signed link. | The bucket has no CORS policy (NF-P3-018), so the app could not read a signed link's bytes to share the file, and a link anyone can open would be a link to a worker's debts. NF-FC-014's row says "return a signed URL": it needs Aditya's agreement (D-175). |
| 6 | **The plan's shape is defined here** (`CoachPlan`). Every figure is `{amount, currency}`, every sentence is text, all in the host country's currency. | NF-FC-012's finish line says "Plan JSON matches contract", NF-FC-021 needs a plan mock, and the plan validator and the translation check both need to find each figure. Pranjal reviews it (D-176). |
| 7 | **Everything in a stream is provisional until `done`.** The server first understands the answer, then writes the reply (design 4.2); the fact may also arrive after the words. | A turn is saved only when it completes (design 4.7). A half-seen fact must not be kept if the connection drops. |
| 8 | `slot_update` is `{slot, value, confirmed}`; `done` is `{message_id, stage, next_slot, turn_count}`. | The screen needs to know whether the worker agreed to a fact, and where the interview stands, without asking again. The conventions leave both open. |
| 9 | **`next_slot` and a simple table of slot to input**, not a structured answer. The chips and amount fields write text. | The tracker asks for input helpers; a structured `answer` field can be added later without breaking anything (open point 3). |
| 10 | Four codes of the Coach's own: `session_not_active`, `session_full`, `turn_in_progress`, `plan_not_ready`. The plan route reuses `request_in_progress` for "the plan for these answers is still being made". | A screen branches on each (new interview, restart, wait, confirm first). `request_in_progress` keeps the conventions' meaning. |
| 11 | **Rate limits:** the Gemini budget (10 a minute) is used only by a request that really calls Gemini, so a stored plan or translation costs none. | Tightening a limit later would be a breaking change, so the contract starts at the budget the repository already has. |
| 12 | The plan id is **the start of the slot hash**, and `slot_hash` is written down as code. | Idempotency by the hash is only real if every implementation writes the same canonical JSON. |
| 13 | **The score's band ids are placeholders** (`needs_work`, `getting_ready`, `well_prepared`). | NF-FC-006 decides the bands. The screen shows a neutral label for a band it does not know. |
| 14 | **The streams are written to the contract, not captured.** | There is no server to capture from. They are byte-exact to the wire format, and a test holds them to the event rules. |
| 15 | Message ids are opaque (`m_001`, ...). | The data model's `t001-c` example would give two consecutive coach messages the same id when the coach re-asks after a language switch. |

## Files

| File | Change |
|---|---|
| `docs/api/v2-coach.md` | New: the contract |
| `backend/app/schemas/coach_session.py` | New: create, session, turn request, stream event data, overview |
| `backend/app/schemas/coach_plan.py` | New: score, plan, plan response, `slot_hash` |
| `docs/mocks/coach/` | New: 30 JSON mocks and 10 `.sse` streams |
| `backend/tests/unit/test_coach_mocks.py` | New: the JSON mocks against the models and the question bank (the drift test) |
| `backend/tests/unit/test_coach_streams.py` | New: the streams against the event rules |
| `backend/tests/unit/test_coach_contract_models.py` | New: the rules in the models, and the document names every route, stream and code |
| `backend/tests/fixtures/coach_mocks.py` | New: helpers shared by those tests |
| `frontend/src/mocks/coach.msw.test.ts` | New: the mock API serves every route, and replays the streams (28 tests) |
| `docs/data-model/collections/coach.md` | One optional field, `last_turn`, on the session |
| `docs/mocks/README.md`, `docs/api/endpoints.md` | The `coach/` section; a pointer to the contract |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched. No Firestore rule changes: the new field is written by the backend only.

## How to use it

**Frontend** (NF-FC-017, -020, -021). In a test: `setupMockServer()`, then `server.use(handlerForMock("coach/session-03-review.json"))` to pick another answer. For a streamed turn: `server.use(sseHandler("POST /api/v2/coach/sessions/s_01/messages", "coach/turn-02-answer.sse"))`. `frontend/src/mocks/coach.msw.test.ts` shows each route, each refusal, and a small reader that splits a stream into events. The app's own reader (with the 30 s / 60 s limits and the retry) is NF-FC-017's job (D-99). The files that matter most for the chat screen: `turn-error-dropped.sse` (no `done`: retry with the same key), `turn-04-clarify.sse` (no fact stored), `turn-06-late-slot-update.sse` (do not depend on the order) and `turn-error-midstream.sse`.

**Backend** (NF-FC-008 to -014). Return `CoachSessionCreateResponse`, `CoachSession`, `CoachPlanResponse` and `CoachOverview`; take `CoachSessionCreateRequest`, `CoachTurnRequest` and `CoachPlanRequest` as bodies; send the event data as `CoachTokenEvent`, `CoachSlotUpdateEvent`, `CoachDoneEvent` and the error envelope. Use `slot_hash` for the plan id. Errors go through `ApiError`. The rules in the models are real checks (the next question is null at review, a completed session has a plan id, the budget adds up, the id is the hash), so a wrong plan fails before it reaches a worker.

**Changing the contract.** Update `docs/api/v2-coach.md`, the models and the mocks together. `test_coach_mocks.py` fails until the mocks parse as the models, `next_slot` and `stage` follow the question bank, the stored text is already redacted (a fixed point of `redact_text`), the plan id is the real hash of its slots, the budget adds up, the Hindi plan has the English plan's numbers, and the overview and the sessions agree.

## Run it

From `backend/`, with the virtual environment active (`source .venv/Scripts/activate` in bash, `.venv\Scripts\Activate.ps1` in PowerShell):

```bash
python -m pytest tests/unit/test_coach_mocks.py tests/unit/test_coach_streams.py tests/unit/test_coach_contract_models.py -q
```

Expect `146 passed`. From `frontend/`:

```bash
pnpm vitest run src/mocks/coach.msw.test.ts
```

Expect `28 passed`. To see that a plan id is the hash of its answers (the two values on the output line are equal):

```bash
python -c "import json; from app.schemas.coach_plan import slot_hash; from app.schemas.coach_profile import CoachProfile; b = json.load(open('../docs/mocks/coach/plan-get-01-english.json', encoding='utf-8'))['body']; print(slot_hash(CoachProfile.model_validate(b['slots']))[:20], b['id'])"
```

To read a stream as the client receives it (PowerShell: `Get-Content ..\docs\mocks\coach\turn-02-answer.sse -Encoding utf8`):

```bash
cat ../docs/mocks/coach/turn-02-answer.sse
```

Lint and types, as in the earlier runbooks:

```bash
python -m black --check app tests && python -m ruff check app tests && python -m mypy app && python -m mypy --strict app/services
```

## Checks run (2026-10-08)

| Check | Result |
|---|---|
| `black --check`, `ruff check` (all of `app` and `tests`) | clean (356 files) |
| `mypy app`, `mypy --strict app/services` | clean (181 and 61 files) |
| Backend unit tests | 1,869 passed, 7 skipped, **1 failed**: `test_coach_question_bank.py::TestTheFile::test_the_file_is_utf8_json_with_a_final_newline`, on a file this task did not touch. It reads raw bytes and fails when Windows checks the file out with CRLF (D-181). 146 of the passes are new |
| Coverage of the new models | 100% (265 statements: `coach_plan`, `coach_session`) |
| Mutation check | Ten deliberate errors in the mocks (a stream with no `done`, a plan whose `left_over` is one off, a Hindi figure changed from 900 to 950, a wrong `next_slot`, a raw phone number in the transcript, a misspelt field, an overview score that disagrees with its plan, one changed word in the review stream, a plan id that is not the hash, a `done` added to the dropped stream) each fail the backend tests; the six that change what a screen reads (the stream, the plan, the next question, the create answer, the review text, the dropped stream) also fail the MSW test. Every file was restored and its hash compared |
| Frontend ESLint, Prettier on the new file | clean |
| Frontend tests | new file 28 passed; whole suite 75 files and 793 tests passed, 186 skipped; **6 files could not load**: 3 need `axe-core`, which is in `package.json` but not installed here (D-169), and 3 (`tests/rules/*`) need the Firestore emulator. None touches this change |
| Frontend `tsc -b` | 4 errors, all in `src/mocks/axe.ts` for the missing `axe-core`; none in the new file |

**Not verified:** a stream read by a real browser over a real network (the streams are replayed by MSW in Node); any endpoint (none exists); the Hindi by a native speaker (D-180); Swagger (nothing to browse); `commitlint` (not installed here; the header is 49 characters, counted by hand).

## Definition of Done

Tracker finish line: *Contract merged before FC frontend / backend branches open; MSW can replay the SSE mock.*

- [x] MSW replays the SSE mocks (ten streams, `coach.msw.test.ts`)
- [ ] **Merged** before the Coach frontend and backend branches open (you)

Documentation:

- [x] Written in Markdown
- [x] Consistent formatting (headings, lists, code blocks)
- [ ] **Reviewed** by Aditya (the reviewer in the tracker), who also owns NF-FC-008, -009 and -014
- [x] In `/docs`
- [x] No AI attribution, no chat-style openers

Streaming (SSE) endpoint, the contract's share (the rest belongs to the tasks that build the endpoint):

- [x] Event types `token` / `slot_update` / `done` / `error` documented, heartbeat every 15 s (`v2-coach.md`, with the conventions)
- [ ] First token under 2 s at the 95th percentile on staging: stated as the goal; **NF-FC-009 measures it**
- [ ] Client disconnect cancels the upstream Gemini call: stated as a rule; **NF-FC-009 builds it**
- [ ] Frontend retries a dropped stream and never shows a half-rendered message as final: stated as a rule, with `turn-error-dropped.sse` ready; **NF-FC-017 builds it**

Feature-flagged module: [x] flag-off answer is `404 not_found` on every route (stated in the contract); the other items (lazy chunk, bundle unchanged, rollback) belong to the tasks that build and ship the module. Nothing in this change runs, so there is nothing to roll back: revert the commit.

## Noticed, not fixed

Left for later: D-175 (PDF delivery: NF-FC-014's wording), D-176 (the plan's shape needs Pranjal's review; add NF-FC-002 to NF-FC-012's dependencies), D-177 (the two extra routes; check-in routes still unspecified), D-178 (write `last_turn` in NF-FC-008 and -009), D-179 (no PDF mock; the streams are not captured), D-180 (a native speaker should read the Hindi), D-181 (a test that fails on a Windows checkout). Also: the standing instructions' "all endpoints under `/api/v1/`" is out of date for v2, and the tracker still calls the API reference `docs/api-contract.md` (D-04).

## Commit

Branch: `docs/NF-FC-002-coach-api-contract` (git reports `main`: create the branch before committing). One commit, as for NF-SA-002:

```bash
git add backend docs frontend/src/mocks/coach.msw.test.ts
git commit -m "docs(api): add coach contract, schemas and mocks" -m "Refs: NF-FC-002"
```

PR title: `docs(api): coach API contract, schemas and mocks (NF-FC-002)`

PR description:

> The Financial Coach's API is now specified before anything is built, so the chat, score and plan screens and the session, turn and plan backends can start in parallel.
>
> - `docs/api/v2-coach.md`: the seven routes (the six in the tracker, plus `GET /coach/overview`, which the dashboard card needs), the streamed turn, the score and the plan.
> - `coach_session.py`, `coach_plan.py`: the same contract as Pydantic models. They refuse what the contract refuses, and the plan id is the real hash of the answers.
> - `docs/mocks/coach/`: 30 JSON samples and 10 streamed turns, including a dropped connection and a mid-stream error. The streams are written to the contract, not captured, because there is no server yet.
> - Tests keep the samples honest: against the models, the question bank, redaction, the plan's arithmetic, and the Hindi plan's numbers. An MSW test replays every stream.
>
> Decisions that need a second pair of eyes: the idempotency key is kept on the session (`last_turn`, which closes D-126 for the Coach); the PDF is served through the API instead of a signed link (D-175); the plan's shape is defined here (D-176).
>
> No endpoint, flag or running behaviour changes. Rollback is reverting the commit.
>
> Reviewer: Aditya. Refs: NF-FC-002
