// @vitest-environment jsdom
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";
import { ApiError, apiRequest } from "@/services/apiClient";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

async function failureOf(path: string): Promise<ApiError> {
  try {
    await apiRequest(path, { method: "POST" });
  } catch (error) {
    if (error instanceof ApiError) {
      return error;
    }
    throw error;
  }
  throw new Error("The request did not fail");
}

describe("how an error answer is read", () => {
  it("keeps the code of a v2 error and the wait the backend asked for", async () => {
    server.use(handlerForMock("scam/analyze-error-rate-limited.json"));

    const error = await failureOf("/api/v2/scam/analyze");

    expect(error.status).toBe(429);
    expect(error.detail).toBe("rate_limited");
    expect(error.retryAfterSeconds).toBe(1380);
  });

  it("still reads the `detail` of a v1 error, and has no wait when none was sent", async () => {
    server.use(
      http.post("*/api/v1/anything", () =>
        HttpResponse.json({ detail: "recent_login_required" }, { status: 403 })
      )
    );

    const error = await failureOf("/api/v1/anything");

    expect(error.detail).toBe("recent_login_required");
    expect(error.retryAfterSeconds).toBeUndefined();
  });

  it("falls back to the status text when the body is not JSON", async () => {
    server.use(
      http.post(
        "*/api/v1/anything",
        () => new HttpResponse("oops", { status: 502, statusText: "Bad Gateway" })
      )
    );

    expect((await failureOf("/api/v1/anything")).detail).toBe("Bad Gateway");
  });
});
