# NF-FC-009 — Coach turn endpoint with SSE streaming

## Summary

The route where the interview happens: `POST /api/v2/coach/sessions/{id}/messages`. The worker speaks (or the coach speaks first), and the coach's reply comes back token by token as Server-Sent Events, in the worker's language, built to `docs/api/v2-coach.md` and the conventions (`docs/api/v2-conventions.md`, sections 4 and 5).

1. **The stream.** `slot_update` events for the facts understood, `token` events for the reply, then exactly one `done` (the turn is saved) or `error` (nothing is saved). A `: ping` goes out after 15 seconds of silence.
2. **Idempotency.** `Idempotency-Key` is required. The same key and body after a finished turn replays it from storage (`Idempotency-Replayed: true`) and runs nothing; the rules for a running, failed or old turn follow the contract.
3. **History window and summary.** Each reply sees the newest 24 turns or 6,000 estimated tokens (`GEMINI_CHAT_HISTORY_*`); the turns left out are summarised after the reply and the summary travels with the next ones.
4. **Cancellation.** Closing the connection closes the Gemini call and marks the turn failed.
5. **A seam for slot extraction.** `CoachTurns` takes a `SlotExtractor`; NF-FC-010 supplies it. Until then it is `NoExtraction`.

**Read this first.** With no extraction a turn **understands nothing**: no `slot_update`, no answer stored, the coach asks the same question again and the stage stays at `intro` (D-210). The endpoint, the stream, the saving, the retries and the language are all real and tested; the interview only moves forward once NF-FC-010 is wired in.

## How a turn goes

```
POST /messages ─► 401 / flag 404 / 10-a-minute limit ─► key check (400) ─► load session (404)
   ─► not active (409) ─► same key finished? replay ─► same key running (409) / other key running (409)
   ─► text rule (422) ─► transcript full (409) ─► mark the turn "running" (a stale write is 409)
   ─► understand the text (NF-FC-010) ─► open the Gemini stream and wait for the first piece
         │  a Gemini failure here is an ordinary HTTP error (502 / 503 / 504) and the turn is marked failed
         ▼
   200 text/event-stream:  slot_update* ─ token* ─ done      (or error)
         │  done: answers, both messages, stage and last_turn are saved in ONE write first
         ▼
   after done: summarise the turns the window left out (best effort)
```

- **What the model is asked.** `coach/reply.v1` (`app/prompts/coach/`): the next question comes from the question bank and the state machine, not from the model; the model puts it in the worker's language and may repeat only the figures in `<slots>` and `<understood>`. The worker's text and the summary are data inside tags.
- **Order.** The facts come before the words (extraction runs first, design 4.2). A clarification replaces the next question with the bank's follow-up wording.
- **`last_turn`** on the session: `{key, body_hash, state, started_at, turn, message_id, slots}`. `running` older than 90 seconds counts as failed; a key older than 24 hours is forgotten; only the latest turn can be replayed.
- **Language.** The turn's `language` becomes the session's. `text` may be left out only for the first message or after a change of language; otherwise `422` on `body.text`.
- **Model and thinking.** `GEMINI_COACH_REPLY_TIER` (default `classification`) and `GEMINI_COACH_REPLY_THINKING_BUDGET` (default `0`), both in `backend/.env.example`. See D-115 and D-211.

## Files

| File | Change |
|---|---|
| `backend/app/api/v2/coach_turns.py` | New: the route and its error mapping |
| `backend/app/core/sse.py` | New: the event format and the heartbeat that cancels the source when the reader leaves |
| `backend/app/services/coach/turn_service.py` | New: `CoachTurns` (start, frames, save, summary) |
| `backend/app/services/coach/turn_replay.py` | New: the retry rules and the replay |
| `backend/app/services/coach/turn_prompt.py`, `turn_types.py` | New: what the reply is asked, the extractor seam |
| `backend/app/services/coach/session_overview.py` | The overview moved out of `session_service.py` (file size); unchanged behaviour |
| `backend/app/services/coach/session_service.py` | `document`, `set_last_turn`, `save_summary` |
| `backend/app/prompts/coach/reply.v1.yaml`, `summarise.v1.yaml` | New prompts |
| `backend/app/config.py`, `backend/.env.example` | Two settings: the reply tier and its thinking budget |
| `backend/app/core/errors.py` | `error_parts`: status, code and message of a Gemini failure, for the `error` event |
| `backend/app/dependencies.py`, `backend/app/api/v2/router.py` | `get_coach_turns`; the route is included |
| `backend/tests/...` | 67 new tests and a stub Gemini, plus two registries updated (below) |
| `docs/api/v2-coach.md`, `docs/data-model/collections/coach.md`, `docs/deferred-items.md` | Status, `last_turn` fields, D-210 to D-213 |

Two existing registries had to learn the new route and prompts: `AI_LIMITED` in `tests/integration/api/test_auth_matrix.py` (the route carries the Gemini budget) and `EXPECTED_PROMPTS` in `tests/unit/test_prompt_loader.py`. No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Reply tier | The fast tier with thinking off by default, not the reasoning tier: the reasoning tier took 18 s to its first piece with default thinking (D-115). It is a setting, so a staging run decides |
| 2 | Extraction | A seam and a no-op now; NF-FC-010 owns the real one (D-210) |
| 3 | Save in one write | Answers, both messages, stage and `last_turn` go in a single transaction, so a turn is saved whole or not at all. The message ids and turn number are known beforehand (`m003-c`, `turn_count + 1`) |
| 4 | Summary after `done` | Off the path of the first piece; it lags one turn (D-212) |
| 5 | A boundary catch-all | An unexpected exception after the stream began becomes an `error` event with `internal_error` and the neutral text, never the exception's own |
| 6 | Replay | Rebuilt from the transcript and the stored answers, the text as one `token` event, which the contract allows |
| 7 | Rate limit | `limit_ai_calls` (10 a minute per worker) on every request, including a replay, as the contract states |
| 8 | Live test | `tests/integration/test_coach_reply_live.py` times the first piece for the real prompt (opt-in) |

