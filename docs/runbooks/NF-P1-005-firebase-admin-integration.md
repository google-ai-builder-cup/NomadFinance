# NF-P1-005 — Firebase Admin Integration

## Summary

The backend now carries the **firebase-admin** SDK and three reusable pieces every later pillar builds on: a Firestore access layer, and a Firebase Auth token verification dependency. `app/core/security.py` owns a lazily-initialized, process-wide Firebase Admin app (`get_firebase_app()`, cached) and `verify_id_token()`, which wraps every Firebase-side failure (expired, revoked, malformed, disabled user, bad certificate) into one `InvalidTokenError`. `app/repositories/base.py` owns the Firestore client singleton (`get_firestore_client()`) and a generic `FirestoreRepository` base class (`get`/`set`/`delete`) that pillar-specific repos (`user_repo.py`, `contract_repo.py`, ...) will subclass. `app/dependencies.py` exposes `get_current_user`, a FastAPI dependency that reads the `Authorization: Bearer <token>` header, verifies it, and returns an `AuthenticatedUser` (`app/schemas/user.py`) or raises `401`.

No endpoint calls `get_current_user` yet — `/health` is still the only route, and it stays public. This task only builds the reusable pieces; the first real consumer is NF-P1-006.

**Credential story, no code branching needed:** in prod, Cloud Run's `nomadfinance-backend` service account supplies Application Default Credentials automatically. Locally, the Firebase Emulator Suite is used instead — `firebase_admin` and `google-cloud-firestore` both read `FIRESTORE_EMULATOR_HOST` / `FIREBASE_AUTH_EMULATOR_HOST` straight from the environment, so the same code path runs against either target depending only on which env vars are set.

## Files

