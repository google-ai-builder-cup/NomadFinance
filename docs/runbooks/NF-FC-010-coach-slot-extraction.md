# NF-FC-010 — Coach slot extraction and clarifying follow-ups

## Summary

After each worker message the Financial Coach now reads which interview answers it contains, and asks again instead of guessing when a figure is unclear. It fills the seam NF-FC-009 left (`SlotExtractor`, D-210): until now a turn understood nothing, so the interview never moved past `intro`.

One structured Gemini call reads the message (`coach/extract.v1`, classification tier). **Code, not the model, then decides what is kept**: every candidate is checked against the worker's own words.

| What the worker says | What the interview does |
|---|---|
| "I am going to Singapore to work in construction." | Two answers, both confirmed, streamed as `slot_update` before the reply |
| "168,000 po ang sahod ko kada buwan." (no money named) | **Nothing stored**; the coach asks "Which money is that in?" (`missing_currency`) |
| "I will earn 450 Singapore dollars." (no period) | Nothing stored; "Is that amount each month, each week or each year?" (`unclear_period`) |
| "Nagbayad po ako ng 800,000 pesos sa recruiter." | Kept **unconfirmed** and asked about (`out_of_range`); the worker corrects it, or says yes and it is confirmed |
| A reading the model is unsure of (below 0.8) | Kept unconfirmed and checked ("Is that amount right?", `low_confidence`) |
| "I do not know the date yet." | The optional leaving date is recorded as declined; nothing is asked again |
| "Why do you ask?" or small talk | Nothing understood, nothing asked: the reply handles it |

## How a reading becomes an answer

`app/services/coach/extraction_checks.py` (no model, under `mypy --strict`):

| Check | Rule |
|---|---|
| Evidence | The words the model quotes must really be in the message (case and spacing aside), or the candidate is dropped |
| Number | A figure must be a number the worker wrote in those words, in any script (६२,००० is 62000), as 1.700 or 1,5, and times thousands, lakh, million or crore **only when that word is written** ("10 juta" is 10 million, never 1 million). A word number counts ("Five percent", "dalawa", "तीन") |
| A zero | A 0 or a word for none or no in the words |
| Money | The currency must be one the worker **named**, in this message or one of the two before it ("dollars" alone is not enough to know which dollars; "Singapore dollars" named a message ago is). It is never taken from the country, the language or the corridor |
| Period | Month, week or year must have been said; a total (fee, debt, savings) is always `once` whatever the model says |
| Country | Named in this message only |
| Percent | An interest needs a percent or an interest word beside the number; a count of people cannot sit beside a percent or an amount |
| Date | A year the worker wrote makes the date theirs; "20 January" is kept unconfirmed and asked about |
| Range | `range_issue` from the question bank: outside it is unconfirmed and asked about |
| Confidence | 0.8 or more is confirmed; 0.5 to 0.8 is kept and checked; under 0.5 is not used |
| Slot | Only the eleven slot names exist in the response schema; a skip rule (no debt, no interest question) is applied to what this same message says |
| Answers done | A confirmed slot is not changed by a later message; no extraction at `review` or `plan` |

A figure that cannot be checked against the words (the model read a number the words do not hold) is never confirmed: it is asked about. So the model can only *propose*, and no answer reaches the interview that the worker did not state.

## Files

| File | Change |
|---|---|
| `backend/app/prompts/coach/extract.v1.yaml` (new) | The prompt: eleven slots, strict rules (never guess, quote exactly, name the money and period only if said), the worker's text as data |
| `backend/app/schemas/coach_extraction.py` (new) | The model's raw reading (`SlotExtraction`, `SlotCandidate`, money and interest with every part optional) |
| `backend/app/services/coach/slot_extractor.py` (new) | `CoachSlotExtractor`: masks the message, sends the context (what was asked, what is unconfirmed, what is done, the last four messages, today), calls Gemini, applies the checks |
| `backend/app/services/coach/extraction_checks.py`, `extraction_cues.py` (new) | The checks above and their word lists (six languages, own script and Latin letters). Under `mypy --strict` |
| `backend/app/dependencies.py` | `get_coach_turns` passes the extractor |
| `backend/app/config.py`, `backend/.env.example` | `GEMINI_COACH_EXTRACT_TIER` (default classification) and `GEMINI_COACH_EXTRACT_THINKING_BUDGET` (default 0) |
| `backend/tests/...` | 128 new tests and the live run (below) |
| `backend/tests/fixtures/coach_extraction_recordings.json` (new, 52 KB) | What the model returned for all 12 personas, so CI replays the whole extractor with no Gemini |
| `backend/app/prompts/README.md`, `docs/api/v2-coach.md`, `docs/deferred-items.md` | The prompt row; the status; D-210 closed; D-214 and D-215 added |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched.

## Results

**Live, real Gemini (`gemini-3.1-flash-lite`), the 12 personas, 2026-10-09:**

