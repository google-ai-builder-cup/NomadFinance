import { describe, expect, it } from "vitest";

import { ApiError } from "@/services/apiClient";
import { scamErrorView } from "@/utils/scamErrors";

describe("scamErrorView", () => {
  it.each([
    [413, "payload_too_large", "analyze.errors.tooLarge", false],
    [415, "unsupported_media_type", "analyze.errors.unsupportedType", false],
    [422, "image_unreadable", "analyze.errors.imageUnreadable", false],
    [422, "validation_failed", "analyze.errors.invalid", false],
    [408, "timeout", "analyze.errors.timeout", true],
    [504, "ai_timeout", "analyze.errors.timeout", true],
    [502, "ai_bad_response", "analyze.errors.busy", true],
    [503, "ai_busy", "analyze.errors.busy", true],
  ])("%i %s", (status, detail, messageKey, canRetry) => {
    expect(scamErrorView(new ApiError(status, detail))).toEqual({ messageKey, canRetry });
  });

  it("tells a rate-limited worker how long to wait, rounded up to whole minutes", () => {
    expect(scamErrorView(new ApiError(429, "rate_limited", 1380))).toEqual({
      messageKey: "analyze.errors.rateLimitedWait",
      canRetry: false,
      waitMinutes: 23,
    });
    expect(scamErrorView(new ApiError(429, "rate_limited")).messageKey).toBe(
      "analyze.errors.rateLimited"
    );
  });

  it("falls back to the shared messages for offline and expired sessions", () => {
    expect(scamErrorView(new ApiError(0, "Network error"))).toEqual({
      messageKey: "errors.offline",
      canRetry: true,
    });
    expect(scamErrorView(new ApiError(401, "unauthenticated"))).toEqual({
      messageKey: "errors.sessionExpired",
      canRetry: false,
    });
  });
});
