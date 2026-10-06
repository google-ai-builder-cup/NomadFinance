# NF-F0-014 — Test harness: emulator fixtures, recorded Gemini, mock API, browser tests

## Summary

There is now one working example of each kind of test, in the place later tasks should copy from, and a "How to Test" section in the root `README.md`.

| Kind | What was added | Sample |
|---|---|---|
| Backend, Firestore emulator | Fixtures `clean_firestore`, `seed_documents`, `seeded_reference_data` in `backend/tests/integration/conftest.py` | `tests/integration/repositories/test_emulator_harness.py` |
| Backend, Gemini | `FakeGemini` that replays recorded answers (`backend/tests/fixtures/fake_gemini.py`, recordings in `tests/fixtures/gemini/`) and the fixture `recorded_gemini` | `tests/unit/test_fake_gemini.py` |
| Frontend, mocked API | MSW handlers generated from `docs/mocks/` (`frontend/src/mocks/`) | `src/hooks/useFeatureFlags.msw.test.tsx` |
| Frontend, component | React Testing Library, added in NF-F0-012 | `src/components/common/*.test.tsx` |
| Browser | Playwright project (`frontend/playwright.config.ts`, `frontend/e2e/`) and a CI job | `e2e/smoke.spec.ts` |

**The tracker said Playwright runs "against staging". Staging was dropped (`NF-F0-011-ci-staging-env.md`).** The tests run against the production build served locally by `vite preview`, with no backend and no sign-in, so they behave the same on a laptop and in CI. `PLAYWRIGHT_BASE_URL` points them at any other running copy of the app.

## A side effect worth knowing: six skipped tests now run

`backend/tests/integration/api/test_contract_e2e_mocked.py` (five countries plus the loan-agreement case) used to skip itself in CI, because the emulator there had no labor-law or complaint-template data. NF-F0-010 noted it. The fixture `seeded_reference_data` now loads the real curated files for SG, AU, KR, MY and JP, in the test process, with the same loader functions `python -m src.loaders.ilo_natlex` uses. The tests ask for the fixture instead of skipping. They are real tests in CI now, and if the data fails to load they fail instead of being skipped quietly.

## Files

| File | Purpose |
|---|---|
| `backend/tests/integration/conftest.py` (new) | The emulator fixtures |
| `backend/tests/fixtures/fake_gemini.py`, `backend/tests/fixtures/gemini/*` (new) | `FakeGemini`, `override_gemini`, `as_client`, and the recordings (`contract.detect`, `coach.reply`) with a README |
| `backend/tests/conftest.py` | The `recorded_gemini` fixture |
| `backend/tests/integration/api/test_contract_e2e_mocked.py` | Uses `seeded_reference_data` instead of skipping (8 lines added, 22 removed) |
| `backend/tests/unit/test_fake_gemini.py`, `tests/integration/repositories/test_emulator_harness.py`, `tests/unit/test_flags_mocks.py` (new) | 12, 4 and 9 tests |
| `docs/mocks/flags/*.json` (new, 4 files) | `GET /api/v2/flags`: all off, Coach on, Scam on, 401 envelope |
| `docs/mocks/README.md` | The mock file format and how the tests use it |
| `frontend/src/mocks/{files,handlers,server}.ts` and `handlers.test.ts` (new) | The MSW layer and its 13 tests |
| `frontend/src/hooks/useFeatureFlags.msw.test.tsx` (new) | The sample, 4 tests |
| `frontend/playwright.config.ts`, `frontend/e2e/smoke.spec.ts`, `frontend/e2e/tsconfig.json` (new) | The browser project, three tests run on a phone and a desktop |
| `frontend/.prettierignore` | `playwright-report`, `test-results`, `coverage`, `.vitest`, so generated output never fails `format:check` |
| `README.md` | "How to Test" |
| **Shared files** (diffs approved 2026-10-07) | `frontend/package.json` and `pnpm-lock.yaml` (`msw` 2.15.0, `@playwright/test` 1.63.0, script `test:e2e`); `.github/workflows/frontend-ci.yml` (new job `e2e`); `.gitignore` (`.vitest/`, `playwright-report/`, `test-results/`); `frontend/e2e/tsconfig.json` |

No new Python package and no change to `backend-ci.yml`.

## How to write the next test of each kind

**A service or endpoint that calls Gemini.**

```python
async def test_it(recorded_gemini):                     # recordings in tests/fixtures/gemini/
    result = await detect_contract("Salary: SGD 650", as_client(recorded_gemini))

def test_endpoint(recorded_gemini):
    app = create_app()
    override_gemini(app, recorded_gemini)               # wherever the app asks for the client
```

A recording is `<operation>.json`: `{"operation", "kind": "structured" | "text", "response" | "text" | "pieces" | "error"}`, or `responses: [...]` for several calls. A `structured` answer is validated into the call's `response_model`, so a recording that no longer fits the model fails the test. A call with no recording fails with the file name to add. Recordings are synthetic: never put a real worker's text in one. The format is in `fake_gemini.py`. The roughly ten older per-file fakes still work and were not migrated.

**A repository or endpoint that uses Firestore.**

```python
def test_it(clean_firestore, seed_documents, seeded_reference_data):
    seed_documents({"users/u1/income/i1": {"amount": 650}})
```

`clean_firestore` deletes every document through the emulator's own endpoint first. `seeded_reference_data` loads the five countries if they are missing, so it is safe after `clean_firestore` and in any order. The fixtures skip the test when no emulator is configured, and fail it if the emulator address is not on this machine.

**A screen or hook that calls the backend.**

