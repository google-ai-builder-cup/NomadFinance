# NF-P1-002 — Backend Docker Image

## Summary

The backend ships as one Docker image built from `backend/Dockerfile`. It is a two-stage build on `python:3.11.9-slim-bookworm` (the team's Python version): the **builder** stage installs `requirements.txt` into a virtualenv at `/opt/venv`, and the **runtime** stage copies only that virtualenv and the `app/` package, so no pip cache, build tools, tests or `.env` files end up in the image. The container runs as a non-root user (`appuser`, uid 10001) and starts **gunicorn** with **uvicorn workers** (`uvicorn-worker` package). Gunicorn reads `PORT` (default 8080) for its bind address and `WEB_CONCURRENCY` (default 1) for its worker count, which is exactly what Cloud Run sets. `APP_ENV` is deliberately **not** baked into the image: it must be passed at run time, and the container exits immediately if it is missing. This image is what NF-P1-003 deploys to Cloud Run.

## Files

| File | Purpose |
|---|---|
| `backend/Dockerfile` | Multi-stage build, non-root runtime, gunicorn start command |
| `backend/.dockerignore` | Keeps `.env*`, `.venv/`, caches, tests and scripts out of the build context. Cache patterns use `**/` so they match in every subfolder, not just the root. |
| `backend/scripts/build_docker.sh` | bash helper for the build (`IMAGE=<name:tag>` to override the tag) |
| `backend/requirements.txt` | Added `uvicorn-worker==0.4.0` (gunicorn worker class; `uvicorn.workers` is deprecated in uvicorn 0.53) |

## Flow

```
docker build
  └─ builder:  python:3.11.9-slim → venv /opt/venv → pip install -r requirements.txt
  └─ runtime:  python:3.11.9-slim → copy /opt/venv + app/ → USER appuser
docker run -e APP_ENV=...
  └─ gunicorn (PID 1, bind 0.0.0.0:$PORT, $WEB_CONCURRENCY workers)
       └─ uvicorn_worker.UvicornWorker → app.main:app → settings validated → /health ready
```

## All commands, in order

Run everything from the `backend/` folder. Commands are the same in PowerShell and bash unless both are shown.

### 0. Prerequisites

Start Docker Desktop, then confirm the daemon is up (prints a version such as `29.8.0 linux`):

```bash
docker info --format "{{.ServerVersion}} {{.OSType}}"
```

Go to the backend folder:

```bash
cd backend
```

### 1. Build the image

**Windows PowerShell**
```powershell
docker build -t nomadfinance-backend:local .
```

**bash**
```bash
./scripts/build_docker.sh
```

Check the image exists and its size (about 395 MB as of NF-P1-004; it grows as dependencies are added):

```bash
docker image ls nomadfinance-backend:local
```

### 2. Run the container

Foreground (logs in the terminal, stop with `Ctrl+C`):

```bash
docker run --rm -p 8080:8080 --env-file .env.local nomadfinance-backend:local
```

`--env-file .env.local` passes every required setting (`APP_ENV`, and since NF-P1-004 also `GEMINI_API_KEY`). Passing only `-e APP_ENV=local` is no longer enough: the container exits with `gemini_api_key Field required`.

### 3. Check `/health` and Swagger

In a second terminal while the container runs:

**Windows PowerShell**
```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

**bash**
```bash
curl -s http://127.0.0.1:8080/health
```

Expected: `{"status":"ok","version":"0.1.0","environment":"local"}`

Open `http://127.0.0.1:8080/docs` in a browser: Swagger UI loads, and `GET /health` → "Try it out" → "Execute" returns 200.

### 4. Check the container runs as non-root

```bash
docker run --rm nomadfinance-backend:local whoami
```

Expected: `appuser`

### 5. Check nothing extra got into the image

```bash
docker run --rm nomadfinance-backend:local sh -c "ls -A /app"
```

Expected: only `app`. Keep the `sh -c "..."` wrapper: Git Bash on Windows rewrites a bare `/app` argument into `C:/Program Files/Git/app`.

```bash
docker run --rm nomadfinance-backend:local sh -c "find /app -name __pycache__ -o -name '*.pyc' | wc -l"
```

Expected: `0`

### 6. Check fail-fast without `APP_ENV`

**Windows PowerShell**
```powershell
docker run --rm nomadfinance-backend:local; echo "exit code: $LASTEXITCODE"
```

**bash**
```bash
docker run --rm nomadfinance-backend:local; echo "exit code: $?"
```

Expected: logs contain `app_env Field required`, then `exit code: 3`

### 7. Check the Cloud Run `PORT` override

```bash
docker run --rm -p 9090:9090 --env-file .env.local -e PORT=9090 nomadfinance-backend:local
```

Expected log line: `Listening at: http://0.0.0.0:9090`. In a second terminal, `/health` on port 9090 returns 200:

**Windows PowerShell**
```powershell
Invoke-RestMethod http://127.0.0.1:9090/health
```

**bash**
```bash
curl -s http://127.0.0.1:9090/health
```

Stop with `Ctrl+C`.

### 8. Check graceful shutdown (what Cloud Run does on scale-down)

Start in the background:

```bash
docker run -d --name nf-test -p 8080:8080 --env-file .env.local nomadfinance-backend:local
```

Stop it (sends SIGTERM):

```bash
docker stop nf-test
```

Read the shutdown logs. Expected: `Handling signal: term`, `Application shutdown complete.`, `Shutting down: Master`:

```bash
docker logs nf-test
```

Check the exit code. Expected: `0`

```bash
docker inspect nf-test --format "{{.State.ExitCode}}"
```

Remove the stopped container:

```bash
docker rm nf-test
```

### 9. Python checks (nothing in `app/` changed, but run before every push)

With the venv activated (see `NF-P1-001-local-dev-setup.md`):

```bash
pytest
ruff check .
black --check .
mypy app tests
```

Expected: `2 passed`, `All checks passed!`, `... would be left unchanged.`, `Success: no issues found`

### 10. Clean up

Remove any leftover test containers (ignore "No such container" errors):

```bash
docker rm -f nf-test nf-port
```

Remove the local image when you no longer need it:

```bash
docker image rm nomadfinance-backend:local
```

Rebuild after any code change. The image is a snapshot, so it will not pick up edits on its own. Repeat step 1.

## Verified results (2026-09-24, Docker 29.8.0)

| Check | Result |
|---|---|
| `docker build` | Succeeds; image size 286 MB |
| `GET /health` on 8080 | `200 {"status":"ok","version":"0.1.0","environment":"local"}` |
| `GET /docs` | 200 |
| `whoami` in container | `appuser` |
| `/app` contents | only `app/`; 0 `__pycache__` / `.pyc`; no `.env`, tests or scripts |
| No `APP_ENV` | exits with code 3, `app_env Field required` |
| `PORT=9090` | `Listening at: http://0.0.0.0:9090`, `/health` 200 |
| `docker stop` | SIGTERM handled, clean shutdown in ~1 s, exit code 0 |
| pytest / ruff / black / mypy | all pass |

## Runtime environment variables

| Variable | Default in image | Set by | Notes |
|---|---|---|---|
| `APP_ENV` | none (required) | `docker run -e` / Cloud Run | `local`, `staging` or `prod`. NF-P1-003 must set `APP_ENV=prod` on the Cloud Run service. |
| `GEMINI_API_KEY` | none (required, since NF-P1-004) | `--env-file .env.local` / Cloud Run secret | Never baked into the image. Cloud Run mounts Secret Manager `gemini-api-key`. |
| `PORT` | `8080` | Cloud Run | gunicorn bind port |
| `WEB_CONCURRENCY` | `1` | Cloud Run (optional) | gunicorn workers; roughly 1 per vCPU |
| `APP_VERSION`, `LOG_LEVEL` | app defaults | optional | see `app/config.py` |

## Commits for this task

This branch (`feature/backend-docker`) carries three separate changes. Commit them separately, in this order:

**1. `.gitignore` fix (repo-wide, separate from Docker)**

The Python cache rule in the root `.gitignore` was misspelled `_pycache_/` (single underscores), so it matched nothing. It is now `__pycache__/`. No cache files were ever committed (`git ls-files` shows none), so nothing needs removing from git.

```bash
git add .gitignore
git commit -m "chore(repo): fix __pycache__ pattern in gitignore"
```

**2. NF-P1-001 docs missed in PR #5**

```bash
git add docs/api/endpoints.md docs/runbooks/NF-P1-001-local-dev-setup.md docs/runbooks/local-dev-setup.md
git commit -m "docs(backend): add NF-P1-001 runbook and health endpoint docs" -m "Refs: NF-P1-001"
```

**3. Docker (this task)**

```bash
git add backend/Dockerfile backend/.dockerignore backend/requirements.txt backend/scripts/build_docker.sh backend/README.md docs/runbooks/NF-P1-002-backend-docker.md
git commit -m "feat(backend): add multi-stage Dockerfile with gunicorn and uvicorn workers" -m "Refs: NF-P1-002"
```

Before pushing, confirm nothing else is staged or left behind:

```bash
git status
```

Only `docs/design-doc/` should remain untracked.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `failed to connect to the docker API ... dockerDesktopLinuxEngine` | Docker Desktop is not running. Start it and wait until `docker info` works (can take 1–2 minutes). |
| Container exits with `app_env Field required` or `gemini_api_key Field required` | Pass `--env-file .env.local`, and make sure `.env.local` has both `APP_ENV` and `GEMINI_API_KEY` (see NF-P1-004). |
| `Bind for 0.0.0.0:8080 failed: port is already allocated` | Something (often `uvicorn --reload` or an old `nf-test` container) already uses 8080. Stop it, run `docker rm -f nf-test`, or map another port: `-p 8081:8080`. |
| `Conflict. The container name "/nf-test" is already in use` | A previous test container still exists: `docker rm -f nf-test`. |
| Code changes not showing up | The image is a snapshot. Rebuild with `docker build` after every change. |
| `./scripts/build_docker.sh: Permission denied` (bash) | `chmod +x scripts/build_docker.sh`, or run `bash scripts/build_docker.sh`. |
| `ls: cannot access 'C:/Program Files/Git/...'` when running a container command from Git Bash | Git Bash converted a Linux path argument to a Windows path. Wrap the command: `sh -c "ls -A /app"`, or run it from PowerShell. |
| `Error while closing socket [Errno 9] Bad file descriptor` on stop | INFO-level message from the uvicorn worker during shutdown. Harmless; shutdown still completes with exit code 0. |

## Not covered here

- Cloud Run deploy: NF-P1-003
- CI image build and deploy: NF-P1-020
- Structured request logging: NF-P1-028
