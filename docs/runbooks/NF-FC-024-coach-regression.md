# NF-FC-024 — Coach multi-turn regression suite

## Summary

`python -m tests.regression.run_coach_regression` (from `backend/`) plays the twelve personas of NF-FC-007 through the real Coach routes, one after another, and writes a report to `docs/evals/coach-regression-<date>.md`. A manual GitHub workflow (**Coach regression**, Actions tab) runs the same command.

For each persona it starts a new session (`restart: true`), lets the coach speak first, types the persona's messages in order, confirms the review, asks for the plan, and then checks:

| Check | Held against |
|---|---|
| **Turn count** | `expected_turn_count` (the `done` event of the last message) |
| **Slot values** | `expected_slots`: every slot equal, every one confirmed, and no slot filled that the persona never states (the interest of a debt of zero, a leaving date it does not know) |
| **Score band** | `expected_score.band`, on the session and again on the plan. The total is shown next to the expected one, not gated: the stored totals use fixed rates and the run uses the live ones |
| **Plan** | stored (200 or 201), 13 weeks, the "not professional financial advice" note, the right language and corridor, made from the persona's answers |
| **Follow-ups** | a message the persona file marks as needing a follow-up (`unclear_period`, `missing_currency`, `out_of_range`) must store nothing |

"Plan validator pass" is read from the route: it refuses (502 `ai_bad_response`) and stores nothing when the plan fails its figure and sentence checks twice, so a stored plan is one that passed (D-260).

- **Exit code 0**: all personas passed. **1**: at least one did not (the report is written either way). **2**: the run could not start: no token, a server that cannot be reached, or an account the `coach` flag is not on for.
- The report has the verdict on top, the run, one row per persona (turns, band, score, plan, retries, time), the problems of each failing persona, the time to the first word of a reply, token usage, and every request id.

Not in this task: the Playwright journey (NF-FC-025), the feature documentation (NF-FC-026), any change to application code.

**There is no live run yet** (D-258): it needs a test account, three repository settings and real Gemini quota. Everything below was checked against a stand-in server and against the real routes with Gemini replaced.

## There is no staging

The tracker says "on staging". Staging was dropped (`NF-F0-011-ci-staging-env.md`): the run goes against **production**, on a dedicated test account on which the `coach` flag is on for its uid only (`docs/data-model/collections/config.md`, `allow_uids`). The runner takes any address, so it also works against the local backend and the emulators:

```bash
python -m tests.regression.run_coach_regression --base-url http://127.0.0.1:8080 --only p10_jp_ph_miguel
```

A token is only ever sent over `https`, or to this machine; any other `http` address is refused.

## What the account needs

- The `coach` flag on for its uid.
- **No analysed contract and no Financial Identity entries.** The Coach would offer them (`known`, and the contract question of NF-FC-015) and the turn counts would no longer be the personas'. The runner drops an offered `known` before the first question, but cannot undo a contract question.
- An ID token that lasts the run (about 20 minutes at the default pace). A Firebase ID token lasts one hour.

## Run it by hand

The token goes in `COACH_EVAL_ID_TOKEN`, never in an option, so it stays out of the shell history and the process list.

PowerShell, from `backend\`:

```powershell
.\.venv\Scripts\Activate.ps1
$env:COACH_EVAL_ID_TOKEN = "<id token of the test account>"
python -m tests.regression.run_coach_regression --base-url https://<the API address> --only p10_jp_ph_miguel
```

bash:

```bash
source .venv/Scripts/activate        # Linux and macOS: .venv/bin/activate
export COACH_EVAL_ID_TOKEN="<id token of the test account>"
python -m tests.regression.run_coach_regression --base-url https://<the API address> --only p10_jp_ph_miguel
```

1. **Try one persona first** (`--only`). It runs about 2 minutes and prints each result; a partial run writes no report unless you give `--report`.
2. **Run all twelve** (no `--only`): about 160 calls at 9 a minute, 20 minutes. One line per persona as it finishes, then the report path.
3. **Read the report**, start with the failures; commit it. The first one is the baseline.

| Option | Meaning |
|---|---|
| `--base-url URL` | The server (default `COACH_EVAL_BASE_URL`, else `http://127.0.0.1:8080`) |
| `--only ID` | Run this persona only (repeatable) |
| `--report PATH` | Write the report here (default `docs/evals/coach-regression-<date>.md`) |
| `--usage-log PATH` | A Cloud Logging export of the run's `gemini_call` lines, for the token table |
| `--rpm N` | Gemini-spending calls a minute (default 9; the server allows 10 a worker) |
| `--plan-language L` | Language of the plan and its PDF (default `en`) |

