# API Endpoints

Base URL: the Cloud Run service URL (local: `http://127.0.0.1:8080`).

All endpoints live under `/api/v1/` except `/health`. Interactive docs are served at `/docs` (Swagger) and the schema at `/openapi.json`.

## Authentication

Protected endpoints require a Firebase Auth ID token as a bearer token:

```
Authorization: Bearer <firebase-id-token>
```

Add `user: AuthenticatedUser = Depends(get_current_user)` (`app/dependencies.py`) to any
endpoint that isn't public. It verifies the token via the Firebase Admin SDK
(`app/core/security.py`) and returns the caller's `uid`/`email`/etc.; a missing, invalid,
expired or revoked token gets a `401`. Endpoints that skip this dependency are public and
must say so explicitly in their own doc section below.

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
