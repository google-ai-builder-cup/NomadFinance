# API Endpoints

Base URL: the Cloud Run service URL (local: `http://127.0.0.1:8080`).

All endpoints live under `/api/v1/` except `/health`. Interactive docs are served at `/docs` (Swagger) and the schema at `/openapi.json`.

| Method | Path | Auth | Rate limit | Owner task |
|---|---|---|---|---|
| GET | `/health` | Public | None | NF-P1-001 |

---

## `GET /health`

Liveness probe for Cloud Run and uptime checks. Unversioned so its path never changes across API versions.

- **Auth:** public, no token required
- **Request:** no parameters, no body
- **Response `200`:** `HealthResponse` (`app/schemas/common.py`)

| Field | Type | Description |
|---|---|---|
| `status` | `"ok"` | Always `"ok"` when the process is serving |
| `version` | string | `APP_VERSION` setting |
| `environment` | string | `APP_ENV` setting: `local`, `staging` or `prod` |

Example:

```bash
curl -s http://127.0.0.1:8080/health
```

```json
{"status": "ok", "version": "0.1.0", "environment": "local"}
```

- **Errors:** none from the handler. If required settings are missing, the process refuses to start, so no response is served.
