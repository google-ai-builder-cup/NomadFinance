# NF-FC-008 — Coach session state machine

## Summary

The part of the Financial Coach (Future Scope, behind the `coach` flag) that remembers an interview: where it stands, what the worker has said, and what is allowed next.

1. **Three routes**, built to `docs/api/v2-coach.md`: `POST /api/v2/coach/sessions` (start, or resume the open one), `GET /api/v2/coach/sessions/{id}` and `GET /api/v2/coach/overview` (the dashboard card).
2. **A state machine** (`session_machine.py`): the stages `intro → income → obligations → debt → savings → review → plan`, the moves of design 4.3, and the rule that the stage is the earliest incomplete one. Any move not in the diagram is refused.
3. **Storage** in `users/{uid}/coach_sessions/{id}` (`coach.md`): one active session per worker, written in a transaction, every write checked against the revision it read.
4. **The methods the next tasks call**: `record_turn`, `request_correction`, `confirm_review`, `complete`.

No Gemini call, no streaming, no score (the engine is NF-FC-011: `score` is `null` until it is wired in, which the contract allows).

## How it works

- **A stage is complete** when every question it applies has a **confirmed** answer. The bank's skip rule drops the interest question when the debt is 0. The departure date is the one optional question: it is complete once answered or **declined** (`declined_slots`, closes D-171).
- **`settle`** walks the diagram forward one hop at a time while a stage is complete, so a worker who volunteers later facts keeps them and the stage ends at the earliest gap. From `review` the answers do not move the stage.
- **At `review`** the worker either confirms (`confirm_review`: every answer confirmed, stage `plan`) or corrects (`request_correction`: back to the stage that holds the answer, which is un-confirmed so it is asked again; once re-answered the session settles forward to `review`).
- **Status**: `active` becomes `completed` (`complete`, from `plan`) or `abandoned` (14 days without a turn, closed when next read or started; or `restart`). A finished session never reopens.
- **One active session**: `create_or_resume` reads the active sessions and creates one only if there is none, in one transaction. A burst that cannot finish returns `409 request_in_progress` with `Retry-After: 2`.
- **Writes** carry the revision they read; a stale write is refused (`SessionConflictError`), so two tabs cannot overwrite each other. A turn is saved whole: answers, messages, language, stage, `last_active`, `expires_at`.
- **Transcript** text is redacted before it is stored (phone numbers, emails, ID and account numbers, URLs); 200 messages at most.
- **Expiry**: `expires_at` is the last turn plus 30 days; an expired session is read as absent until the TTL policy deletes it (D-103).
- **Ownership**: another worker's session, a missing one and an id that cannot exist are the same `404 not_found`.

## Files

| File | Change |
|---|---|
| `backend/app/services/coach/session_machine.py` | New: stages, moves, `settle`, `next_slot`, status moves |
| `backend/app/services/coach/session_service.py` | New: `CoachSessions` (start, get, overview, record_turn, correction, confirm, complete) |
| `backend/app/services/coach/session_document.py` | New: the stored document, the contract's view of it, idle and expiry |
| `backend/app/services/coach/session_types.py` | New: errors and small value types |
| `backend/app/repositories/coach_session_repo.py` | New: sessions (transactions) and the newest plan |
| `backend/app/api/v2/coach.py` | New: the three routes |
| `backend/app/api/v2/router.py`, `backend/app/dependencies.py` | The router is included; `get_coach_sessions` |
| `backend/tests/...` | 116 new tests (below), a fake storage and an app wired to it |
| `docs/data-model/collections/coach.md` | Two fields: `declined_slots`, `question_bank_version` |
| `docs/api/v2-coach.md` | Implementation status; `409 request_in_progress` on start; open point 8 resolved |
| `docs/deferred-items.md` | D-171 closed; D-103, D-178 noted; D-206 to D-208 added |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched: the rules and indexes of NF-F0-004 already cover `coach_sessions` and `coach_plans`.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Routes in this task | The contract assigns `POST /sessions`, `GET /sessions/{id}` and `GET /overview` to NF-FC-008, so they are built here |
| 2 | "Not sure" about the date | `declined_slots` on the session, not a fake value (D-171) |
| 3 | A stage needs confirmed answers | An answer saved as unconfirmed (low confidence, awaiting a check) keeps the stage where it is and the question is asked again |
| 4 | Corrections | Only at `review`; the corrected answer is un-confirmed so the stage gate does the rest |
| 5 | Score | `null` until NF-FC-011 passes a `scorer`; it is worked out on read, not stored (D-208) |
| 6 | Idle sessions | Closed on read or start, not by a job, as `coach.md` says |
| 7 | `record_turn` takes `extra` | So the turn endpoint can write `last_turn`, `models`, `prompt_versions` and `summary` in the same step without this task owning their rules |
| 8 | Overview | Reads only: it skips an idle session and never closes it |
| 9 | Contention | More transaction attempts than the default (15), and a burst that still fails is a `409`, not a `500` |

