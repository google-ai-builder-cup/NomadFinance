# Contributing

Humans write every commit and press every git button. The history carries the task id and nothing else about how a change was made. Two things enforce that: **pre-commit hooks** on your machine and a **commit check in CI** that re-runs on every commit of a pull request.

## One-time setup

You need Python 3.11, Node 22.12 or newer, and pnpm 10.

```bash
pip install -r backend/requirements-dev.txt   # ruff, black and mypy at the CI pins
pip install pre-commit==4.6.2
(cd frontend && pnpm install)                 # eslint and prettier, used by the hooks
pre-commit install                            # installs the pre-commit and commit-msg hooks
```

On Windows PowerShell, run the second block as separate lines: `cd frontend; pnpm install; cd ..`.

The first commit after `pre-commit install` is slow: pre-commit builds its tool environments once and reuses them. `pre-commit install` keeps any commit-msg hook you already had and runs it after commitlint.

## What runs when you commit

| Hook | Runs on | Does |
|---|---|---|
| ruff | `backend/`, `data-scripts/` Python | Lints and fixes what it can (same version as CI) |
| black | the same files | Formats with `backend/pyproject.toml` (line length 100); uses the black you installed above |
| gitleaks | the staged changes | Blocks a commit that adds a key, token or private key |
| eslint | `frontend/` `.ts` and `.tsx` | Same flags as `pnpm lint`, zero warnings allowed |
| prettier | `frontend/` | Formats, keeping each file's line endings (a Windows checkout is CRLF) |
| commitlint | the commit message | Enforces the message rules below |

A hook that rewrites a file (ruff, black, prettier) stops the commit. Look at the change, `git add` the file again, and commit again.

Run everything on all files without committing: `pre-commit run --all-files` (this rewrites files the formatters would change). Run one hook: `pre-commit run <hook id> --files <paths>`.

## Commit messages

```
<type>(<scope>): <imperative summary>
Refs: NF-XXX-NNN
```

| Rule | Detail |
|---|---|
| Type | `feat`, `fix`, `docs`, `chore`, `refactor`, `perf`, `test`, `build`, `ci`, `style`, `revert`, in lower case |
| Scope | Required, in kebab-case: `feat(flags)`, `docs(data-model)` |
| Subject | Imperative, starts lower case, no full stop |
| Header | At most **72 characters** in all, including the type and scope |
| Body | Optional, after a blank line, explains why |
| Trailer | **`Refs:` is the only trailer.** `Refs: NF-F0-009` or `Refs: NF-F0-009, NF-P4-004`. Put it under the subject (or at the end of the body). |

Every other trailer is refused: `Co-authored-by`, `Signed-off-by`, `Fixes`, `Generated-by`, session or tool lines, anything of the form `Name: value` that is not `Refs:`. The check is an allow-list on purpose, so it needs no list of names to forbid and nothing new can slip through. In a body, avoid a line that begins `Word:` when it is the last paragraph; reword it.

Merge commits made by GitHub or `git merge` (`Merge pull request ...`, `Merge branch ...`) are skipped.

Accepted:

```
feat(flags): add feature flag service and require_flag dependency
Refs: NF-F0-005
```

Refused, with the reason the hook prints:

| Message | Why |
|---|---|
| `Update stuff` | no type, no scope |
| `feat: add y` | scope missing |
| `feat(x): Add y.` | starts upper case, ends with a full stop |
| `wip(x): add y` | `wip` is not a type |
| `feat(x): add y` then `Co-authored-by: A <a@b.c>` | only `Refs:` is allowed as a trailer |
| `feat(x): add y` then `Refs: 12` | a Refs value must be a task id such as `NF-F0-009` |

If a message is refused, fix it and commit again: the commit was not made. For the last commit use `git commit --amend`; for earlier commits in a branch, an interactive rebase. Both are yours to run.

## In CI

`.github/workflows/commit-policy.yml` runs commitlint, the same config at the same version, over **every commit between `main` and the head of your pull request**. `git commit --no-verify` skips the local hooks but not this check, so a bad message fails the pull request instead. Fix it by rewriting the branch's commits and pushing again.

## Checks a pull request must pass

Five checks run on every pull request, and `main` accepts a merge only when all of them are green, the branch is up to date with `main` and a teammate has approved (branch protection, NF-F0-010; settings in `docs/runbooks/NF-F0-010-ci-test-gates.md`).

| Check | What it runs | Run it yourself |
|---|---|---|
| Backend checks | ruff, black, mypy, pytest, the tests that need the Firestore emulator, the coverage gate, the Docker build | from `backend/`: `ruff check .`, `black --check .`, `mypy app`, `pytest -q` |
| Frontend checks | eslint, prettier, vitest with coverage, `tsc` and the build | from `frontend/`: `pnpm lint`, `pnpm format:check`, `pnpm test:coverage`, `pnpm build` |
| Frontend rules tests | The Firestore and Storage rules on the emulators | `pnpm test:rules` |
| Data scripts checks | ruff, black, mypy, pytest and the dry runs | from `data-scripts/` |
| Commit policy | commitlint over every commit of the pull request | see "Commit messages" |

**Coverage.** Every `backend/app/<package>` your pull request changes must have 70% of its statements covered, and `app/` as a whole 93% (`backend/scripts/check_coverage.py`). On the frontend, floors are set in `frontend/vite.config.ts` (15% overall, 70% for `src/utils`, 35% for `src/lib`): most screens have no unit test yet, so these stop coverage from collapsing and are raised as tests are added. To see your own numbers, from `backend/`: `pytest --cov=app --cov-report=term-missing`.

**The emulator tests.** The repository and end-to-end tests skip themselves when no Firestore emulator is running, so a plain `pytest` leaves about 19 of them out. CI runs them with `firebase emulators:exec` (see `.github/workflows/backend-ci.yml`); to do the same, from `backend/`: `firebase emulators:exec --only firestore,auth --project demo-nomadfinance --config ../frontend/firebase.json "python -m pytest tests/integration -q"`. Run only `tests/integration` that way: the configuration unit tests deliberately refuse emulator variables.

## Secrets

The gitleaks hook stops a key before it is committed; if it blocks something that is not a secret (a placeholder, a test value), change the value to an obvious placeholder first. If it must stay, add its fingerprint (printed by the hook) to a `.gitleaksignore` file and say why in the pull request. Never commit `.env` files; only `.env.example` carries placeholder names.

If gitleaks reports a real key, treat it as leaked: rotate it, even if you never push.

## Branches and pull requests

Branch from a fresh `main` using the branch named in the task: `feature/`, `fix/`, `chore/`, `docs/` or `test/` followed by the task id and a short name, for example `chore/NF-F0-009-ci-commit-policy`. Aim for under 400 changed lines per pull request. Fill in the pull request template, including the task id.
