# NF-SA-009 — Psychology explainer and safe next steps

## Summary

After `POST /api/v2/scam/analyze` has classified a message, it now writes the `explainer` of the contract (`docs/api/v2-scam.md`) in the **worker's language** (the `language` they sent, not the message's) at about a grade-6 reading level:

- **A scam** (reasoning tier): `why_it_works`, one entry per detected tactic ("tap to explain"), `scammer_wants`, and exactly 3 `next_steps`.
- **A message that is not a scam** (classification tier): a short `reassurance` and one general `tip`.
- **If it cannot be made**, the answer is still `200` with `explainer: null` and `explainer_status: "unavailable"`. The worker keeps the verdict.

The screenshot path calls the same function (NF-SA-008), so it gets the explainer too.

Not in this task: similar scams (NF-SA-010), indicators (NF-SA-011), storing, caching and the 20-an-hour limit (NF-SA-012), the one-tap report (NF-SA-013), the screens and read-aloud, the eval runner (NF-SA-014). The tracker's dependency NF-SA-007 and its sibling NF-SA-008 are merged.

## How it works

```
analyze_text / analyze_screenshot
  redact -> classify (Flash-Lite) -> explain_message
                                       |- scam   -> scam/explain.v1   reasoning tier, thinking budget 256, at most 20 s;
                                       |                                busy, rate limited or slow -> the same prompt
                                       |                                once on the classification tier; whole step 40 s
                                       '- benign -> scam/reassure.v1  (classification tier)
                                      -> clean + check -> Explainer | None
```

**What the scam call is given:** the worker's language (named in words), the host country of their corridor, the verdict's type and risk, what the message asks for (`details`), the tactics to explain, and the curated notes from `scam_taxonomy`: each tactic's `how_it_works` and the type's and tactics' `safe_response`. The redacted message sits in a `<message>` block the prompt calls data. Sources and curators are not sent.

**What is checked before an answer is returned.** Any failure makes the explainer `unavailable` and keeps the verdict:

| Check | Why |
|---|---|
| One entry for each detected tactic, in the verdict's order; an unknown or repeated tactic id is dropped; a missing one rejects the answer | The contract says "one per detected tactic" |
| Exactly 3 steps (more are cut to 3, fewer reject the answer) | The contract |
| No link, email address, `[PHONE]`-style token, and no run of 7 or more digits that the curated notes did not give; no text over 400 characters | A scam message can try to plant its own contact point into "next steps"; a runaway answer is not grade 6 |
| Hindi and Nepali in Devanagari, Bengali in Bengali script, the others in Latin letters | "Language matches the user profile". It does not tell Tagalog from Indonesian |
| The whole step finishes within 40 s | The client allows 60 s for the check, and the verdict took a few seconds |
| The reasoning tier gets 20 s of those 40; a 429, a 503, a timeout or those 20 s run out send the same prompt once to the classification tier. An answer that fails a check above is **not** retried on the other tier | Measured live on the free tier (below): the reasoning model refused most calls. Another tier is usually free, and asking a second model about an answer that was merely wrong helps nobody |

A scam with **no detected tactic** is explained through its type's usual tactics (`related_tactics`), so `why_it_works` is never empty.

**Helplines:** the prompt may name a helpline only if the curated notes give it for the worker's host country, and the check refuses a long number the notes did not give. Today the notes carry one number, Singapore's 1799, so a worker on an Australian or Malaysian corridor is told to use an official place, not a number.

**Logging:** one line `scam_explained input=… kind=… status=…`; `scam_explainer_fallback reason=…` when the reasoning tier was busy or slow; and on failure `scam_explainer_unavailable kind=… reason=…` where the reason is an error class or a rule name. The model's words are never logged, since they can repeat the message.

## Files