### Getting an ID token

Sign in to the app with the test account, then in the browser's developer tools open Application → IndexedDB → `firebaseLocalStorageDb` and copy `stsTokenManager.accessToken` (the ID token) and `stsTokenManager.refreshToken`. Keep the refresh token for the workflow (below). A fresh ID token from a refresh token:

```bash
curl -s "https://securetoken.googleapis.com/v1/token?key=$FIREBASE_WEB_API_KEY" \
  -d grant_type=refresh_token --data-urlencode "refresh_token=$REFRESH_TOKEN"
```

## Token usage

No API answer carries token counts (the contract hides model details). The runner records the `X-Request-ID` of every call, and the server logs one `gemini_call` line per Gemini call with that id. With no log file the report prints this command, filled in with the account's hashed uid (read from the token's claims) and the start time:

```bash
gcloud logging read 'jsonPayload.message=~"^gemini_call " AND jsonPayload.uid_hash="<hash>" AND timestamp>="<start>"' \
  --project nomadfinance-prod --format=json > coach-usage.json
```

Run the report again with `--usage-log coach-usage.json` (the same command, `--only` not needed) and the token table fills in per persona. The workflow cannot do this step: it has no Google Cloud login (D-259).

## The manual workflow

`.github/workflows/coach-regression.yml` (**Coach regression**, Actions tab, "Run workflow"; listed once it is on `main`). Inputs: `only` (one persona, or empty for all) and `plan_language`. It installs `backend/requirements.txt`, exchanges the test account's refresh token for a fresh ID token (masked in the log), runs the command and attaches the report whether or not the run passed. Needs:

| Setting | Kind | Holds |
|---|---|---|
| `COACH_EVAL_REFRESH_TOKEN` | repository secret | The test account's refresh token |
| `COACH_EVAL_FIREBASE_WEB_API_KEY` | repository secret | The project's web API key (to exchange the refresh token) |
| `COACH_EVAL_BASE_URL` | repository variable | The API address (https) |

It is not a required check and is not scheduled: "nightly" in the tracker is a button, as the task says ("manual-dispatch"), because a run spends real Gemini quota.

## Files

| File | Change |
|---|---|
| `backend/tests/regression/coach_client.py` (new) | The routes as the screens call them: the stream reader, the idempotency key and the resend of a dropped stream, the pacing, the plan's wait |
| `backend/tests/regression/coach_replay.py` (new) | One persona, from a new session to a stored plan; the leaving date moved to the day of the run |
| `backend/tests/regression/coach_dates.py` (new) | Moves a date in the persona's own words (English, Hindi, Indonesian month names) by the same number of days for everyone |
| `backend/tests/regression/coach_checks.py` (new) | The checks above, each returning plain sentences |
| `backend/tests/regression/coach_report.py` (new) | The report, and the token table from a log export |
| `backend/tests/regression/run_coach_regression.py` (new) | The command |
| `backend/tests/fixtures/coach_regression_server.py` (new) | A stand-in server that follows the contract, with switches to break it |
| `backend/tests/unit/test_coach_regression.py` (new) | 28 tests: the client, the checks, the dates, each way of breaking the server |
| `backend/tests/unit/test_coach_regression_report.py` (new) | 9 tests: the report, the token table, the command and its exit codes |
| `backend/tests/integration/api/test_coach_regression_routes.py` (new) | 3 tests against the real routes, Gemini replaced |
| `.github/workflows/coach-regression.yml` (new, **shared path, approved before it was written**) | The manual job |
| `docs/deferred-items.md` | D-203 closed; D-258 to D-260 added |