| File | Purpose |
|---|---|
| `backend/app/core/security.py` | Firebase Admin app singleton, `verify_id_token()`, `InvalidTokenError` |
| `backend/app/repositories/base.py` | Firestore client singleton, generic `FirestoreRepository` base class |
| `backend/app/schemas/user.py` | `AuthenticatedUser` — identity decoded from a verified token (not the Firestore profile; that's NF-P1-022) |
| `backend/app/dependencies.py` | `get_current_user` — the auth dependency, add `Depends(get_current_user)` to any non-public route |
| `backend/app/config.py` | `firebase_project_id` setting |
| `backend/.env.example` | `FIREBASE_PROJECT_ID` placeholder |
| `backend/requirements.txt` | Added `firebase-admin==7.7.0` |
| `backend/tests/conftest.py` | `anyio_backend` fixture, needed to run the async `get_current_user` tests |
| `backend/tests/unit/core/test_security.py`, `tests/unit/test_dependencies.py`, `tests/unit/repositories/test_base.py` | Mocked unit tests — no emulator needed, always run |
| `backend/tests/integration/repositories/test_firestore_repository.py` | Real Firestore read/write round trip — skips unless the emulator is running |
| `docs/api/endpoints.md` | New "Authentication" section |
| `docs/runbooks/NF-P1-001-local-dev-setup.md` | Points here for the Firebase Emulator instead of repeating it |

## Flow

```
Request:  Authorization: Bearer <firebase-id-token>
  └─ route:  Depends(get_current_user)                    [app/dependencies.py]
       └─ verify_id_token(token)                           [app/core/security.py]
            └─ firebase_admin.auth.verify_id_token()  ──►  Firebase Auth (prod)
                                                       ──►  Auth Emulator (local, FIREBASE_AUTH_EMULATOR_HOST)
            ├─ expired / revoked / invalid / disabled  ──►  InvalidTokenError ──► HTTPException 401
            └─ valid                                    ──►  AuthenticatedUser(uid, email, ...)

Repository read/write:
  SomeRepository(FirestoreRepository):  collection_name = "..."
       └─ get_firestore_client()                          [app/repositories/base.py]
            └─ firebase_admin.firestore.client()     ──►  Firestore (prod, ADC via nomadfinance-backend SA)
                                                       ──►  Firestore Emulator (local, FIRESTORE_EMULATOR_HOST)
```

## All commands, in order

Run from `backend/`, venv activated (see `NF-P1-001-local-dev-setup.md`). Steps 1–3 need nothing extra; step 4 needs the Firebase Emulator.

### 1. Install the new dependency

```bash
pip install -r requirements-dev.txt
```

Expected: `firebase-admin-7.7.0` (and its transitive `google-cloud-firestore`, `google-api-core`, `pyjwt`) appear in the install output.

### 2. Run the checks

```bash
pytest -v
ruff check .
black --check .
mypy app tests
```

Expected: `16 passed, 1 skipped` (the skip is the emulator-only Firestore round trip — see step 4), `All checks passed!`, `N files would be left unchanged.`, `Success: no issues found`.

### 3. Prove token verification works, without the emulator

The unit tests already do this with a mock; the same thing from a REPL, to see it directly:

```bash
python
```
```python
>>> from unittest.mock import patch
>>> from app.core.security import verify_id_token
>>> with patch("app.core.security.firebase_auth.verify_id_token", return_value={"uid": "demo-uid", "email": "worker@example.com"}):
...     verify_id_token("whatever")
...
{'uid': 'demo-uid', 'email': 'worker@example.com'}
```

Expected: the decoded claims dict comes back unchanged. This proves the wrapper (ordering of the `except` clauses, `check_revoked=True`) is wired correctly; it doesn't call real Firebase.

### 4. Optional — real Firestore + Auth against the emulator

Full setup: `docs/runbooks/NF-P1-001-local-dev-setup.md`, section 6. Short version:

```bash
npm install -g firebase-tools
gcloud components install cloud-firestore-emulator
firebase emulators:start --only firestore,auth --project demo-nomadfinance
```

In another terminal, with `FIRESTORE_EMULATOR_HOST` / `FIREBASE_AUTH_EMULATOR_HOST` exported (or set in `.env.local`):

```bash
pytest tests/integration/repositories/test_firestore_repository.py -v
```

Expected: `1 passed` instead of `1 skipped` — a document actually gets written, read back, merged, read again and deleted against the emulator.

This step was **not run in this session** — the Firestore Emulator component isn't installed on this machine. Run it once to get a real pass before relying on it for the demo.

### 5. How a future endpoint uses this

```python
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.schemas.user import AuthenticatedUser

router = APIRouter()

@router.get("/me")
async def read_profile(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    return user
```

An endpoint that should stay public simply omits the dependency — and per the Backend Endpoint Definition of Done, must say so in its own `docs/api/endpoints.md` section (see the `/health` entry there for the pattern).

## Verified results (2026-09-24, commit `aa0a542`)

| Check | Result |
|---|---|
| `pip install -r requirements-dev.txt` | `firebase-admin==7.7.0` installs cleanly alongside the existing pins (shares `httpx==0.28.1`) |
| `pytest -v` | 16 passed, 1 skipped (Firestore-emulator test, expected without the emulator) |
| `ruff check .` | All checks passed! |
| `black --check .` | 119 files would be left unchanged. |
| `mypy app tests` | Success: no issues found in 119 source files |
| `uvicorn app.main:app --reload --port 8080` | Boots, `Application startup complete.` — Firebase init is lazy, `/health` behavior unchanged |
| REPL token verification (mocked) | Decoded claims returned unchanged, confirms `verify_id_token` wrapper logic |
| Firestore Emulator round trip | Not run — emulator component not installed on this machine; test is written and auto-skips |

## Definition of Done

- [x] Firebase Auth token verification implemented (`get_current_user`) — reusable dependency; no live endpoint consumes it yet (none exist besides `/health`, which stays public)
- [x] `firebase-admin` installed and pinned
- [x] Firestore read/write path implemented and unit-tested (mocked)
- [ ] Firestore read/write verified against a real Firestore instance/emulator — pending someone running step 4 with the emulator installed
- [x] `docs/api/endpoints.md` updated (Authentication section)
- [x] Checks pass: `pytest`, `ruff`, `black`, `mypy`
- [ ] Reviewed by at least one teammate
- [ ] Committed to the repo

## Commit

Branch: `feature/backend-firebase-admin`

```bash
git add backend/app/core/security.py backend/app/repositories/base.py backend/app/schemas/user.py backend/app/dependencies.py backend/app/config.py backend/.env.example backend/requirements.txt backend/tests/conftest.py backend/tests/unit/core backend/tests/unit/test_dependencies.py backend/tests/unit/repositories/test_base.py backend/tests/integration/repositories docs/api/endpoints.md docs/runbooks/NF-P1-001-local-dev-setup.md docs/runbooks/NF-P1-005-firebase-admin-integration.md backend/README.md
git commit -m "feat(backend): integrate firebase-admin SDK and auth verification" -m "Refs: NF-P1-005"
```

Before pushing, run `git status` and confirm nothing else is staged.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `source .venv/bin/activate: No such file or directory` (Git Bash) | Windows venvs put the activation script in `Scripts/`, not `bin/`. Use `source .venv/Scripts/activate`. |
| `ruff`: `B008 Do not perform function call Depends in argument defaults` | Known false positive for FastAPI's own `Depends()`-as-default pattern; suppressed inline with `# noqa: B008` on that line rather than a repo-wide ruff config change. |
| `mypy`: `Skipping analyzing "firebase_admin": ... missing library stubs` | `firebase-admin` ships with no `py.typed` marker. Suppressed inline with `# type: ignore[import-untyped]` on the import line, not a `pyproject.toml` override. |
| `mypy`: `Returning Any from function declared to return "Client"` | Same root cause — `firestore.client()` is untyped. Suppressed with `# type: ignore[no-any-return]` at the one call site in `repositories/base.py`. |
| `tests/integration/repositories/test_firestore_repository.py` always `SKIPPED` | Expected without `FIRESTORE_EMULATOR_HOST` set. Follow step 4 above to run it for real. |
| `async def functions are not natively supported` in pytest | Missing the `anyio_backend` fixture / `@pytest.mark.anyio`. Already added to `tests/conftest.py`; new async tests need `pytestmark = pytest.mark.anyio` at the top of the file. |
| `google.auth.exceptions.DefaultCredentialsError` when actually calling Firebase (not from these tests, which mock it) | No ADC available. Run `gcloud auth application-default login` for a real project, or point at the emulator (step 4) for local work — never commit a service account key. |
| PowerShell: `&&` not recognized, or `source` not recognized | PowerShell isn't bash. Use `;` instead of `&&`, and `.\.venv\Scripts\Activate.ps1` instead of `source ...`. |

## Not covered here

- Wiring `Depends(get_current_user)` into a real endpoint: NF-P1-006 (first consumer)
- Firestore security rules (`infra/firebase/firestore.rules`): NF-P1-014
- Full Firestore user profile schema (home_country, host_country, job_type, ...) and `user_repo.py` contents: NF-P1-022, NF-P1-023
- CORS, rate limiting, structured request logging (`app/core/middleware.py`): NF-P1-027, NF-P1-028
- `frontend/firebase.json` / Firebase Hosting config: NF-P1-008
- CI running these checks on push: NF-P1-020
