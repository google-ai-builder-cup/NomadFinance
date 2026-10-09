import { FirebaseError } from "firebase/app";

import { CoachStreamDropped } from "@/services/coachService";
import { ApiError } from "@/services/apiClient";
import type { CoachFailure } from "@/types/coach";
import { errorMessageKey } from "@/utils/errors";

export interface CoachErrorView {
  /** i18n key in the `coach` namespace (the shared `errors.*` keys resolve from there too). */
  messageKey: string;
  /**
   * What the worker can do about it: send the same turn again, start a new interview, or only
   * carry on (a different answer, or signing in again).
   */
  action: "retry" | "restart" | "none";
  /** Seconds until the limit frees up, for the rate-limit message. */
  waitSeconds?: number;
}

/** Whatever stopped a turn, as the one shape the chat keeps. */
export function toFailure(error: unknown): CoachFailure {
  if (error instanceof CoachStreamDropped) {
    return { code: error.reason === "timeout" ? "stream_timeout" : "stream_dropped", status: 0 };
  }
  if (error instanceof ApiError) {
    return {
      code: error.status === 0 ? "network" : error.detail,
      status: error.status,
      retryAfterSeconds: error.retryAfterSeconds,
    };
  }
  // Offline with an ID token that has lapsed: Firebase cannot refresh it, so the call fails
  // before the request is made. To the worker that is the same as having no connection.
  if (error instanceof FirebaseError && error.code === "auth/network-request-failed") {
    return { code: "network", status: 0 };
  }
  return { code: "unknown", status: 0 };
}

/** What to tell a worker whose turn failed, by the backend's code (docs/api/v2-coach.md). */
export function coachErrorView(failure: CoachFailure): CoachErrorView {
  const { code, status } = failure;
  switch (code) {
    case "session_not_active":
      return { messageKey: "chat.error.sessionNotActive", action: "restart" };
    case "session_full":
      return { messageKey: "chat.error.sessionFull", action: "restart" };
    case "not_found":
      return { messageKey: "chat.error.notFound", action: "restart" };
    case "turn_in_progress":
    case "request_in_progress":
      return { messageKey: "chat.error.inProgress", action: "retry" };
    case "plan_not_ready":
      return { messageKey: "score.error.notReady", action: "none" };
    case "score_unavailable":
      return { messageKey: "score.error.unavailable", action: "retry" };
    case "validation_failed":
      return { messageKey: "chat.error.invalid", action: "none" };
    case "rate_limited":
      return failure.retryAfterSeconds === undefined
        ? { messageKey: "chat.error.rateLimited", action: "retry" }
        : {
            messageKey: "chat.error.rateLimitedWait",
            action: "retry",
            waitSeconds: failure.retryAfterSeconds,
          };
    case "ai_busy":
    case "ai_unavailable":
    case "ai_bad_response":
      return { messageKey: "chat.error.busy", action: "retry" };
    case "ai_timeout":
    case "stream_timeout":
      return { messageKey: "chat.error.timeout", action: "retry" };
    case "stream_dropped":
      return { messageKey: "chat.error.dropped", action: "retry" };
    default:
      break;
  }
  if (status === 429) {
    return { messageKey: "chat.error.rateLimited", action: "retry" };
  }
  if (status === 502 || status === 503) {
    return { messageKey: "chat.error.busy", action: "retry" };
  }
  if (status === 504) {
    return { messageKey: "chat.error.timeout", action: "retry" };
  }
  // The shared messages: no connection, signed out, a server problem.
  const messageKey = errorMessageKey(new ApiError(status, code));
  return { messageKey, action: status === 401 ? "none" : "retry" };
}
