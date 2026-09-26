import { FirebaseError } from "firebase/app";

import { ApiError } from "@/services/apiClient";

// Firestore codes have no prefix; Firebase Auth codes start with "auth/".
const FIREBASE_MESSAGE_KEYS: Readonly<Record<string, string>> = {
  unavailable: "errors.offline",
  "auth/network-request-failed": "errors.offline",
  unauthenticated: "errors.sessionExpired",
  "auth/user-token-expired": "errors.sessionExpired",
  "resource-exhausted": "errors.tooManyRequests",
};

const RETRYABLE_FIREBASE_CODES = new Set([
  "unavailable",
  "deadline-exceeded",
  "aborted",
  "internal",
]);

function apiMessageKey(status: number): string {
  if (status === 0) {
    return "errors.offline";
  }
  if (status === 401) {
    return "errors.sessionExpired";
  }
  if (status === 429) {
    return "errors.tooManyRequests";
  }
  return status >= 500 ? "errors.server" : "errors.generic";
}

/** i18n key that tells a person, in plain words, why a request failed. */
export function errorMessageKey(error: unknown): string {
  if (error instanceof ApiError) {
    return apiMessageKey(error.status);
  }
  if (error instanceof FirebaseError && error.code in FIREBASE_MESSAGE_KEYS) {
    return FIREBASE_MESSAGE_KEYS[error.code];
  }
  return navigator.onLine ? "errors.generic" : "errors.offline";
}

/**
 * Whether repeating the same request by itself can succeed. A 4xx answer will not change on
 * a repeat, and a 429 needs a longer wait than an automatic retry gives it.
 */
export function isRetryable(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status === 0 || error.status === 408 || error.status >= 500;
  }
  if (error instanceof FirebaseError) {
    return RETRYABLE_FIREBASE_CODES.has(error.code);
  }
  return true;
}
