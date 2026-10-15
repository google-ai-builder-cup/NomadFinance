# NF-HR-008 — Security review v2 (OWASP API Top 10 and model risks)

## Summary

The v2 surface (Scam Analyzer, Financial Coach, Financial Identity signals) was reviewed against the OWASP API Top 10 (2023) and the risks of a language model in the loop. **No High or Critical finding is open.** The findings, with evidence, are in [`docs/security-review-v2.md`](../security-review-v2.md); this page is the hand-over: what changed, how to re-run it, and what was left out.

| # | Severity | Finding | Status |
|---|---|---|---|
| F2-01 | Low | A v2 JSON route read a body of up to 10 MB before it checked the 4,000-character limit | **Fixed** (128 KB cap on v2 JSON) |
| F2-02 | Low | No `/api/` answer said it was not to be cached or that its type was not to be guessed | **Fixed** (`no-store`, `nosniff`) |
| F2-03 | Low | A Coach reply holding a web link or an e-mail address was shown and saved | **Fixed** (`reply_contains_link`) |
| F2-04 | Info | No secret scan in CI | **Left out by decision** (D-91, D-282) |
| F2-05 | Info | Two High advisories in build-time tools | `source-map-js` **fixed**; `braces` accepted, no fix exists (D-283) |
| F2-06 to F2-08 | Info | Unknown body fields ignored; the offline outbox keeps a token until sign-out; the Coach reply is shown before its last check | Accepted, reasons in the review |

## Files

| File | Change |
|---|---|
| `backend/app/core/middleware.py` | `V2_JSON_MAX_BYTES` (128 KB) and `BodySizeLimitMiddleware._limit_for`: a `/api/v2/` request with `Content-Type: application/json` is cut at 128 KB, everything else keeps the upload cap. New `SecurityHeadersMiddleware`: `X-Content-Type-Options: nosniff` on every answer and `Cache-Control: no-store` under `/api/` unless the answer sets its own |
| `backend/app/main.py` | Registers `SecurityHeadersMiddleware` outside CORS, so a 413 or 429 carries the headers; the order comment is updated |
| `backend/app/services/coach/guard_rules.py`, `guard.py`, `guard_types.py` | `contains_link` (scheme links, `www.`, e-mail addresses, after NFKC) and the reason `reply_contains_link` in `check_reply` |
| `backend/tests/integration/api/test_security_v2.py` (new) | 13 tests over a table of the 14 v2 routes, read from the app |
| `backend/tests/unit/services/test_coach_guard.py`, `tests/integration/api/test_coach_turns_guard.py` | 8 unit cases (5 blocked, 3 ordinary replies) and 3 streams for the link check |
| `backend/tests/fixtures/security_redteam.py`, `tests/integration/test_security_redteam_live.py` (new) | 12 Coach attacks and controls, 7 analyzer cases and 1 screenshot, run against the real models; skipped unless `RUN_LIVE_GEMINI=1` |
| `frontend/package.json`, `frontend/pnpm-lock.yaml` | One `pnpm.overrides` entry, `source-map-js >=1.2.2`; the lockfile moved that one package from 1.2.1 to 1.2.2 |
| `docs/security-review-v2.md` (new), `docs/SECURITY.md`, `docs/api/v2-conventions.md` | The review; two rows in the controls table; the 413 row; D-282 to D-284 |

Not touched: `.github/workflows/*`, `.gitleaks.toml` (not created), `firebase.json`, `firestore.rules`, `storage.rules`, `backend/Dockerfile`, `requirements*.txt`. No dependency was added.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | "Every v2 route" | The review is a **test that reads the route table from the app**, so a route added later without its controls fails the suite, instead of a document that goes stale |
| 2 | What the earlier work already covers | Bad tokens (21 kinds), one worker's id on another worker's route in each feature's own tests, and the rules tests were **not repeated**; the new file adds the stranger's answer against a missing id on all 9 id routes, answer contents, extra fields, body size, headers, links and prompt contents |
| 3 | The size of the JSON cap | 128 KB, for `/api/v2` and `application/json` only: a 4,000-character message is under 50 KB even when every character is escaped. A screenshot is multipart and keeps the 10 MB cap; v1 is unchanged |
| 4 | What counts as a link in a Coach reply | A scheme link, `www.` or an e-mail address. A bare address such as `evil.example/pay` is not caught (a pattern cannot tell it from a sentence); the guard's classifier is the layer for it |
| 5 | The live red-team | About 20 real-model calls with invented messages, as approved. The key's reasoning-tier quota ran out for 5 of the 7 analyzer explanations, so those were not checked for system-prompt echo (D-284) |
| 6 | gitleaks | Installed on this machine with `brew install gitleaks` (8.30.1, the version pre-commit pins) to scan the full history. It is outside the repository |
| 7 | The secret scan in CI and the allowlist | **Left out**: the job fails on its first run without the allowlist, and the team chose to leave both for later. The exact files are kept in the review (F2-04) so they can be applied as they are |
| 8 | Deferred-item numbers | D-282 to D-284: D-274 to D-281 were already taken by NF-HR-004 on `main` |

## Results

**Backend (2026-10-11), run as `backend-ci.yml` runs them:** `black --check`, `ruff check`, `mypy app` (242 files), `mypy --strict app/services` (108 files), `pytest`: **3,757 passed, 197 skipped** (the live tests, including the new one).

