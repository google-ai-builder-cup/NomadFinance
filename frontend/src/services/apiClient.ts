import { getIdToken } from "@/services/authService";

// Address of the NomadFinance backend. Empty means "same origin": in development Vite
// forwards /api to the local backend (vite.config.ts). A deployed site needs this set, and
// the backend must allow the site's origin (CORS, NF-P1-027).
const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

/** Whether calls to the backend can work here. Features that need it stay hidden otherwise. */
export const isApiConfigured = import.meta.env.DEV || baseUrl !== "";

export class ApiError extends Error {
  constructor(
    /** HTTP status; 0 means the request never reached the backend (offline, blocked). */
    readonly status: number,
    /** The backend's `detail` text, or a code such as "recent_login_required". */
    readonly detail: string,
    /** Seconds the backend asked to wait (`Retry-After`), when it sent one. */
    readonly retryAfterSeconds?: number
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

// v1 answers `{detail}`; v2 answers `{code, message, request_id}`. The code is what a screen
// branches on, so it is kept when there is no `detail`.
async function errorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown; code?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    return typeof body.code === "string" ? body.code : response.statusText;
  } catch {
    return response.statusText;
  }
}

function retryAfterSeconds(response: Response): number | undefined {
  const seconds = Number(response.headers.get("Retry-After"));
  return Number.isFinite(seconds) && seconds > 0 ? seconds : undefined;
}

/** Call a backend endpoint as the signed-in user. Throws ApiError for any failure. */
export async function apiRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getIdToken();
  if (token === null) {
    throw new ApiError(401, "Not signed in");
  }
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Network error");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorDetail(response), retryAfterSeconds(response));
  }
  return response;
}