No change to `requirements*.txt` (`httpx` and `pydantic` are already pinned), `pyproject.toml`, any other workflow, or application code.

## Decisions that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Where the runner lives | `backend/tests/regression/`, next to the persona fixtures it reads, rather than `data-scripts/`, whose requirements have no `httpx` (that would have been a shared-file change) |
| 2 | Leaving dates (D-203) | Moved to the day of the run: `today + (original − 2026-10-09)`, written the way the persona wrote it. Every night is the same test, whatever the clock |
| 3 | Pace | 9 Gemini-spending calls a minute for one account, because the server allows 10 a minute per worker; the opening turn and the plan count. A 429 or a busy answer is waited for, not failed |
| 4 | A retry | A dropped stream, an `error` event, `ai_busy` and its kin are sent again with the **same key**, up to 3 times, as the contract says a client must; the report shows how many retries a persona needed |
| 5 | A setup problem stops the run | 401, 403 or 404 on the first `POST /sessions`, or a server that cannot be reached, ends the run with exit 2 instead of failing twelve personas for one reason |
| 6 | Token from the environment | Not an option, so it is not in a shell history or a process list. Logged nowhere |
| 7 | The ID token is minted in the workflow | A stored ID token would be an hour old; the refresh token is exchanged at the start of each run |
| 8 | The band is gated, the total is not | Live rates move the total (D-258) |

## Checks run (2026-10-10)

| Check | Result |
|---|---|
| New tests | **40 passed** (37 unit, 3 against the real routes) |
| Backend suite (`pytest tests`) | **3,608 passed, 172 skipped, 0 failed** |
| `black --check`, `ruff check`, `mypy` on the new files | clean |
| **The tests fail when the runner is broken** (one deliberate break at a time, restored after) | Band check removed: 1 test failed. Slot comparison removed: 1. Turn count check removed: 3. Follow-up check removed: 1 |
| The stand-in server broken in nine ways (a wrong slot, an extra slot, a wrong turn count, a wrong band, a filled follow-up, a refused plan, a bad plan, no access, a dropped stream) | Each is reported against the persona it hits |
| The workflow | The YAML parses; the shell part of the job was syntax-checked. **Not dispatched** (it is not on `main`, and needs the three settings) |
| `python -m tests.regression.run_coach_regression` with no token | prints the reason, exit 2 |

**Not verified:** a run against a live server with real Gemini (so no report and no 12 / 12, D-258); the token log export (D-259); the workflow itself.

## Definition of Done (Test-only / QA task)

- [x] **The test fails when the behaviour is broken**: shown above, for each check and for the exit codes.
- [ ] **Passes in CI**: the 40 tests run in the backend CI with the rest of the suite; the workflow has not been dispatched.
- [x] Bugs found are filed with severity: none in the code under test. The runner's first run against the real server may find some (D-258).
- [ ] **Report committed under `docs/evals`**: not done, it needs the live run (D-258).
- [ ] Tracker finish line "12 / 12 personas pass": not shown yet, same reason.

## Noticed, not fixed

- D-205 still stands: no persona for KR, HK, Nepali or Bengali.
- `starlette.testclient` prints a deprecation warning about `httpx` at the start of every test run (`install httpx2 instead`). It comes from a dependency and does not fail anything; worth a look when the pins are next reviewed.

## Commit

Branch: `test/NF-FC-024-test-coach-regression` (already created).

Commit message:

```
test(coach): add multi-turn persona regression runner
Refs: NF-FC-024
```