```ts
setupMockServer();                                       // once per file; opt-in
server.use(handlerForMock("flags/flags-coach-on.json")); // or the default for that request
```

`src/hooks/useFeatureFlags.msw.test.tsx` is the working example. A request with no handler fails the test. Add a mock to `docs/mocks/<folder>/` (format in `docs/mocks/README.md`) and every handler, test and the backend's own drift check pick it up.

**A flow in a real browser.** Add `e2e/<name>.spec.ts`. Use roles and visible text, as the smoke test does.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Playwright targets the built app, not a deployed address. | Staging was dropped. A landing-and-sign-in test needs no backend, so it runs anywhere. |
| 2 | Chromium only, as a phone (Pixel 5) and a desktop. | Workers use phones first. Safari and Firefox belong to NF-HR-005. |
| 3 | `msw` is **2.15.0**, not the newest. | The 3.x line needs Node 22; CI and `engines` use Node 20 (the same trap as `jsdom`, NF-F0-012). Do not bump it until CI moves. |
| 4 | MSW is opt-in per test file (`setupMockServer()`), not global. | Existing tests that mock their own services are untouched. |
| 5 | The mock files are read with Node's file system, not Vite's `import.meta.glob`. | The folder is outside the frontend, and Vite refused `.sse` imports from there in the jsdom environment. The path comes from the working directory (`pnpm test` runs from `frontend/`), because `import.meta.url` is an `http://` address in that environment. |
| 6 | The helper is `setupMockServer`, not `useMockServer`. | ESLint reads a `use…` function as a React hook and refuses a call at the top of a file. |
| 7 | A mock without a top-level `status` (`idempotency-exchange.json`) gets no handler. | It scripts a flow of steps, not one response. |
| 8 | The `e2e` CI job is separate and is not a required check. | It overlaps the other jobs instead of lengthening them. Make it required after it has run cleanly a few times. |
| 9 | The fixtures only talk to a local emulator. | `clean_firestore` deletes everything; the emulator address must be loopback, and the clearing is an emulator-only endpoint. |

## What was verified

| Check | Result |
|---|---|
| Backend `pytest` without an emulator | 1,277 passed, 69 skipped (the emulator and live-Gemini tests), 11 s. It was 1,256 before this task |
| Backend emulator step, the command CI runs, with the `gcloud` credentials hidden as on a runner | 385 passed, 40 skipped (all live Gemini), 0 failed, 15 s including the emulator start. It was 375 passed, 46 skipped. The six end-to-end tests ran |
| Frontend `pnpm test` | 371 passed in 1.7 s (it was 354 after NF-F0-012; 17 added here) |
| `tsc -b`, `pnpm lint` (zero warnings), `pnpm format:check`, `pnpm build`, coverage gates (18.8% lines against a 15% floor), `tsc -p e2e` | clean |
| `black`, `ruff`, `mypy app`, `mypy --strict app/services` | clean |
| `pnpm test:e2e` | 6 passed (3 tests, 2 projects) in 5 s |
| Do the browser tests fail when the page is wrong? | Yes: with the heading text changed on purpose the test failed, and the spec was restored |
| Does `PLAYWRIGHT_BASE_URL` work? | Yes: pointed at an address with nothing listening, the test failed at once |
| The workflow file | Parses as YAML (checked with `js-yaml`); the `e2e` job has 8 steps |

**Not verified, because it cannot run on a laptop:** the new `e2e` job on GitHub's runner (the `--with-deps` browser install, the artifact upload on failure), and the full CI run time.

## "Total CI time under 8 minutes"

This could not be measured here. What is known:

| Piece | Measured locally |
|---|---|
| Backend tests with no emulator | 11 s |
| Backend emulator step including the emulator start | 15 s |
| Frontend unit tests | 1.7 s |
| Frontend build | 2 to 6 s |
| Playwright run (3 tests, 2 projects) | 5 s |

The slow parts of a run are the installs and the Docker image build, which were not timed. The new `e2e` job runs **in parallel** with `Frontend checks`, so it lengthens a run only if it is the slowest job. Its own cost is the install, the build and the browser download. **To check the acceptance line:** after the first push, open the pull request's checks on GitHub, note the duration of each job and use the longest, since they run side by side. If it is over 8 minutes, the first things to look at are the backend image build and `playwright install --with-deps`, which can be cached.

## Definition of Done

- [x] One sample test of each kind green locally: backend emulator, recorded Gemini, mocked API with component test, browser
- [ ] One sample test of each kind green **in CI**: wired (the backend emulator step already runs the new tests, the browser job is added), not yet seen run
- [x] README "How to Test" section added
- [ ] Total CI time under 8 minutes: not measured, see above
- [x] Fixtures documented here and in `docs/mocks/README.md`
- [ ] Reviewed by a teammate

## Commit

Branch: `test/NF-F0-014-test-harness`.

```bash
git commit -m "test(harness): add emulator fixtures, fake Gemini, MSW and Playwright" -m "Refs: NF-F0-014"
```

PR title: `test(harness): emulator fixtures, recorded Gemini, mock API and browser tests (NF-F0-014)`

## Noticed, not fixed

- The backend virtual environment used for these runs lacks `pytest-cov` (it is in `requirements-dev.txt`), so `pytest --cov` fails there until `pip install -r requirements-dev.txt`. CI installs it.
- Chromium was installed into the user cache for the Playwright run (94 MB, `~/Library/Caches/ms-playwright`). Nothing system-wide.
- `FakeGemini` has no "record" mode that captures a real answer, since that needs a key and quota. Recordings are written by hand from the response models.
