import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/services/apiClient";
import { scamErrorView, scamReportErrorView } from "@/utils/scamErrors";

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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("scamReportErrorView", () => {
  it.each([
    [409, "not_a_scam", "report.errors.notAScam", false],
    [422, "validation_failed", "report.errors.invalid", false],
    [404, "not_found", "report.errors.expired", false],
    [429, "rate_limited", "report.errors.rateLimited", true],
  ])("%i %s", (status, detail, messageKey, canRetry) => {
    expect(scamReportErrorView(new ApiError(status, detail))).toEqual({ messageKey, canRetry });
  });

  it("lets the worker try again after a server error or a lost connection", () => {
    expect(scamReportErrorView(new ApiError(500, "internal_error")).canRetry).toBe(true);
    expect(scamReportErrorView(new ApiError(0, "Network error"))).toEqual({
      messageKey: "errors.offline",
      canRetry: true,
    });
  });

  it("treats an error that is not the API's as one to retry", () => {
    // These tests run in Node, which has no `navigator` before version 21 (CI is on 20), and the
    // fallback message asks it whether the browser is online.
    vi.stubGlobal("navigator", { onLine: true });

    expect(scamReportErrorView(new Error("boom")).canRetry).toBe(true);
  });
});
