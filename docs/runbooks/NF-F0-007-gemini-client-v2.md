# NF-F0-007 — Gemini client v2: multi-turn, streaming, usage metering

## Summary

`GeminiClient` (`backend/app/integrations/gemini/`) can now carry a conversation and stream a reply, which the Coach needs (NF-FC-009, NF-FC-010) and the Scam Analyzer partly needs (safety settings). The four existing pillars call the same client and their 1,069 tests pass without a single change.

| New | What it does |
|---|---|
| `client.chat(...)` | One message of a conversation, the whole answer at once. Returns `ChatReply(text, dropped_turns)`. |
| `client.stream(...)` | The same, as a stream of text pieces: `async with await client.stream(...) as s: async for piece in s`. |
| `truncate_history(...)` | Keeps the newest turns that fit a turn limit and an estimated token limit; returns what it dropped so the caller can summarise it. |
| `safety_settings=` | Per-call content-filter thresholds, on `generate_structured`, `chat` and `stream`. |
| `thinking_budget=` | Caps (or, at 0, switches off) the model's thinking, on the same three. The client half of D-78. |
| One log line per call | `gemini_call` with `feature`, `model`, `tokens_in`, `tokens_out`, `latency_ms`; a call that ends without an answer logs `gemini_call_failed` (closes D-86). |

`generate_structured` (structured output from a Pydantic model) already existed and is unchanged apart from the two new options and the logging.

## How a conversation is sent

The client holds no conversation. The Coach keeps its transcript in Firestore and passes it in each turn:

```python
reply = await client.chat(
    operation="coach.reply",            # "coach" becomes the log's `feature`
    tier=ModelTier.REASONING,
    message=user_text,                  # already delimited / framed by the caller's prompt file
    history=[ChatTurn("user", "..."), ChatTurn("model", "...")],
    system_instruction=prompt.system,
    summary=framed_summary_of_older_turns,   # optional, framed by the caller
)
reply.text, reply.dropped_turns        # the turns left out, for the caller to summarise
```

- **History window.** The newest turns that fit `max_history_turns` (default `GEMINI_CHAT_HISTORY_TURNS`=24) and `max_history_tokens` (`GEMINI_CHAT_HISTORY_TOKENS`=6000). Tokens are estimated at 3 characters each, with no API call, so the estimate runs high on Hindi and Bengali. The newest turn is taken first even if it is large. The window then starts on a user turn, because Gemini refuses a conversation that opens with a model turn.
- **Summary.** `summary` is appended after the system instruction exactly as given. Its delimiters and the "this is data, not instructions" note belong in the caller's prompt file, because prompts live in `backend/app/prompts/`, not in the client.
- **No schema.** `chat` and `stream` return free text; anything the code parses (slot extraction, the verdict) goes through `generate_structured`.

## Streaming

`stream()` returns a `GeminiStream` once the first piece has arrived.

