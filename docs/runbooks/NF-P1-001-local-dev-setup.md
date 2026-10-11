# Local Dev Setup — Backend

## Summary

The backend is a FastAPI app in `backend/` that runs on Python 3.11.9 (the team-pinned version). Configuration is read once at startup by `app/config.py` from environment variables, locally via `backend/.env.local`; if a required variable such as `APP_ENV` is missing, the app refuses to start rather than failing later on a request. `GET /health` is the liveness probe; every other route goes under `/api/v1/` (`app/api/v1/router.py`) or `/api/v2/` (`app/api/v2/router.py`, the flag-gated Coach and Scam Analyzer). The full list is `docs/api/endpoints.md` and `docs/api/openapi.json`. Before pushing any backend branch, all four checks below (pytest, ruff, black, mypy) must pass locally, since CI will run the same ones.

## 1. One-time setup

Run from the `backend/` folder.

**Windows PowerShell**
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env.local
```

**bash (macOS / Linux / WSL)**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env.local
```

Check the interpreter: `python --version` should print `Python 3.11.9`.

`.venv/` and `.env.local` are gitignored. Never commit `.env.local` or put real keys in `.env.example`.

## 2. Run the API

Activate the venv first (`.\.venv\Scripts\Activate.ps1` or `source .venv/bin/activate`), then:

**Windows PowerShell**
```powershell
uvicorn app.main:app --reload --port 8080
```

**bash**
```bash
./scripts/run_local.sh
```

Then open:
- `http://127.0.0.1:8080/health` → `{"status":"ok","version":"2.0.0","environment":"local"}` (the version is the `APP_VERSION` setting, default `2.0.0`; an `APP_VERSION=0.1.0` line left in an older `.env.local` shows here instead, so delete it)
- `http://127.0.0.1:8080/docs` → Swagger UI

Gunicorn does not run on Windows. Production uses gunicorn with uvicorn workers inside Docker; test that path through the container (NF-P1-002).

## 3. Checks before every push

With the venv activated, from `backend/`:

```bash
pytest
ruff check .
black --check .
mypy app
```

| Command | What it checks | Expected output |
|---|---|---|
| `pytest` | Unit and integration tests in `tests/` | `N passed` |
| `ruff check .` | Lint rules from `pyproject.toml` | `All checks passed!` |
| `black --check .` | Formatting, line length 100 | `N files would be left unchanged.` |
| `mypy app` | Type hints (`--strict` for `app/services/`). CI runs exactly this; `tests/` is not type-checked (adding it reports about 150 errors) | `Success: no issues found` |

To fix formatting and auto-fixable lint issues:

```bash
black .
ruff check . --fix
```

Without activating the venv, prefix each tool with the venv path:
- PowerShell: `.\.venv\Scripts\python -m pytest`, `.\.venv\Scripts\python -m ruff check .`, `.\.venv\Scripts\python -m black --check .`, `.\.venv\Scripts\python -m mypy app`
- bash: `.venv/bin/python -m pytest` (same pattern for the others)

## 4. Workflow for a new backend task

1. Pull `main`, create your branch (`feature/<scope>-<short-desc>`).
2. If `requirements*.txt` changed, rerun `pip install -r requirements-dev.txt`.
3. New env vars: add the field to `app/config.py` and a placeholder to `backend/.env.example`, then to your own `.env.local`.
4. New endpoints: create the router in `app/api/v1/<pillar>.py`, include it in `app/api/v1/router.py`, put request/response models in `app/schemas/`, and document it in `docs/api/endpoints.md`.
5. Add tests under `tests/unit/` or `tests/integration/`.
6. Run the four checks in section 3. All must pass before pushing.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `app_env Field required` on startup | `.env.local` is missing or has no `APP_ENV`. Copy `.env.example` to `.env.local`. |
| `Activate.ps1 cannot be loaded because running scripts is disabled` | Use the non-activated commands from section 3, or ask your machine admin about the PowerShell execution policy. |
| `python --version` shows 3.12 or another version | The venv was created with the wrong interpreter. Delete `.venv` and recreate it with `py -3.11 -m venv .venv`. |
| `ModuleNotFoundError: No module named 'app'` | Run commands from `backend/`, not the repo root. |
| pytest warning about `httpx2` | Known deprecation notice from Starlette's test client. Harmless for now. |

## 6. Firebase Emulator (Firestore + Auth)

Firebase Admin integration (`app/core/security.py`, `app/repositories/base.py`) talks to
real Firestore/Auth in prod via the Cloud Run service account, and to the Firebase Emulator
Suite locally so nothing touches live data. Setup, env vars and how to verify the round trip:
[`docs/runbooks/NF-P1-005-firebase-admin-integration.md`](./NF-P1-005-firebase-admin-integration.md).
