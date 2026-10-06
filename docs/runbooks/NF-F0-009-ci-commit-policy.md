# NF-F0-009 — Commit policy guardrails (commitlint + pre-commit + CI)

## Summary

Three layers keep commit messages and code hygiene consistent without naming any tool in the config:

| Layer | Where | Catches |
|---|---|---|
| commit-msg hook | `.pre-commit-config.yaml` → `commitlint.config.cjs` | A non-conventional subject, a header over 72 characters, any trailer except `Refs:` |
| pre-commit hooks | `.pre-commit-config.yaml` | ruff, black, eslint, prettier, gitleaks on what is staged |
| CI job | `.github/workflows/commit-policy.yml` | The same commitlint check over every commit in a pull request, so `--no-verify` does not get past it |

Setup and the message rules are in [docs/CONTRIBUTING.md](../CONTRIBUTING.md).

## The allow-list

`commitlint.config.cjs` has one custom rule, `trailer-allow-list`. It rejects **every** trailer except `Refs: NF-XXX-NNN` (comma-separated for several), so the config contains no author, tool or service name to forbid and a new tool's trailer is refused without a change.

- A line is trailer-shaped when it reads `Key: value` or `Key #123`.
- It checks the last paragraph of the message, and any hyphenated `Some-Key:` line anywhere in the body (so `Co-authored-by` cannot hide above a closing sentence).
- The repo writes `Refs:` directly under the subject with no blank line, so the rule does not rely on commitlint's footer parsing, which would not see it. `body-leading-blank` and the footer rules are therefore off.
- `Refs` must be spelled exactly so, and its value must match `NF-<2 letters or digits>-<3 digits>`.

**Limits.** Free text is not a trailer, so a line such as "generated with ..." is not caught; neither is a URL in the body. The reviewer and the pull request template ("No AI attribution") still cover that. Merge commits (`Merge pull request`, `Merge branch`) and `Revert` messages are skipped by commitlint's defaults.

## Rules chosen

| Rule | Value | Source |
|---|---|---|
| type | feat, fix, docs, chore, refactor, perf, test, build, ci, style, revert | Conventional Commits, as the repo already uses |
| scope | required, kebab-case | CLAUDE.md format `<type>(<scope>): ...`; every earlier commit has one |
| subject | no full stop, not sentence / start / pascal / upper case | CLAUDE.md |
| header length | at most 72 | CLAUDE.md |

## Pins

| Tool | Version | Pinned in |
|---|---|---|
| `@commitlint/cli` | 21.2.3 (needs Node 22.12+) | `.pre-commit-config.yaml` and the workflow |
| ruff | v0.16.8 | `.pre-commit-config.yaml`, matches `backend/requirements-dev.txt` |
| black | 26.5.1 | `backend/requirements-dev.txt`, run from the developer's install |
| gitleaks | v8.30.1 | `.pre-commit-config.yaml` |
| pre-commit | 4.6.2 | CONTRIBUTING.md |

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | No `package.json` at the root; commitlint is installed by pre-commit (`language: node`) and by `npx` in CI. | A root `package.json` and lockfile are shared files and would put a second Node project beside `frontend/`. One pinned version in two places is enough. |
| 2 | No third-party GitHub Action for commitlint; `npx` with a pinned version. | An action is another thing to pin and trust (see D-91). |
| 3 | The config has no `extends`; every rule is written out. | The policy reads in one file and needs only the CLI. |
| 4 | eslint and prettier run as `node frontend/node_modules/.../bin/...`, not `pnpm exec`. | `pnpm --dir frontend exec` starts in `frontend/`, where the staged paths (`frontend/src/...`) do not exist. |
| 5 | prettier runs with `--end-of-line auto`. | A Windows checkout is CRLF (`core.autocrlf=true`). With the default `lf`, the hook rewrote three clean files during testing and would fail every commit. |
| 6 | black is a `language: system` hook (`python -m black`). | The compiled wheel pre-commit installs is blocked by Windows Application Control on this machine; the black from `requirements-dev.txt` runs. `--config backend/pyproject.toml` because black finds its config from the common folder of the staged files. |
| 7 | CI has no path filter and runs on `pull_request` only. | It must run on every pull request to be a required check later (NF-F0-010). `main` holds merge commits, which are skipped anyway. |

