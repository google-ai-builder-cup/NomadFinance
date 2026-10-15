# NF-F0-010 — CI test and coverage gates, CODEOWNERS, pull request template

## Summary

A pull request can now be stopped by a failing test, a low-coverage package, a bad commit message, a missing review or an out-of-date branch. The gates are in place and were run locally; **they only force anything once branch protection is switched on (steps below, D-116), which needs a repository admin and has to come after this pull request has run its checks once.**

| Stops a merge when | Enforced by |
|---|---|
| Lint, format, types or any test fails (backend, frontend, rules, data scripts) | The four CI jobs, once required |
| A changed `backend/app/<package>` is under 70% covered, or `app/` is under 93% | `backend/scripts/check_coverage.py` in Backend checks |
| Frontend coverage falls under its floors | `coverage.thresholds` in `frontend/vite.config.ts`, run by Frontend checks |
| A commit message breaks the policy | Commit policy |
| No teammate has approved, the approval is stale, or the branch is behind `main` | Branch protection, with `.github/CODEOWNERS` |

## What was measured first (2026-10-06)

The gates are set against real numbers, not guesses.

**Backend** (line coverage of `app/`):

| Run | Total | Weakest package |
|---|---|---|
| `pytest` as CI ran it before | 95.7% | `app/repositories` **63.0%** |
| plus the tests that need the Firestore emulator (what CI runs now) | **96.9%** | `app/repositories` 80.6%, next `app/integrations` 93.8% |

About 19 repository and end-to-end tests skip themselves without an emulator, so CI never ran them, and a 70% rule on a changed package would have blocked every pull request touching `app/repositories`. The emulator step fixes both.

**Frontend** (`vitest`, v8 coverage): **16.7% of lines** overall. `src/utils` 78%, `src/lib` 40%, services 9%, hooks 7%, components 7%, pages 0%. Most screens have no unit test, so a 70% frontend gate is not possible; the floors below only stop it falling (D-118).

## The gates

| Where | Rule |
|---|---|
| Backend, changed package | At least **70%** of statements covered, for every `backend/app/<package>` the pull request touches (a new package with no tests counts as 0%) |
| Backend, total | At least **93%** (measured 96.9%) |
| Frontend, overall | Lines and statements 15%, functions 13%, branches 15% (measured 16.7 / 16.7 / 15.1 / 17.7) |
| Frontend, `src/utils/**` | 70% (measured 78%) |
| Frontend, `src/lib/**` | 35% (measured 40%) |

"Coverage drop" is a fixed floor, not a comparison with `main` (D-119). Type checks: `mypy app` runs in Backend checks and `tsc -b` inside `pnpm build` in Frontend checks; both existed already.

## Run the gates yourself

Do this before pushing, so GitHub holds no surprises. No environment variable or secret is needed: CI uses placeholder Firebase values, and your own `.env.local` files stay as they are. PowerShell, from the repository root.

**Backend** (from `backend/`, virtual environment active). `pytest-cov` and `coverage` are new dev dependencies, so install them once:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

What CI runs, in its order. Each command should finish clean (about 1,245 tests pass without the emulator):

```powershell
ruff check .
black --check .
mypy app
pytest -q --cov=app --cov-report=
```

Then the tests that need the Firestore emulator, adding to the same coverage data. First check that no emulator from an earlier run still holds the ports (the command prints nothing when they are free; if it prints a line, stop that process with `taskkill /PID <last number> /F`, the known Windows leftover, D-34):

```powershell
netstat -ano | findstr ":8085 :9099"
firebase emulators:exec --only firestore,auth --project demo-nomadfinance --config ../frontend/firebase.json "python -m pytest tests/integration -q --cov=app --cov-append --cov-report="
```

About 375 pass and none fail. Then the gate itself; it ends with `app (total) ... 96.9% ... 93%` and no `FAIL` line:

```powershell
coverage json -o coverage.json
python scripts/check_coverage.py coverage.json
```

To see what a pull request changing one package would be judged on, list its files in a text file and pass it: `python scripts/check_coverage.py coverage.json --changed-list changed.txt` (one path per line, as `git diff --name-only` prints them). `.coverage` and `coverage.json` are git-ignored. To see which lines are untested: `pytest --cov=app --cov-report=term-missing`.

