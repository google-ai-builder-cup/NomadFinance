import { ApiError, apiRequest } from "@/services/apiClient";

/** The backend's code for "sign in again before this". Must match backend RECENT_LOGIN_REQUIRED. */
const RECENT_LOGIN_REQUIRED = "recent_login_required";

const DELETED_FLAG = "nomadfinance.accountDeleted";

export function isRecentLoginRequired(error: unknown): boolean {
  return (
    error instanceof ApiError && error.status === 403 && error.detail === RECENT_LOGIN_REQUIRED
  );
}

/**
 * Delete the signed-in user's account: the backend removes the Firestore profile and
 * everything under it, the uploaded files and the sign-in account (NF-P1-023). Only the
 * token's own account can be named, so there is nothing to pass in.
 */
export async function deleteAccount(): Promise<void> {
  await apiRequest("/api/v1/users/me", { method: "DELETE" });
}

/** Remember to tell the person their account is gone on the landing page they are sent to. */
export function rememberAccountDeleted(): void {
  try {
    sessionStorage.setItem(DELETED_FLAG, "1");
  } catch {
    // Only the notice is lost; the account is already deleted.
  }
}

/** Whether the landing page should say the account was deleted. Read with `clear...` after. */
export function accountWasDeleted(): boolean {
  try {
    return sessionStorage.getItem(DELETED_FLAG) === "1";
  } catch {
    return false;
  }
}

export function clearAccountDeletedNotice(): void {
  try {
    sessionStorage.removeItem(DELETED_FLAG);
  } catch {
    // Nothing stored.
  }
}
