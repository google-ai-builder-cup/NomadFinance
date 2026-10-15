# NF-P1-004 — Gemini Client Wrapper

## Summary

All Gemini calls in the backend go through one class, `GeminiClient` (`app/integrations/gemini/client.py`), using the `google-genai` SDK. A caller names a **tier** (`REASONING`, `EXTRACTION` or `CLASSIFICATION`) instead of a model ID, and passes a **Pydantic model** as the response schema. The client sends it as Gemini's `response_schema`, validates the answer, and returns a typed object, so no service ever parses free text. Each attempt is capped at 30 s. Rate limits (429), server errors (5xx), network errors and timeouts are retried with jittered exponential backoff (tenacity, 3 attempts total). Bad requests (other 4xx) and invalid output are not retried. Every SDK failure comes out as one of our own `Gemini*Error` types, and every call logs its token usage (prompt, output, thinking, total), latency and attempt count, tagged with an `operation` label for cost tracking. The API key is a required setting: locally from `backend/.env.local`, in prod from Secret Manager (`gemini-api-key`) mounted by Cloud Run. Model choices and why they changed from the original design are in `docs/decisions/ADR-002-multi-model-gemini-strategy.md`.

## Files

| File | Purpose |
|---|---|
| `backend/app/integrations/gemini/client.py` | `GeminiClient.generate_structured()`, retries, timeout, error mapping, usage logging, `get_gemini_client()` |
| `backend/app/integrations/gemini/model_tiers.py` | `ModelTier` enum and `model_for()` tier → model ID |
| `backend/app/integrations/gemini/errors.py` | `GeminiError` hierarchy |
| `backend/app/integrations/gemini/__init__.py` | Public exports: import from `app.integrations.gemini` |
| `backend/app/config.py` | `GEMINI_API_KEY` (required), per-tier model IDs, timeout, attempts |
| `backend/.env.example` | Placeholder `GEMINI_API_KEY=` and commented overrides |
| `backend/requirements.txt` | `google-genai==2.25.0`, `tenacity==9.1.4` |
| `backend/tests/unit/integrations/test_gemini_client.py` | 15 unit tests with a fake SDK (no network) |
| `backend/tests/conftest.py` | Dummy `GEMINI_API_KEY` so tests never need the real key |
| `backend/scripts/gemini_smoke_test.py` | Live check: one real call per tier (the extraction call reads a PDF) |
| `backend/scripts/deploy_manual.sh` | Adds `--set-secrets GEMINI_API_KEY=gemini-api-key:latest` |
| `docs/decisions/ADR-002-multi-model-gemini-strategy.md` | Tier → model decision |

Also updated because `GEMINI_API_KEY` is now required: `backend/README.md`, the `docker run` commands in `NF-P1-002-backend-docker.md`, and the deploy command and flag table in `NF-P1-003-cloud-run-first-deploy.md`.

## Flow

```
service code
  └─ get_gemini_client().generate_structured(operation, tier, contents, response_model, system_instruction)
       ├─ model_for(tier)            → e.g. REASONING → gemini-3.5-flash
       ├─ GenerateContentConfig      → response_mime_type=application/json, response_schema=<Pydantic model>
       ├─ tenacity (max 3 attempts, jittered backoff up to 8 s)
       │    └─ asyncio.timeout(30 s) → client.aio.models.generate_content(...)
       │         ├─ 429                     → GeminiRateLimitError   (retried)
       │         ├─ 5xx                     → GeminiUnavailableError (retried)
       │         ├─ network error           → GeminiUnavailableError (retried)
       │         ├─ timeout                 → GeminiTimeoutError     (retried)
       │         └─ other 4xx               → GeminiRequestError     (not retried)
       ├─ log: gemini_call operation=… tier=… model=… prompt_tokens=… output_tokens=… thinking_tokens=… total_tokens=… latency_ms=… attempts=…
       └─ validate → response_model instance
            └─ empty / blocked / schema mismatch → GeminiResponseError (not retried)
```

## Models

| Tier | Default | Env override |
|---|---|---|
| `ModelTier.REASONING` | `gemini-3.5-flash` | `GEMINI_MODEL_REASONING` |
| `ModelTier.EXTRACTION` | `gemini-3.5-flash-lite` | `GEMINI_MODEL_EXTRACTION` |
| `ModelTier.CLASSIFICATION` | `gemini-3.1-flash-lite` | `GEMINI_MODEL_CLASSIFICATION` |

Other settings: `GEMINI_TIMEOUT_SECONDS` (default 30), `GEMINI_MAX_ATTEMPTS` (default 3, includes the first try).

## How to use it in a service

```python
from google.genai import types
from pydantic import BaseModel

from app.integrations.gemini import GeminiError, ModelTier, get_gemini_client


class ContractText(BaseModel):
    raw_text: str
    language: str


async def extract_contract(pdf_bytes: bytes, system_prompt: str) -> ContractText:
    return await get_gemini_client().generate_structured(
        operation="contract.extract",          # shows up in the token-usage log
        tier=ModelTier.EXTRACTION,
        contents=[types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")],
        response_model=ContractText,
        system_instruction=system_prompt,       # from the prompt library (NF-P1-029)
    )
```