## Run it

From `backend/` with its virtual environment active:

```bash
python -m pytest tests/unit/test_sse.py tests/unit/services/test_coach_turn_service.py tests/unit/services/test_coach_turn_prompt_and_replay.py tests/integration/api/test_coach_turns.py -q
```

Expect `66 passed`. The test that reads the turn back from real storage needs the Firestore emulator (Terminal 1, from `frontend/`: `firebase emulators:start --only firestore --project demo-nomadfinance`). Terminal 2, bash:

```bash
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance GOOGLE_CLOUD_PROJECT=demo-nomadfinance
python -m pytest tests/integration/repositories/test_coach_session_repo.py -q
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"; $env:GOOGLE_CLOUD_PROJECT = "demo-nomadfinance"
python -m pytest tests/integration/repositories/test_coach_session_repo.py -q
```

Expect `10 passed`; unset the three variables afterwards (`test_config.py` fails while they are set).

**The real model, once, to see the first piece** (needs `GEMINI_API_KEY` in `.env.local`; uses a little quota):

```bash
RUN_LIVE_GEMINI=1 python -m pytest tests/integration/test_coach_reply_live.py -v -s
```

PowerShell: `$env:RUN_LIVE_GEMINI = "1"; python -m pytest tests/integration/test_coach_reply_live.py -v -s`. It prints the time to the first piece on the fast tier and on the reasoning tier (thinking off, and default) and checks the opening is written in Hindi.

**By hand against a running backend** (the `coach` flag on for your account, `$ID_TOKEN` a Firebase ID token):

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8080/api/v2/coach/sessions -H "Authorization: Bearer $ID_TOKEN" -H "Content-Type: application/json" -d '{"language": "en"}' | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
KEY=$(python -c "import uuid; print(uuid.uuid4())")
curl -N -X POST http://127.0.0.1:8080/api/v2/coach/sessions/$SESSION_ID/messages -H "Authorization: Bearer $ID_TOKEN" -H "Content-Type: application/json" -H "Accept: text/event-stream" -H "Idempotency-Key: $KEY" -d '{"language": "en"}'
```

Expect `token` events and a `done` with `"stage":"intro","next_slot":"destination_country","turn_count":0`. Send the same command again with the same `$KEY`: the same events, with `Idempotency-Replayed: true` (add `-i`), and no second Gemini call.

## Checks run (2026-10-09)

| Check | Result |
|---|---|
| New tests | 66 new + 1 on the emulator: the wire format and heartbeat (6), the prompt and the retry rules (19), the turn service (20), the API (21), real storage (1) |
| Backend suite (no emulator) | 2,593 passed, 137 skipped, **1 failed**: `test_coach_question_bank.py::TestTheFile::test_the_file_is_utf8_json_with_a_final_newline` (D-181, line endings on this checkout) |
| `black --check`, `ruff check .`, `mypy app` | clean (386 files, 195 source files) |
| Stream format | Events are the four of the conventions; the data validates against `CoachTokenEvent`, `CoachDoneEvent`, `ErrorEnvelope`; the first turn has the shape of `turn-01-start.sse` |
| Client disconnect | A hanging stream is cancelled, the upstream stream is closed and the turn is marked failed (unit test); the heartbeat cancels its source when the reader goes |
| Retries | Replay without a Gemini call, `idempotency_key_reused`, `request_in_progress`, `turn_in_progress`, a stale turn after 90 seconds, a failed turn run again, a key forgotten after 24 hours |

**Not verified:** the first piece under 2 seconds (D-211), the real model in any language (D-213), the live test (needs the key, not run), behaviour behind Cloud Run's proxy with real buffering, and the turn with real slot extraction (NF-FC-010).

## Definition of Done

Tracker row: *First token < 2 s p95 on staging; stream format matches contract; client disconnect cancels the upstream call.*

- [ ] First token under 2 s at p95 on staging: **not measured** (D-211)
- [x] Stream format matches the contract (events, headers, ordering, heartbeat, replay header, errors before and after the first byte)
- [x] A client disconnect cancels the upstream Gemini call (and the turn is marked failed)
- [x] History window and a summary of older turns
- [x] Idempotency, one turn at a time, session full, session not active, rate limit
- [x] Prompts in `app/prompts/coach/` with versions recorded on the session; token usage is logged by the Gemini client (operation `coach.reply`)
- [ ] Second-reader review (Pranjal, per the tracker)

## Noticed, not fixed

All are in `docs/deferred-items.md`: D-210 (wire in slot extraction), D-211 (first piece not measured), D-212 (the summary lags one turn), D-213 (read the live replies in each language). Also outside this task: D-181 still fails on this Windows checkout.

## Commit

Branch: `feature/NF-FC-009-coach-turn-sse` (already created).

Commit message:

```
feat(coach): add turn endpoint with streamed replies
Refs: NF-FC-009
```