## Files

| File | Change |
|---|---|
| `commitlint.config.cjs` (new) | Rules and the `trailer-allow-list` plugin |
| `.pre-commit-config.yaml` (new) | ruff, black, gitleaks, eslint, prettier, commitlint |
| `docs/CONTRIBUTING.md` (was empty) | Setup, hooks, message rules, CI, secrets, branches |
| `.github/workflows/commit-policy.yml` (new, **shared file**) | The CI job |

## Checks run (2026-10-06)

| Check | Result |
|---|---|
| commitlint over 24 messages | 23 behave as expected. Accepted: a Refs line under the subject, Refs after a body, two Refs ids, a plain `chore(ci)` message, merge commits, prose containing `Note:` mid-body. Refused with the right reason: `Co-Authored-By`, `Co-authored-by` after a valid Refs, `Signed-off-by`, `Generated-by` above a Refs line, a trailer above a closing sentence, `Fixes:`, `Session:`, `refs:`, `Refs: 12`, `Refs: NF-F0-009 extra`, no scope, no type, upper-case type, capitalised subject, full stop, unknown type, 84-character header, upper-case scope. The 24th, the real NF-F0-008 subject, is refused for length (74 characters), which is the policy working. |
| `commitlint --from HEAD~6 --to HEAD` on real history | Merges skipped; three recent commits flagged (73, 74 and 140 characters, one with a scope that is not kebab-case). Old commits are not re-checked in CI, only the commits of a pull request. |
| pre-commit `validate-config` | OK |
| ruff, eslint, prettier, commitlint hooks through pre-commit | Pass on clean files; eslint fails on a planted `var`; commitlint fails on a planted `Co-Authored-By` and passes a valid message |
| black hook | Passes on clean files; reformats a planted badly formatted file |
| prettier on CRLF files | Leaves them unchanged with `--end-of-line auto` |
| **gitleaks blocks a planted fake key** | **Not verified.** pre-commit cannot build gitleaks on this machine: Windows Application Control blocks Go's linker (`link.exe`), and Docker is not running. See below. |
| CI job on GitHub | **Not run.** The workflow file needs your OK first, then a pull request. |

### Incident during testing

Running the prettier hook with `--write` changed three tracked frontend files from CRLF to LF (`package.json`, `CountryPair.tsx`, `EmptyState.tsx`). Git saw no content change; I restored the CRLF endings and `git status` is clean again. Decision 5 is the fix.

## Open points

- **gitleaks on Windows machines where Application Control blocks Go.** Either install the gitleaks binary and switch the hook id to `gitleaks-system` (same repo and rev), or use `gitleaks-docker`. The default `gitleaks` hook is correct on a machine that can build Go.
- **No secret scan in CI** (D-91, a new job in `security-scan.yml`, waiting for the team's OK). A hook can be skipped with `--no-verify`; only a CI scan cannot.
- **72 characters is stricter than recent commits.** All three non-merge commits among the last six were over (73, 74 and 140 characters). The limit is CLAUDE.md's; if the team prefers 100, change `header-max-length` in one place.
- Make the **Commit policy** check required in branch protection: NF-F0-010.

## Definition of Done (the task's acceptance)

- [x] A commit with a disallowed trailer or non-conventional subject fails locally (commit-msg hook run through pre-commit)
- [ ] ... and in CI (workflow written, waiting for OK and a pull request)
- [ ] gitleaks blocks a planted fake key (not verifiable on this machine yet)
- [x] Setup documented in CONTRIBUTING.md
- [ ] Reviewed by Pranjal