## Run it

From `backend/` with its virtual environment active (`source .venv/Scripts/activate` in bash, `.venv\Scripts\Activate.ps1` in PowerShell):

```bash
python -m pytest tests/unit/test_coach_session_machine.py tests/unit/services/test_coach_session_service.py tests/integration/api/test_coach_sessions.py -q
```

Expect `107 passed`. The storage tests need the Firestore emulator. Terminal 1, from `frontend/`:

```bash
firebase emulators:start --only firestore --project demo-nomadfinance
```

Terminal 2, from `backend/`. bash:

```bash
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance GOOGLE_CLOUD_PROJECT=demo-nomadfinance
python -m pytest tests/integration/repositories/test_coach_session_repo.py -q
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"; $env:GOOGLE_CLOUD_PROJECT = "demo-nomadfinance"
python -m pytest tests/integration/repositories/test_coach_session_repo.py -q
```

Expect `9 passed`. Unset the three variables afterwards: `tests/unit/test_config.py` fails while they are set (it checks that a deployed environment refuses them).

**By hand against a running backend** (needs the `coach` flag on for your account and a Firebase ID token `$ID_TOKEN`):

```bash
curl -s -X POST http://127.0.0.1:8080/api/v2/coach/sessions -H "Authorization: Bearer $ID_TOKEN" -H "Content-Type: application/json" -d '{"language": "en"}'
curl -s -X POST http://127.0.0.1:8080/api/v2/coach/sessions -H "Authorization: Bearer $ID_TOKEN" -H "Content-Type: application/json" -d '{"language": "hi"}'
curl -s http://127.0.0.1:8080/api/v2/coach/overview -H "Authorization: Bearer $ID_TOKEN"
```

Expect `201` with `resumed: false`, then `200` with the same `id` and `resumed: true` (and `language` still `en`), then an overview with that session and `plan: null`.

## Checks run (2026-10-09)

| Check | Result |
|---|---|
| New tests | 116 passed: 68 state machine (every one of the 49 stage pairs and 9 status pairs, skip and decline rules), 24 service, 15 API, 9 storage on the emulator |
| Backend suite (no emulator) | 2,521 passed, 134 skipped, **1 failed**: `test_coach_question_bank.py::TestTheFile::test_the_file_is_utf8_json_with_a_final_newline`, the line-ending test of D-181 on a Windows checkout |
| `black --check`, `ruff check .`, `mypy app` | clean (371 files, 187 source files) |
| **Emulator** | Three simultaneous starts leave one active session (repeated 5 times); a stale write is refused and changes nothing; a new service over the same storage resumes the interview at the same stage with its messages; Firestore timestamps read back into the contract model |

The tests that cover the Definition of Done: *survives a server restart* (`test_a_new_service_over_the_same_storage_continues_where_the_old_one_stopped`, and the same with real storage on the emulator), *illegal transitions rejected* (the 49 pairs, plus out-of-turn confirm, correct and complete), *one active session* (service, API and emulator).

**Not verified:** "one active session" on a real Firestore project (D-206); the TTL policy (D-103); the backend with a real Firebase token (the API tests replace sign-in and the flag).

## Definition of Done

Tracker row: *Session survives a server restart mid-interview; illegal stage transitions are rejected; unit tests per transition.*

- [x] Session survives a restart (stored every write; tested with a new service, and on the emulator)
- [x] Illegal stage transitions are rejected (`IllegalTransitionError`; nothing is written)
- [x] Unit tests per transition (every pair of stages and of statuses)
- [x] Create, get, resume, one active session (routes and tests)
- [x] Python standards: types, async I/O, specific exceptions, no stack traces to clients, files under about 300 lines
- [ ] Second-reader review (Pranjal, per the tracker)
- [ ] Checked on staging (D-206)

## Noticed, not fixed

All are in `docs/deferred-items.md`: D-206 (check "one active session" on staging), D-207 (what NF-FC-009, -010, -012 call and how errors map), D-208 (the score is not stored on the session). Also outside this task: D-181, the line-ending test, still fails on this Windows checkout.

## Commit

Branch: `feature/NF-FC-008-coach-session-state` (already created).

Commit message:

```
feat(coach): add session state machine and session routes
Refs: NF-FC-008
```