| Run | Answers right | Invented | Follow-ups as the personas expect |
|---|---|---|---|
| First run (128 expected answers) | **128 of 128** | none | 1 difference: "I do not know the date yet" was read as an unclear answer, not a decline |
| Prompt wording for "decline" tightened, final run | **128 of 128 (100%)** | **none** | **all of them**: a missing currency (persona 9), an unclear period (persona 2), an out-of-range fee (persona 9), the optional date declined (persona 6) |

The tracker's finish line is at least 95% right and no slot filled with a value the worker did not state. Both hold, in English, Tagalog, Hindi (and Hindi to English), and Indonesian.

An earlier live attempt failed before reading anything: Gemini's schema does not accept `additionalProperties`, which `extra="forbid"` produces. The response models therefore leave extra keys ignored; what matters (the slot name) is a fixed list.

**The checks catch a model that is wrong or invents.** A test plays a model that claims all 11 answers on every one of the 140 persona messages, sure of itself and quoting the whole message; only the slots the message really states get through. The first versions of the rules let some through, and each was tightened: a country named in an earlier message, a thousands factor with no thousands word ("10 juta" read as 1 million), a number beside a percent taken as a count of people, a date matched on a stray digit. Three deliberate breaks of the checks (a currency taken with no cue, the quoted evidence not checked, the period not checked) each failed tests.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Where trust sits | The model proposes; code checks. A reading the code cannot confirm is asked about, never kept as confirmed |
| 2 | Currency | Never inferred from the destination or language (persona 9 expects a follow-up for a figure with no money). A zero needs no money, so a stored zero takes the worker's own currency, else the host country's |
| 3 | Out-of-range | Kept unconfirmed and asked about (NF-FC-001): the worker may mean it. A "yes" confirms the same value |
| 4 | Review and plan | No extraction there (answers do not move the stage; corrections are explicit moves, NF-FC-008) |
| 5 | Privacy | The message is masked (`redact_text`) before it is sent; nothing of it is logged, only counts and the follow-up reason |
| 6 | Failure | A Gemini failure while reading is an ordinary HTTP error before the stream, the turn is marked failed, nothing is stored (NF-FC-009's rule) |
| 7 | Tier | The fast tier with thinking off, a setting like the reply's (D-115). A weaker tier costs the worker a question, never a wrong figure |

## Limits (D-214, D-215)

A job type and a bank-or-wallet answer are judged by meaning, so they rest on the model's confidence and the review step. A zero is recognised by a 0 or a word for none, so the model's own reading tells "not" apart from "nothing". The cue words (money, period, country, percent, none, small numbers) are checked against the personas but not by native speakers. The extraction call runs before the reply, so it adds one fast-tier round trip to the first piece (D-211, still unmeasured).

## Manual test

```bash
cd backend
# 1. the free tests (the replay of the 12 personas included)
pytest tests/unit/services/test_coach_extraction_checks.py tests/unit/services/test_coach_extraction_personas.py tests/unit/services/test_coach_extraction_replay.py tests/unit/services/test_coach_slot_extractor.py tests/integration/api/test_coach_turns_extraction.py
# 2. the live run: about 130 calls, about 25 minutes on a free-tier key
RUN_LIVE_GEMINI=1 LIVE_SPACING_SECONDS=4 EXTRACTION_RECORD=tests/fixtures/coach_extraction_recordings.json pytest tests/integration/test_coach_extraction_live.py -v -s
```

Needs `GEMINI_API_KEY` in `.env.local` or the shell for the live run. The replay test names the prompt it was recorded with and fails when the prompt changes: record again.

## Checks run (2026-10-09)

| Check | Result |
|---|---|
| `black`, `ruff`, `mypy app`, `mypy --strict app/services` | clean |
| Backend tests | 2,801 passed, 151 skipped (the live ones); about 205 new, among them 45 on the checks, 140 on the persona messages, 5 replay, 7 on the extractor and 5 through the turn route |
| Live, 12 personas | 128 of 128 right, none invented, every follow-up as expected (above) |
| Break the checks on purpose | 3 breaks, each caught |

**Not verified:** how fast the first piece arrives with the extraction call in front of it (D-211), the cue words by native speakers (D-214), and messages beyond the 12 personas, which are the next test.

## Definition of Done (Backend, Gemini step)

- [x] Correct tier (classification) via a setting
- [x] Structured output via a Pydantic response model; no free-text parsing
- [x] Prompt in the library as a versioned file, with its variables
- [x] Failures handled (Gemini errors reach the turn; unreadable readings become follow-ups)
- [x] Tests with recorded answers, and a live run recorded here
- [x] At least 95% of slots right and none invented on the 12 personas
- [ ] First piece under 2 s with extraction in front (D-211)
- [ ] Reviewed by a teammate (Devam)

## Commit

Branch: `feature/NF-FC-010-coach-slot-extraction` (already checked out).

```bash
git commit -m "feat(coach): add slot extraction with checked answers and follow-ups" -m "Refs: NF-FC-010"
```

PR title: `feat(coach): slot extraction with checked answers and clarifying follow-ups (NF-FC-010)`