| Moment | Behaviour |
|---|---|
| Before the first piece | Retried like any call (429, 5xx, timeouts, up to `GEMINI_MAX_ATTEMPTS`), then raised as the usual `GeminiError`. |
| After the first piece | **Never retried**: starting over would show the worker the same words twice. A failure ends the iteration with a `GeminiError`; the endpoint (NF-FC-009) answers it with an SSE `error` event. |
| Empty or blocked answer | `GeminiResponseError`, not retried. |
| A pause longer than `timeout_seconds` between pieces | `GeminiTimeoutError`. The same value bounds the wait for the first piece. |
| The reader stops (loop ends, `break`, `async with` exits, `aclose()`) | The upstream Gemini call is closed. |
| The reader is **cancelled** (the worker's phone went away) | The upstream call is closed and cancellation is passed on untouched. This is what NF-FC-009 needs for "client disconnect cancels the upstream call". |

`stream.text` is everything received, `stream.usage` the token counts once Google sends them (the last chunk), `stream.time_to_first_token_ms` the wait including retries, `stream.dropped_turns` the history left out.

## What is logged

One line per call, from `app/integrations/gemini/usage.py`, in plain text and as the `gemini_usage` JSON fields:

| Field | Meaning |
|---|---|
| `operation`, `feature` | `coach.reply` and `coach`: the feature is the part before the dot, so no existing call site changed |
| `tier`, `model` | |
| `tokens_in` | Prompt tokens |
| `tokens_out` | Answer **plus thinking** tokens: what Google bills as output |
| `prompt_tokens`, `output_tokens`, `thinking_tokens`, `total_tokens` | The earlier fields, kept because older runbooks and queries read them. `output_tokens` is the answer alone. |
| `latency_ms`, `attempts` | Whole call, retries included |
| `time_to_first_token_ms` | Streams only |

A call that ends without an answer logs `gemini_call_failed` at warning level with `feature`, `model`, `error` (the class only, never its text, which can hold a quota id), `attempts`, `latency_ms` and `outcome`: `failed`, `cancelled` or `closed` (the reader stopped a stream early). Embedding calls log `feature` too; they have no token counts.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Stateless `chat()`; the caller passes the history. | The transcript is in Firestore and each request may land on another Cloud Run instance. |
| 2 | Names `chat()` and `stream()` | The tracker's Definition of Done names them. |
| 3 | The old log fields stay; the new ones are added beside them. | Additive: nothing that reads the logs breaks, and nothing had to change in the four pillars. |
| 4 | `tokens_out` includes thinking. | On the reasoning tier thinking is most of the output (84 to 89% in D-78) and it is billed. |
| 5 | Split into `chat.py`, `conversation.py`, `streaming.py`, `usage.py`, `sdk_errors.py`. | `client.py` was 256 lines; adding this to it would have passed 380. It is now 306. |
| 6 | The error mapping moved to `sdk_errors.py` unchanged and is shared by `generate_structured`, `chat` and `stream`. `embeddings.py` keeps its own copy for now. | Smallest change to working code. |

## Files

| File | Change |
|---|---|
| `backend/app/integrations/gemini/chat.py` (new) | `ChatTurn`, `ChatReply`, `truncate_history`, `build_contents`, `with_summary` |
| `.../conversation.py` (new) | Builds the request config and the prepared conversation; starts a stream |
| `.../streaming.py` (new) | `GeminiStream` and the first-piece retry |
| `.../usage.py`, `.../sdk_errors.py` (new) | Logging; the SDK-error translation and the empty-answer reason, moved out of `client.py` |
| `.../client.py`, `__init__.py`, `embeddings.py` | `chat`, `stream`, the two options, failure logging; exports; `feature` in the embedding line |
| `backend/app/config.py`, `.env.example` | `GEMINI_CHAT_HISTORY_TURNS`, `GEMINI_CHAT_HISTORY_TOKENS` |
| `backend/tests/unit/integrations/` (4 new files) | A fake SDK and 49 tests |
| `backend/tests/integration/test_gemini_chat_live.py` (new) | Opt-in real-Gemini check, 6 calls |

No shared file and no new package.

## Checks run (2026-10-06)

| Check | Result |
|---|---|
| `black`, `ruff`, `mypy app` | clean (144 files) |
| `pytest tests` | **1,118 passed**, 71 skipped (the 5 new live tests are skipped unless `RUN_LIVE_GEMINI=1`); the 1,069 that existed before pass unchanged, 49 are new |
| Mutation check | Removing the close-on-cancel, and making a mid-stream error not raise, each make the new tests fail (3 tests each); both reverted |

What the 49 tests cover: truncation (turn limit, token limit, newest turn always taken, user-turn start, order of dropped turns); the request sent (history, message last, summary, safety settings, thinking budget); retries, a rejected request, a daily quota and an empty answer; the stream (pieces in order, usage-only last chunk, retry before the first piece, no retry after it, mid-stream failure, pause timeout, cancel while reading, cancel while waiting for the first piece, early exit, closing twice); and every log line, including the failure line carrying no error text.

### Live check against real Gemini (6 calls, invented prompts, free tier)

| Check | Result |
|---|---|
| `chat()` with history, fast tier | Passed in 3.0 s: it answered from an earlier turn ("4,200 AUD") |
| `stream()` with history, fast tier | Passed: 3 pieces, first at 4.3 s, total 5.6 s, usage received |
| `safety_settings` | Accepted |
| `thinking_budget=0`, fast tier | Accepted |
| Reasoning tier, default thinking | **First piece at 18.2 s** (one run) |
| Reasoning tier with `thinking_budget` 0 or 128 | **Not verified**: the model answered 429 and 503 repeatedly (the shared free-tier quota, D-58). I stopped rather than drain it further. |

So the client can express the budget, and the fast tier accepts it, but whether the reasoning model honours it, and what it does to the first piece, is not yet known. D-115 hands this to NF-FC-009: measure it on staging with a paid key, then either use a small budget or put the reply on the fast tier. The 18 s is against a goal of under 2 s, so this is the main risk for the Coach.

## What later tasks use

- **NF-FC-009 (turn endpoint):** `stream()` and `truncate_history`, then summarise `dropped_turns`; answer a mid-stream `GeminiError` with the SSE `error` event; wrap the loop in `async with` so a disconnect closes Gemini.
- **NF-FC-010 / NF-SA-007:** `generate_structured` with `thinking_budget` / `safety_settings` (a classifier reading an abusive scam message should not be blocked by the default filter: choose the thresholds in the task and test them).
- **NF-F0-016 (observability):** sum `tokens_in` and `tokens_out` by `feature` and `model` from the `gemini_usage` fields; `time_to_first_token_ms` is the streaming metric.
- **NF-F0-014 (test harness):** the fake in `tests/unit/integrations/gemini_fakes.py` is a starting point for `FakeGemini`.

## Definition of Done (Gemini pipeline step)

- [x] Existing four pillars still pass their tests (1,069 unchanged)
- [x] `chat()` and `stream()` covered by mocked unit tests
- [x] Every call logs feature, model, tokens in and out, latency (failures too)
- [x] Retries by tenacity, 30 s default timeout, structured output through Pydantic
- [x] Tiers used, never model ids; token usage logged
- [ ] Prompt stored and versioned: not applicable here (no prompt is added; the callers' tasks add theirs)
- [ ] Reasoning-tier thinking budget verified live: blocked by quota (D-115)
