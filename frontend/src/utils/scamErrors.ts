import { ApiError } from "@/services/apiClient";
import { errorMessageKey } from "@/utils/errors";

export interface ScamErrorView {
  /** i18n key in the `scam` namespace (shared `errors.*` keys resolve from there too). */
  messageKey: string;
  /** Whether sending the same thing again can work; a refused input must change first. */
  canRetry: boolean;
  /** Minutes until the hourly limit frees up, for the 429 message. */
  waitMinutes?: number;
}

/** What to tell a worker whose check failed, by the backend's error code (v2-scam.md). */
export function scamErrorView(error: unknown): ScamErrorView {
  if (!(error instanceof ApiError)) {
    return { messageKey: errorMessageKey(error), canRetry: true };
  }
  const { status, detail } = error;
  if (status === 413) {
    return { messageKey: "analyze.errors.tooLarge", canRetry: false };
  }
  if (status === 415) {
    return { messageKey: "analyze.errors.unsupportedType", canRetry: false };
  }
  if (status === 422) {
    return detail === "image_unreadable"
      ? { messageKey: "analyze.errors.imageUnreadable", canRetry: false }
      : { messageKey: "analyze.errors.invalid", canRetry: false };
  }
  if (status === 429) {
    const waitMinutes =
      error.retryAfterSeconds === undefined ? undefined : Math.ceil(error.retryAfterSeconds / 60);
    return {
      messageKey:
        waitMinutes === undefined ? "analyze.errors.rateLimited" : "analyze.errors.rateLimitedWait",
      canRetry: false,
      waitMinutes,
    };
  }
  if (status === 408 || status === 504) {
    return { messageKey: "analyze.errors.timeout", canRetry: true };
  }
  if (status === 502 || status === 503) {
    return { messageKey: "analyze.errors.busy", canRetry: true };
  }
  return { messageKey: errorMessageKey(error), canRetry: status === 0 || status >= 500 };
}