**Frontend** (from `frontend/`):

```powershell
cd ..\frontend
pnpm install --frozen-lockfile
pnpm test:coverage
pnpm lint
pnpm build
```

All tests pass and the line summary is about 16 to 17% (floors in `vite.config.ts`). If `pnpm` itself fails with `error: CommandNotFound`, see the table below: use `npx --yes pnpm@10` instead. If `pnpm install --frozen-lockfile` says the lock file does not match `package.json`, do not edit the lock file by hand; tell the task owner. `pnpm format:check` fails on Windows because of line endings (D-21); the Linux check in CI is the one that counts. The rules tests are unchanged: `pnpm test:rules`.

| Symptom | Cause and fix |
|---|---|
| `pnpm ...` prints `error: CommandNotFound` | Either you are in the wrong folder (the `pnpm` scripts exist only in `frontend/`, not in `backend/` or the repository root), or the `pnpm` command on this machine is a broken shim. In `frontend/`, put `npx --yes pnpm@10` in front instead: `npx --yes pnpm@10 install --frozen-lockfile`, `npx --yes pnpm@10 test:coverage`, `npx --yes pnpm@10 lint`, `npx --yes pnpm@10 build`. The repository's own launch config does the same. CI is not affected: it installs pnpm 10 itself |
| `Could not start Firestore Emulator, port taken` | An emulator from an earlier run is still alive. Find it with the `netstat` line above and stop it |
| 6 tests in `tests/unit/test_config.py` fail while the emulator is running | They test that a deployed environment refuses emulator variables, so they cannot run under the emulator. CI runs only `tests/integration` there. Run the unit tests without it |
| The coverage gate says a package is under 70% | Add tests for what you changed, or run `pytest --cov=app --cov-report=term-missing` to see the uncovered lines |
| `No test files found` from `pnpm test:rules` | `include` in `frontend/vite.config.ts` must list `tests/**/*.test.ts` as well as `src` |

## Branch protection (to do: repository admin)

**Order matters.** A required check can only be selected after it has run once, and requiring one that does not exist blocks the very pull request that adds it. So: merge this pull request, let the checks run on it (they run on the pull request itself), then set this up.

The rule for `main` (click path under "Steps in GitHub" below):

| Setting | Value |
|---|---|
| Require a pull request before merging | on |
| Required approvals | **1** |
| Dismiss stale pull request approvals when new commits are pushed | on |
| Require review from Code Owners | on |
| Require approval of the most recent reviewable push | on (the author cannot push after the review and merge) |
| Require status checks to pass | on |
| Require branches to be up to date before merging | **on** (this is the stale-branch rule) |
| Required checks | `Backend checks`, `Frontend checks`, `Frontend rules tests`, `Data scripts checks`, `Commit policy` |
| Require conversation resolution | on |
| Block force pushes, restrict deletions | on |
| Do not allow bypassing the above | on, once the team is used to it |

Not required on purpose: **Security scan** (D-120). A new advisory in a dependency, unrelated to a pull request, would block every merge. The check names above are the job names in the workflows; they are distinct on purpose, because GitHub identifies a required check by its job name and three jobs were all called `checks`.

Merge method: the repository uses merge commits ("Merge pull request #n"), which commitlint skips. Squash would rewrite the message the policy checks.

### Steps in GitHub

Needs repository admin rights.

1. **Repo, Settings, Rules, Rulesets, New ruleset, New branch ruleset.**
2. Name it `main protection`; **Enforcement status: Active**.
3. **Target branches:** Add target, **Include default branch**.
4. Turn on **Restrict deletions** and **Block force pushes**.
5. Turn on **Require a pull request before merging**, and inside it: required approvals **1**; dismiss stale approvals when new commits are pushed; **Require review from Code Owners**; require approval of the most recent reviewable push; require conversation resolution.
6. Turn on **Require status checks to pass**, and inside it: **Require branches to be up to date before merging**; add the five checks above (type the name in the search box; a check that is not offered has not run on a pull request yet).
7. Leave the **bypass list** empty and save.