| File | Change |
|---|---|
| `backend/app/prompts/scam/explain.v1.yaml`, `reassure.v1.yaml` (new) | The two prompts |
| `backend/app/schemas/scam_explain.py` (new) | The loose structured-output models of the two calls |
| `backend/app/services/scam/explainer.py` (new) | The calls, the cleaning, the checks and the time box |
| `backend/app/services/scam/analyzer.py` | Calls `explain_message` after the verdict; fills `explainer` and `explainer_status` |
| `backend/tests/unit/services/test_scam_explainer.py` (new) | 45 tests |
| `backend/tests/fixtures/scam_explain.py` (new) | Rebuilds each model answer from the analyze mocks' `explainer` |
| `backend/tests/integration/api/test_scam_analyze.py`, `test_scam_analyze_screenshot.py`, `tests/unit/test_prompt_loader.py` | Now use the explainer recordings; the answer equals the mock's `explainer` for all four cases |
| `backend/tests/integration/api/test_scam_explain_live.py` (new) | Opt-in live test with the timing and the English reading grade |
| `backend/app/prompts/README.md`, `docs/api/v2-scam.md` | Table rows, the contract's "state" and open point 1, the design's benign rule, D-138 to D-140 |

No shared files, no new dependencies, no workflow change. The contract (`v2-scam.md`) and the response models did not change: the explainer shapes were already there from NF-SA-002.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | A scam is explained on the reasoning tier with `THINKING_BUDGET = 256`, at most 20 s of a 40 s box, and **one retry on the classification tier** when the reasoning tier is busy, rate limited or slow | The tracker says the reasoning model; D-115 measured 18 s to a first piece with default thinking, and writing six plain lines needs little thinking. The live run of 2026-10-07 (below) showed the reasoning model refusing most calls on the free tier, so a scam would usually have had no explainer. The contract allows the time box and a faster tier. The numbers are first guesses (D-138) |
| 2 | A benign message is reassured on the classification tier, not skipped | Design 5.2 said "the explainer is skipped for benign", but the tracker's Definition of Done and the contract both give a benign message a reassurance and a tip. The expensive tier is skipped, not the reassurance. `design.md` is updated |
| 3 | Two prompts and two loose response models | A scam and a reassurance share nothing but the language rules, and a tier each |
| 4 | Grounded in the curated taxonomy notes, with the host country | The steps rest on the curators' `safe_response`, not on what the model remembers, and a helpline is only the right country's |
| 5 | Failure is `unavailable`, never an error | The contract: the worker keeps the verdict |
| 6 | The checks refuse the answer rather than editing it | Cutting a sentence out of an explanation can change its meaning; a worker with no explainer is safer than one with a wrong one |
| 7 | The explainer is written in the request's `language`, not the message's | The contract: "the worker's language" |

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` (backend) | clean |
| `mypy --strict app/services` | clean |
| `pytest` (backend) | **1633 passed, 94 skipped** (the live tests); 45 are new in `test_scam_explainer.py`, and 4 endpoint tests were added to `test_scam_analyze.py` (a failed explainer still gives the verdict, a busy reasoning tier still gives an explainer, a benign message never calls the scam explainer, and the raw message reaches no call) |
| The answer against the mocks | For all four mock cases (high, medium, low, benign) the endpoint returns exactly the mock's `explainer`, text and language |
| Caught by my own test | A helpline the curated notes write as `1300 292 371` was refused because the check compared digits with spaces; digits are now compared on their own |
| Live, free tier, 2026-10-07 (run by Devam, before the fallback) | English scam explained in 18.5 s (with one 503 retry), Hindi in 9.5 s, both plain and in the right script. Across the two runs, 2 of 10 scam explainers on the reasoning model finished; 8 were refused (`GeminiRateLimitError` or `GeminiUnavailableError`) or ran out the 40 s box (a further five attempts in the first run were lost to a bug in the live test itself, an event loop shared between tests, now fixed). Classifying a message took 13 to 43 s on the same key. The fallback was added after this run |
| Live, after the fallback and the test fixes (run by Devam, free tier, 2026-10-07) | **9 passed in 183 s**: an English scam, a code-phishing call on an Australian corridor with no Singapore helpline in the text, Hindi, Tagalog, Indonesian, Nepali and Bengali in their own script, a message that orders the writer to add `[URL]` and `[PHONE]` (it did not), and a benign delivery notice. The reasoning model was refused on most calls, so the classification-tier fallback answered; it is the usual path on this key |

`mypy app tests` (without `--strict`, tests included) reports 28 errors in 15 test files. None of them is in a file this task created, and the one in `test_scam_analyze_screenshot.py` is on a line this task did not touch.

## Do this: measure it live again (D-138)

From `backend/`, with `GEMINI_API_KEY` in `.env.local` (see `backend/.env.example`):

PowerShell:

```powershell
$env:RUN_LIVE_GEMINI = "1"
pytest tests/integration/api/test_scam_explain_live.py -v -s
```

bash:

```bash
RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_scam_explain_live.py -v -s
```

About 12 Gemini calls, 9 of them explainers on the reasoning tier, which has answered 429 and 503 on the free tier (D-58): if it does, wait a minute and run a single test with `-k`. It prints for each case the seconds the explainer took against the 40 s allowed, and the text. It asserts:

- the English scam explainer has 3 steps, finishes within the time box and reads at Flesch-Kincaid grade 8 or below (grade 6 is the aim; the estimate is rough on short text);
- a code-phishing message for an Australian corridor does not mention 1799 (Singapore's number);
- Hindi, Tagalog, Indonesian, Nepali and Bengali come back in their own script;
- a message that tells the writer to put `[URL]` and `[PHONE]` in the next steps does not get them there;
- a delivery notice gets a benign reassurance.

Each test uses its own Gemini client (the shared one keeps a connection pool tied to the first test's event loop, which made four earlier runs fail with `Event loop is closed`). Watch the log lines: `scam_explainer_fallback reason=…` means the reasoning tier was busy and the classification tier answered, and `scam_explainer_unavailable` means both failed. If a scam usually takes over about 25 s, lower `THINKING_BUDGET` or `PRIMARY_TIMEOUT_SECONDS`, or put the scam explainer on the classification tier from the start (constants in `app/services/scam/explainer.py`).

## Manual test through the API

The endpoint needs the flag on, a Firebase token, the taxonomy loaded (`python -m src.loaders.scam_taxonomy` in `data-scripts/`) and a Gemini key; the commands are in `docs/api/v2-scam.md` ("Analyze"). For a scam the answer has `explainer.kind: "scam"` and `explainer_status: "ready"`; for a message such as a delivery notice, `kind: "benign"`. To see the `unavailable` shape, set `GEMINI_MODEL_REASONING` to a model name that does not exist and send a scam: the verdict is returned with `explainer: null`.

## Not done, and why

- **The reasoning tier is unproven on this key** (D-138): it was refused on most calls, so the passing live run mostly exercised the classification-tier fallback. A run on a key with more quota would show whether the reasoning tier is worth its latency, and by how much the two tiers' explanations differ.
- **No native speaker has read the output** (D-139), and grade 6 is measured only for English.
- **Not stored and not cached** (NF-SA-012; D-140 lists what that task must do with the explainer).
- **Latin-script languages are not told apart** (Tagalog from Indonesian, either from English).

## Definition of Done (backend endpoint)

- [x] Explainer present for every `is_scam: true` verdict (or `unavailable` when it cannot be made, per the contract)
- [x] A benign verdict gets a short reassurance and a general tip
- [x] Language matches the request's `language` (script checked; Latin languages by the prompt)
- [x] Pydantic models for the structured output; prompts in `app/prompts/scam/`, versioned, not inline
- [x] Structured logging with timing through the Gemini client; no model text or message text in the logs
- [x] Errors: a failed explainer never fails the check; the existing `ai_*` errors for a failed classification are unchanged
- [x] `docs/api/v2-scam.md` and the prompts README updated; the Swagger shapes did not change
- [x] Tests, lint, format and `mypy --strict app/services` pass
- [x] Measured live after the fallback: 9 of 9 live tests pass; English reads at grade 8 or below by Flesch-Kincaid
- [ ] Reasoning tier compared with the fallback on a key with quota (D-138)
- [ ] Read by speakers in the other five languages (D-139)
- [ ] Rate limiting: not this task (the general 10-a-minute budget applies; the 20-an-hour limit is NF-SA-012)