Rules:
- Always pass a Pydantic `response_model`. There is no free-text method on purpose.
- Pick a tier, never a model ID.
- Use a dotted `operation` name, `<pillar>.<step>` (e.g. `radar.validate`), so token logs can be grouped per pipeline step.
- Catch `GeminiError` (or a specific subclass) at the endpoint layer and turn it into an HTTP error. Never let SDK exceptions or tracebacks reach the client. This is wired app-wide since NF-P1-006 (`app/core/errors.py`): `GeminiRateLimitError` and `GeminiUnavailableError` → 503 with `Retry-After: 30`, `GeminiTimeoutError` → 504, `GeminiResponseError` → 502, `GeminiRequestError` → 500 (it is our bug). Endpoints can simply let `GeminiError` propagate.
- Leave `temperature` unset unless there is a reason. Gemini 3 models are tuned for their default.

## All commands, in order

Run from the `backend/` folder with the venv activated (see `NF-P1-001-local-dev-setup.md`), unless a step says otherwise.

### 0. Pull and install the new dependencies

```bash
pip install -r requirements-dev.txt
```

Check: `pip show google-genai tenacity` lists `2.25.0` and `9.1.4`.

### 1. Add the Gemini key to `.env.local` (every teammate, one time)

The app now refuses to start without `GEMINI_API_KEY`. Read the key from Secret Manager (needs `gcloud auth login` and access to `nomadfinance-prod`):

```bash
gcloud secrets versions access latest --secret gemini-api-key --project nomadfinance-prod
```

Open `backend/.env.local` and add the line below, pasting the value after `=` with no quotes or spaces:

```
GEMINI_API_KEY=<paste the key here>
```

Never commit `.env.local`, and never paste the key into code, docs, chat or tickets.

### 2. Unit tests and checks

```bash
pytest
ruff check .
black --check .
mypy app tests
```

Expected: all tests pass (the Firestore repository test is skipped unless the emulator runs), `All checks passed!`, `... would be left unchanged.`, `Success: no issues found`.

Only the Gemini tests:

```bash
pytest tests/unit/integrations/test_gemini_client.py -v
```

Expected: `15 passed`. These use a fake SDK client: no network, no key, no quota used.

### 3. Live smoke test (real Gemini calls, uses a little free-tier quota)

```bash
python -m scripts.gemini_smoke_test
```

Run it with `python -m` from `backend/`. `python scripts/gemini_smoke_test.py` fails with `No module named 'app'`.

Expected: three `OK` lines, one per tier, each with a validated JSON object, plus one `gemini_call ...` usage log line per call. Exit code 0. Any `FAIL` line names the error type (see Troubleshooting).

Try a different model for one tier without touching code:

**Windows PowerShell**
```powershell
$env:GEMINI_MODEL_REASONING = "gemini-3.8-flash"; python -m scripts.gemini_smoke_test; Remove-Item Env:GEMINI_MODEL_REASONING
```

**bash**
```bash
GEMINI_MODEL_REASONING=gemini-3.8-flash python -m scripts.gemini_smoke_test
```

### 4. Run the API locally (unchanged, but now needs the key)

```bash
uvicorn app.main:app --reload --port 8080
```

Or in Docker (from `backend/`):

```bash
docker build -t nomadfinance-backend:local .
docker run --rm -p 8080:8080 --env-file .env.local nomadfinance-backend:local
```

`/health` must still return 200.

### 5. Cloud Run: let the service read the secret (one time, project owner)

The Cloud Run runtime account has no roles yet (NF-P1-003). Grant it read access to this one secret only:

```bash
gcloud secrets add-iam-policy-binding gemini-api-key --project nomadfinance-prod --member="serviceAccount:nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
```

Check the binding:

```bash
gcloud secrets get-iam-policy gemini-api-key --project nomadfinance-prod
```

Expected: `roles/secretmanager.secretAccessor` with `serviceAccount:nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com`.

### 6. Cloud Run: redeploy with the secret mounted

After this PR is merged. `deploy_manual.sh` now passes `--set-secrets GEMINI_API_KEY=gemini-api-key:latest`:

```bash
bash scripts/deploy_manual.sh
```

PowerShell users: follow step 4 of `NF-P1-003-cloud-run-first-deploy.md`. Its command now includes the `--set-secrets` line.

Check that the secret is mounted:

```bash
gcloud run services describe nomadfinance-api --project nomadfinance-prod --region asia-south1 --format "yaml(spec.template.spec.containers[0].env)"
```

Expected: an entry `name: GEMINI_API_KEY` with `secretKeyRef` → `key: latest`, `name: gemini-api-key`. Then check `/health` on the service URL (200).

If step 5 was skipped, the deploy fails with `Permission denied on secret ... for Revision service account`.

## Live check results

Run on 2026-09-24 with the team key, default models, `python -m scripts.gemini_smoke_test`:

```
gemini_call operation=smoke.reasoning tier=reasoning model=gemini-3.5-flash prompt_tokens=31 output_tokens=61 thinking_tokens=289 total_tokens=381 latency_ms=23155 attempts=1
gemini_call operation=smoke.extraction tier=extraction model=gemini-3.5-flash-lite prompt_tokens=534 output_tokens=35 thinking_tokens=None total_tokens=569 latency_ms=1955 attempts=1
gemini_call operation=smoke.classification tier=classification model=gemini-3.1-flash-lite prompt_tokens=24 output_tokens=17 thinking_tokens=None total_tokens=41 latency_ms=2361 attempts=1
OK   reasoning: {"risky":true,"reason":"In Singapore, retaining a migrant worker's passport is illegal under the Passports Act. ..."}
OK   extraction: {"employer":"Lim Household Services Pte Ltd","monthly_salary":750.0,"currency":"SGD"}
OK   classification: {"iso_639_1":"tl"}
```

Seen in real traffic during testing (not simulated):
- `503 UNAVAILABLE` "high demand" on `gemini-3.5-flash` → `gemini_retry attempt=1` → success on attempt 2.
- A 30 s timeout on a PDF extraction with `gemini-3.5-flash` → `gemini_retry ... GeminiTimeoutError` → success on attempt 2.
- `gemini-3.8-flash`, `3.7-flash`, `3.6-flash`: 503 on every attempt → clean `GeminiUnavailableError` after 3 attempts. This is why they are not the defaults (see ADR-002).

Reasoning calls take 13–23 s because of thinking tokens. That is inside the 30 s timeout, but long contracts may get close to it (see Troubleshooting).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `gemini_api_key Field required` on startup, in tests or in Docker | Add `GEMINI_API_KEY` to `backend/.env.local` (step 1). Docker: use `--env-file .env.local`. Cloud Run: the `--set-secrets` flag is missing (step 6). |
| `No module named 'app'` when running the smoke test | Run `python -m scripts.gemini_smoke_test` from `backend/`. |
| `GeminiRequestError: ... 400 INVALID_ARGUMENT ... API key not valid` | Wrong or truncated key in `.env.local`. Copy it again (step 1). No quotes, no trailing space. |
| `GeminiRequestError: ... 404 NOT_FOUND` | Model ID wrong or retired. Check https://ai.google.dev/gemini-api/docs/models, then set `GEMINI_MODEL_<TIER>` and update ADR-002. |
| `GeminiRequestError: ... 403 PERMISSION_DENIED` | Key has no access to that model (e.g. the Limited Access 2.5 models). Pick another model for that tier. |
| `GeminiUnavailableError: ... 503 UNAVAILABLE ... high demand` | Google-side capacity. Free-tier traffic is served last. Already retried 3 times. Try again later, or switch that tier to another model with `GEMINI_MODEL_<TIER>`. |
| `GeminiRateLimitError` | Free-tier quota for that model is used up (per minute or per day). Wait, or check limits in AI Studio → Rate limits. |
| `GeminiTimeoutError` | Three attempts, each over 30 s. Reasoning calls already take 13–23 s on short inputs because of thinking, and large PDFs are slower. Raise `GEMINI_TIMEOUT_SECONDS` for that environment if it happens often. |
| `GeminiResponseError: ... did not match <Model>` | The output didn't fit the schema. Simplify the Pydantic model (fewer nested or optional fields) or tighten the prompt. |
| `GeminiResponseError: ... prompt blocked` | Safety filter blocked the input. Log the `operation` and review the input. |
| No `gemini_call` log lines when running the API | App logging isn't configured yet, so INFO logs from `app.*` are dropped under uvicorn and gunicorn. NF-P1-028 adds it. The smoke test configures logging itself, so the lines show there. |
| Deploy fails: `Permission denied on secret` | Do step 5 (IAM grant), then redeploy. |

## Commit and PR for this task

Branch: `feature/backend-gemini-client`. Run from the **repo root**, not `backend/`, so files under `docs/` are staged too:

```bash
git add backend docs
git status
```

`git status` must list only the NF-P1-004 files from the Files table above, the three doc updates (`backend/README.md`, `NF-P1-002-backend-docker.md`, `NF-P1-003-cloud-run-first-deploy.md`) and this runbook. Never `.env.local`.

```bash
git commit -m "feat(backend): add Gemini client with model tiers and retries" -m "Refs: NF-P1-004"
```

PR title: `feat(backend): Gemini client wrapper with model tiers and retries (NF-P1-004)`

After merge: do steps 5 and 6 (IAM grant, redeploy) so Cloud Run gets the key.

## Not covered here

- Prompt files and loader (`app/prompts/`): NF-P1-029
- First endpoint using the client, and mapping `GeminiError` to HTTP responses: NF-P1-006
- Embeddings (`app/integrations/gemini/embeddings.py`, use `gemini-embedding-001`): NF-P3-002
- JSON logging so the `gemini_usage` fields reach Cloud Logging: NF-P1-028
