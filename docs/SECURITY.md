# Security

NomadFinance handles migrant workers' contracts, pay records and complaints. This page says how to report a problem and what is in place. The detail, with evidence, is in [`runbooks/NF-P4-004-security-audit.md`](runbooks/NF-P4-004-security-audit.md).

## Reporting a problem

Tell a team member directly (Devam, Aditya or Pranjal) or open a private note in the team chat. Please do not put a vulnerability, a key or a worker's data in a public issue or a pull request. If a key may have leaked, say so at once: the key is replaced first and the question of how it leaked comes second.

## What protects the app

| Layer | Control |
|---|---|
| Sign-in | Firebase Auth, phone and Google only. Anonymous and email sign-in are off. SMS is allowed to the eleven countries the app serves. |
| API | Every endpoint except `/health` needs a Firebase ID token, verified with its signature, audience, issuer, expiry and revocation. A test sends 21 kinds of bad token to every route. |
| Scheduled jobs | `/api/v1/internal/*` accept only Cloud Scheduler's signed token from one service account. |
| Data in the browser | Firestore and Storage rules let a worker read only their own documents. Everything a worker writes, apart from their profile and marking alerts read, goes through the API. The rules are tested, including cross-user reads and collection-group queries. |
| Abuse | 60 requests a minute per worker, 10 for endpoints that call Gemini, and a 10 MB upload cap. Uploads are identified by their content, not by the name or type the browser claims. |
| Secrets | Only in Secret Manager, readable by the backend's own service account. None in the repository or its history, or in the built app. |
| Deployment | Keyless GitHub-to-Google deploys. The API's documentation pages are served only in local development. |

## Rules for contributors

- Never commit a key, token, password or `.env` file. Only `.env.example` files with placeholder names.
- Every new API endpoint uses `Depends(get_current_user)` unless it is deliberately public; the test `test_auth_matrix.py` fails otherwise.
- An endpoint that calls Gemini also uses `Depends(limit_ai_calls)`.
- Anything a worker can write straight to Firestore needs a rule that checks the shape of the data. The backend must never assume that data is well formed.
- Do not log a person's pay, text, phone number or email.
