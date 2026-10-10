# Load test (NF-HR-007)

Locust scenarios against the real API with Gemini replaced by a stand-in that answers late. It
measures what the service itself does under concurrency (event loop, thread pool, Firestore,
streams, the PDF renderer), not Gemini, and it never touches production.

```bash
# 1. Emulators (from frontend/)
firebase emulators:start --only auth,firestore,storage --project demo-nomadfinance

# 2. Reference data (from data-scripts/, with the emulator variables set) and the workers
python -m src.loaders.corridors && python -m src.loaders.cost_baselines \
  && python -m src.loaders.scam_taxonomy && python -m src.loaders.ilo_natlex
cd ../backend && python -m tests.load.seed --users 120

# 3. The API, started as production starts it (one gunicorn UvicornWorker). The limits are raised
#    so that 100 simulated workers are not refused by the per-worker limits they would meet alone.
RATE_LIMIT_DEFAULT=100000/minute RATE_LIMIT_AI=100000/minute RATE_LIMIT_SCAM_ANALYZE=100000/hour \
  gunicorn tests.load.load_app:app --worker-class uvicorn_worker.UvicornWorker --timeout 0 \
  -b 127.0.0.1:8080

# 4. Locust, installed outside the repo (it is not in requirements-dev.txt):
python -m venv /tmp/locust && /tmp/locust/bin/pip install locust==2.32.5
LOAD_WORKERS=120 LOAD_SCENARIO=all /tmp/locust/bin/locust -f tests/load/locustfile.py \
  --headless -u 30 -r 10 -t 120s --host http://127.0.0.1:8080 --csv out
curl -s "127.0.0.1:8080/__load/reads"        # documents read per route
```

Set the emulator variables (`FIRESTORE_EMULATOR_HOST=127.0.0.1:8085`,
`FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099`, `STORAGE_EMULATOR_HOST=http://127.0.0.1:9199`,
`FIREBASE_PROJECT_ID=demo-nomadfinance`, `APP_ENV=local`) in every shell.

- `LOAD_SCENARIO`: `scam`, `coach`, `v1` or `all`. `LOAD_WORKERS`: how many seeded workers.
- Each simulated user is one worker, so two users never share a Coach session. A run that is
  stopped leaves turns "running" for up to 90 s (`STALE_AFTER`), so clear Firestore between runs
  (`DELETE http://127.0.0.1:8085/emulator/v1/projects/demo-nomadfinance/databases/(default)/documents`)
  and seed again.
- `LOAD_GEMINI_SCALE` multiplies the stand-in's delays (0 makes it instant).
- The session start is run without its transaction unless `LOAD_KEEP_SESSION_TRANSACTION=1`:
  the emulator makes a query inside a transaction contend across workers (see the report).
- Timings come from a laptop, so compare runs of the same machine, not across machines.