### Check that it works

Open a small throwaway pull request (a one-word fix in a doc). Confirm that the Merge button is blocked until a teammate approves and the five checks pass, and that after another pull request merges, GitHub shows the branch as out of date and asks for an update. Then record it under "Rollout" below.

## What changed

| File | Change |
|---|---|
| `backend/scripts/check_coverage.py` (new) | The coverage gate: per changed package and total; writes a table to the job summary. Standard library only |
| `backend/tests/unit/scripts/test_check_coverage.py` (new) | 22 tests |
| `.github/workflows/backend-ci.yml` (**shared**) | Runs for every pull request; full history; `pytest --cov`; then the integration tests under `firebase emulators:exec` with coverage appended; then the gate; job named `Backend checks` |
| `.github/workflows/frontend-ci.yml` (**shared**) | Runs for every pull request; vitest with coverage before the build, with the placeholder Firebase env at job level; jobs named `Frontend checks` and `Frontend rules tests` |
| `.github/workflows/data-ci.yml` (**shared**) | Runs for every pull request; job named `Data scripts checks` |
| `.github/workflows/commit-policy.yml` (new, **shared**) | commitlint 21.2.3 over every commit of the pull request. It was written for NF-F0-009 but not merged with it |
| `backend/requirements-dev.txt`, `backend/pyproject.toml` (**shared**) | `pytest-cov==7.1.0`, `coverage==7.16.2`; `[tool.coverage.run] source = ["app"]` |
| `frontend/package.json`, `frontend/pnpm-lock.yaml` (**shared**) | `pnpm test`, `pnpm test:coverage`; `@vitest/coverage-v8@5.0.2` (the lock file gains that package and 7 it needs, nothing else moved) |
| `frontend/vite.config.ts` | vitest `include` and the coverage floors |
| `.gitignore` (**shared**) | `coverage/`, `coverage.json` |
| `backend/tests/integration/api/test_cors_rate_limit.py` | One test now clears the emulator variables: a deployed environment refuses to start with them (NF-P4-004), so it failed whenever the emulator was running |
| `.github/CODEOWNERS`, `.github/pull_request_template.md` | See below |
| `docs/CONTRIBUTING.md` | A "Checks a pull request must pass" section; D-46 closed, D-116 to D-120 |

Only pushes and pull requests that change a folder used to start its CI. The `paths` filter is gone for **pull requests** (three workflows), because a required check that does not run leaves a docs-only pull request "waiting for status" for ever. Pushes to `main` keep their filters. The repository is public, so the extra minutes cost nothing.

## CODEOWNERS and the pull request template

- **CODEOWNERS.** All three of us own everything; GitHub never asks the author to review, so the other two are requested. "Require review from Code Owners" turns that into a rule. Sensitive paths (workflows, `core/`, config, dependencies, the Dockerfile, the rules and index files, `firebase.json`, infra, the commit policy) are listed separately, with the same owners, so the rule is visible and one line changes if ownership splits. **It cannot name "the right reviewer"**: the tracker rotates the reviewer per task and work is not divided by code area. The template asks for the tracker's reviewer by name instead.
- **Template.** Task, owner and reviewer; what and why; testing steps; screenshots; rollout and rollback (flag and how to undo it); a checklist (which items CI enforces and which are by hand, shared-file approval, runbook); and the tracker's Definition of Done for each kind of task as collapsible lists to keep the one that applies.

## Verified (2026-10-06)

| Check | Result |
|---|---|
| Whole backend sequence, in the workflow's order, from `backend/` | plain `pytest --cov`: 1,245 passed, 71 skipped; integration tests under the emulator with `--config ../frontend/firebase.json`: **375 passed, 0 failed** (the failing test is fixed); combined 96.9%; gate exit 0 |
| Gate on the real report | Passes at 70%; with the package minimum at 85% it fails on `app/repositories` (80.6%) and names it |
| `check_coverage.py` | 22 tests; ruff, black, mypy clean |
| Frontend coverage config | In a scratch copy with the provider installed: all 303 tests pass at 16.7%; raising the floors makes it exit 1 with a message per threshold |
| Real `frontend/` | `tsc -b`, eslint, prettier, 303 tests and `vite build` pass; the rules suite under the emulator: 186 passed |
| All workflow files | Parse as YAML; every job has a unique name |
| Caught on the way | Limiting vitest to `src/` would have made `pnpm test:rules` find no files; `include` now covers `tests/` too, and the rules suite still runs |