**Frontend, as `frontend-ci.yml` runs them:** `pnpm lint` (0 warnings), `pnpm format:check`, `pnpm test:coverage` (139 files, 1,645 tests), `pnpm build`, the end-to-end job (148 passed), and `pnpm test:rules` (3 files, 186 tests).

| Check | Result |
|---|---|
| Stranger's id against a missing id | The same status, code and message on all 9 id routes; nothing of the owner's data changed; a history cursor from another worker is `400 invalid_cursor` |
| Flag off | Every guarded route answers as an unknown path does |
| Answer contents | No internal field and no uid at any depth in 7 answers; `uid`, `status`, `stage`, `revision` in a body change nothing stored |
| Size | A 2 MB JSON body is `413 payload_too_large`; a 4,000-character message is still `200` |
| Headers | `no-store` and `nosniff` on every worker answer tested |
| Links | A message with `169.254.169.254` and `127.0.0.1` makes no socket connection; a Coach reply with a link, an e-mail address or `www.` ends in `ai_bad_response` and saves nothing |
| Prompts | Nothing one worker typed, nor the uid, appears in a call made for another |
| Red-team, live | Coach guard 10 of 10 attacks stopped, 2 of 2 controls let through; analyzer 7 of 7 right, no system-prompt echo in the verdict and details; the screenshot with an order inside was transcribed with the fee request intact |
| Secrets | 198 commits and the working tree: 0 real secrets (30 matches, all test constants or an example hash) |
| Dependencies | `pip-audit`: none in backend or data-scripts. `pnpm audit`: 1 High (`braces`, dev, no fix), 3 moderate; production at high and above: none |
| Break check | Before the fixes the body-size test returned `422` (not `413`) and the header test found no `Cache-Control`, both seen when the tests were first run; the link check was added with its tests together, and `check_reply` returned nothing for such a reply by the code before it |

**Not verified:** production Firestore and the live site (everything ran on emulators, in-memory stores or recorded answers); the Radar indicator count against many different messages from one worker; the explanation's echo check for 5 of the 7 analyzer cases (D-284); a bare address with no scheme in a Coach reply.

## Manual test

From `backend/`:

```bash
pytest tests/integration/api/test_security_v2.py tests/unit/services/test_coach_guard.py tests/integration/api/test_coach_turns_guard.py -v
```

The two fixes by hand (start the API with `uvicorn app.main:app`, then use a valid token):

```bash
# a JSON body of 200 KB to a v2 route: 413 payload_too_large
python -c "import json;print(json.dumps({'text':'a'*200000,'language':'en'}))" > big.json
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" --data @big.json http://127.0.0.1:8080/api/v2/scam/analyze

# the headers of a worker's answer
curl -sI -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/v2/coach/overview | grep -i -E "cache-control|x-content-type-options"
```

**Windows PowerShell:** `python -c "import json;print(json.dumps({'text':'a'*200000,'language':'en'}))" | Out-File -Encoding ascii big.json`, then `curl.exe -s -o NUL -w "%{http_code}\n" -H "Authorization: Bearer $env:TOKEN" -H "Content-Type: application/json" --data "@big.json" http://127.0.0.1:8080/api/v2/scam/analyze`, and `curl.exe -sI -H "Authorization: Bearer $env:TOKEN" http://127.0.0.1:8080/api/v2/coach/overview`.

The live red-team (spends Gemini quota; about 20 calls):

```bash
RUN_LIVE_GEMINI=1 LIVE_PAUSE_SECONDS=2 pytest tests/integration/test_security_redteam_live.py -v -s
```

**Windows PowerShell:** `$env:RUN_LIVE_GEMINI = "1"; $env:LIVE_PAUSE_SECONDS = "2"` first, then the same `pytest` command.

The scans (the commands are in the review's "Reproduce" section): `gitleaks git --log-opts="--all" --redact --no-banner`, `pip-audit -r backend/requirements.txt --no-deps --disable-pip`, `pnpm audit`, and `pnpm test:rules` from `frontend/`.

## Definition of Done (Documentation and QA)

- [x] Every OWASP API Top 10 item has a verdict for the v2 routes, with evidence
- [x] Rules audited and tested (186 emulator tests); secrets, dependencies and the model red-team run
- [x] Findings logged with severity; **zero open High** (the one High left is a dev-only tool with no fix, accepted and ticketed)
- [x] Fixes have tests that fail without them; strict types, lint and format clean; no shared workflow, rules or Dockerfile touched
- [x] The CI jobs run locally with the same commands, including end-to-end and the rules tests
- [x] Written in Markdown, no attribution wording; `docs/security-review-v2.md` is in the change
- [ ] `docs/security-review-v2.md` merged (after the pull request)
- [ ] Second reader of the review (Devam)
- [ ] Secret scan in CI (D-91, D-282): left out by decision
- [ ] The live red-team repeated when the Gemini quota allows (D-284)

## Commit

Branch: `test/NF-HR-008-test-security-review-v2` (already checked out).

```bash
git commit -m "test(security): review v2 routes and fix JSON cap, headers, reply links" -m "Refs: NF-HR-008"
```

The header is 71 characters (the limit is 72). PR title: `test(security): v2 security review, three small fixes and a red-team (NF-HR-008)`
