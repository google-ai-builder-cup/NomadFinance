import { FirebaseError } from "firebase/app";
import { describe, expect, it } from "vitest";

import { ApiError } from "@/services/apiClient";
import { CoachStreamDropped } from "@/services/coachService";
import { coachErrorView, toFailure } from "@/utils/coachErrors";

describe("toFailure", () => {
  it("keeps the backend's code and status from a refusal", () => {
    expect(toFailure(new ApiError(409, "session_full"))).toEqual({
      code: "session_full",
      status: 409,
      retryAfterSeconds: undefined,
    });
  });

  it("keeps Retry-After", () => {
    expect(toFailure(new ApiError(429, "rate_limited", 30)).retryAfterSeconds).toBe(30);
  });

  it("calls a request that never arrived `network`", () => {
    expect(toFailure(new ApiError(0, "Network error"))).toMatchObject({
      code: "network",
      status: 0,
    });
  });

  it("tells a stream that stalled from one that ended", () => {
    expect(toFailure(new CoachStreamDropped("timeout")).code).toBe("stream_timeout");
    expect(toFailure(new CoachStreamDropped("ended")).code).toBe("stream_dropped");
    expect(toFailure(new CoachStreamDropped("network")).code).toBe("stream_dropped");
  });

  it("does not leak the text of an unknown error", () => {
    expect(toFailure(new Error("secret stack"))).toEqual({ code: "unknown", status: 0 });
  });
});

describe("coachErrorView", () => {
  it.each([
    ["session_not_active", 409, "chat.error.sessionNotActive", "restart"],
    ["session_full", 409, "chat.error.sessionFull", "restart"],
    ["not_found", 404, "chat.error.notFound", "restart"],
    ["turn_in_progress", 409, "chat.error.inProgress", "retry"],
    ["request_in_progress", 409, "chat.error.inProgress", "retry"],
    ["validation_failed", 422, "chat.error.invalid", "none"],
    ["rate_limited", 429, "chat.error.rateLimited", "retry"],
    ["ai_busy", 503, "chat.error.busy", "retry"],
    ["ai_unavailable", 503, "chat.error.busy", "retry"],
    ["ai_bad_response", 502, "chat.error.busy", "retry"],
    ["ai_timeout", 504, "chat.error.timeout", "retry"],
    ["stream_timeout", 0, "chat.error.timeout", "retry"],
    ["stream_dropped", 0, "chat.error.dropped", "retry"],
  ])("explains %s (%i) with %s and offers %s", (code, status, messageKey, action) => {
    expect(coachErrorView({ code, status })).toEqual({ messageKey, action });
  });

  it("says how long to wait when the backend said", () => {
    expect(coachErrorView({ code: "rate_limited", status: 429, retryAfterSeconds: 12 })).toEqual({
      messageKey: "chat.error.rateLimitedWait",
      action: "retry",
      waitSeconds: 12,
    });
  });

  it("falls back to the status for a code it does not know", () => {
    expect(coachErrorView({ code: "something_new", status: 429 }).messageKey).toBe(
      "chat.error.rateLimited"
    );
    expect(coachErrorView({ code: "something_new", status: 503 }).messageKey).toBe(
      "chat.error.busy"
    );
    expect(coachErrorView({ code: "something_new", status: 504 }).messageKey).toBe(
      "chat.error.timeout"
    );
  });

  it("uses the shared words for no connection, a signed-out worker and a server fault", () => {
    expect(coachErrorView({ code: "network", status: 0 })).toEqual({
      messageKey: "errors.offline",
      action: "retry",
    });
    expect(coachErrorView({ code: "unauthenticated", status: 401 })).toEqual({
      messageKey: "errors.sessionExpired",
      action: "none",
    });
    expect(coachErrorView({ code: "internal", status: 500 })).toEqual({
      messageKey: "errors.server",
      action: "retry",
    });
  });
});

describe("toFailure for a lapsed sign-in with no connection", () => {
  it("calls Firebase's network error `network`, like a request that never arrived", () => {
    const error = new FirebaseError("auth/network-request-failed", "Network error");

    expect(toFailure(error)).toEqual({ code: "network", status: 0 });
  });

  it("leaves another Firebase error as unknown", () => {
    expect(toFailure(new FirebaseError("auth/user-disabled", "x")).code).toBe("unknown");
  });
});