**Not verified: any run on GitHub.** I cannot run Actions from here, and I have no `gh` access to read or set branch protection. Watch the first pull request (D-117): the emulator step's `--config` path, the commit-policy range, and the backend job's time (now with an emulator, probably 4 to 6 minutes).

## Rollout: what the task owner does, in order

Ticked items are done; the rest are for the owner, in this order.

- [x] Gates, workflows, template, CODEOWNERS and docs written (branch `chore/NF-F0-010-ci-test-gates`)
- [x] Verified locally: the whole backend sequence including the emulator step and the gate; frontend coverage, lint, type check, build and the rules suite (see "Verified")
- [ ] **Run the gates yourself** (section above)
- [ ] **Commit and push.** Two commits keep the history readable (`git add` the workflow and code files, then the docs and templates):
  - `chore(ci): add coverage gates, emulator tests and a commit-policy check` with `Refs: NF-F0-010`
  - `docs(ci): add CODEOWNERS, PR template and CI contributor guide` with `Refs: NF-F0-010`
  - `git push -u origin chore/NF-F0-010-ci-test-gates`
- [ ] **Open the pull request into `main`** and fill in the new template
- [ ] **Watch the first run** on the pull request's Checks tab: `Backend checks`, `Frontend checks`, `Frontend rules tests`, `Data scripts checks` and `Commit policy` must appear and go green (`Security scan` may be red for an unrelated advisory). Things that could only be checked on GitHub, and the first place to look if a check is red: the `--config ../frontend/firebase.json` path of the emulator step, the commitlint range, and the backend job's time (now 4 to 6 minutes). Copy the failing step's log into the pull request or to the task owner
- [ ] **A teammate reviews** (the tracker names Pranjal); CODEOWNERS requests the others automatically
- [ ] **Merge** with a normal merge commit
- [ ] **Set branch protection** (steps above, repository admin), then **check it works** with a throwaway pull request
- [ ] **Record it:** mark D-116 and D-117 Done with the date in and tick the two open boxes in the Definition of Done below

## If a check is red on a pull request

| Check | What it means and what to do |
|---|---|
| Backend checks, step ruff, black or mypy | Run the same command from `backend/` and fix what it names |
| Backend checks, a test fails | Run that test locally. If it only fails in CI, check whether it needs the emulator (it then belongs in `tests/integration`) |
| Backend checks, Coverage gate | The table in the job summary shows the package under 70% or the total under 93%. Add tests for the code you changed |
| Frontend checks, Unit tests with coverage | `ERROR: Coverage for ... does not meet ... threshold` names the floor; add tests rather than lowering it. Floors are raised, not lowered, as tests are added (D-118) |
| Frontend checks, install | `pnpm-lock.yaml` and `package.json` disagree; regenerate the lock file with `pnpm install` and commit it (a shared file: show the diff first) |
| Frontend rules tests | `pnpm test:rules` locally; a rule or its test changed |
| Data scripts checks | The same commands from `data-scripts/` |
| Commit policy | A commit in the branch breaks the message rules (type and scope, 72 characters, only a `Refs:` trailer). Rewrite that commit (`git commit --amend`, or an interactive rebase for older ones) and push again; see `docs/CONTRIBUTING.md` |
| Security scan | Not required. A new advisory in a dependency: fix it in its own change |

## Definition of Done

- [x] pytest with coverage; fails under 70% on a changed backend package (and under 93% overall)
- [x] vitest with coverage and floors; type checks (mypy, tsc) already in the jobs
- [x] CODEOWNERS and the pull request template with the Definition of Done checklists
- [x] Gates demonstrated to fail: the coverage gate on the real report, the frontend floors in a scratch copy
- [ ] Branch protection set on GitHub (D-116, repository admin, after the first run)
- [ ] CI jobs seen green on GitHub (D-117)
- [ ] Reviewed by Pranjal
