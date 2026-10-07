import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/services/apiClient";
import { analyzeScam, buildAnalyzeInit } from "@/services/scamService";

vi.mock("@/services/apiClient", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/apiClient")>()),
  apiRequest: vi.fn(),
}));

// Braces: a function returned from beforeEach is run after the test as its clean-up, and the
// mock itself is a function.
beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
});

describe("buildAnalyzeInit", () => {
  it("sends a message as JSON, trimmed, with the corridor only when there is one", () => {
    const init = buildAnalyzeInit({
      input: { kind: "text", text: "  Pay 800 SGD  " },
      language: "hi",
      corridorId: "SG-IN",
    });

    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({
      text: "Pay 800 SGD",
      language: "hi",
      corridor_id: "SG-IN",
    });

    const without = buildAnalyzeInit({ input: { kind: "text", text: "hi" }, language: "en" });
    expect(JSON.parse(without.body as string)).toEqual({ text: "hi", language: "en" });
  });

  it("sends a screenshot as a form and leaves the Content-Type to the browser", () => {
    const file = new File(["x"], "chat.png", { type: "image/png" });
    const init = buildAnalyzeInit({
      input: { kind: "screenshot", file },
      language: "tl",
      corridorId: "SG-PH",
    });

    const form = init.body as FormData;
    expect(form.get("image")).toBeInstanceOf(File);
    expect(form.get("language")).toBe("tl");
    expect(form.get("corridor_id")).toBe("SG-PH");
    expect(init.headers).toBeUndefined();
  });
});

// An Error is compared by message alone, so a test reads the status from the caught error.
async function statusOfFailure(): Promise<number | null> {
  try {
    await analyzeScam({ input: { kind: "text", text: "hi" }, language: "en" });
  } catch (error) {
    return error instanceof ApiError ? error.status : -1;
  }
  return null;
}

describe("analyzeScam", () => {
  it("returns the backend's answer", async () => {
    vi.mocked(apiRequest).mockResolvedValue(Response.json({ id: "k_01" }));

    const result = await analyzeScam({ input: { kind: "text", text: "hi" }, language: "en" });

    expect(result.id).toBe("k_01");
    expect(vi.mocked(apiRequest).mock.calls[0][0]).toBe("/api/v2/scam/analyze");
  });

  it("reports a spent timer as a timeout, not as being offline", async () => {
    // The 60 s timer, fired by hand: apiClient reports the aborted fetch as status 0.
    const timer = new AbortController();
    const spy = vi.spyOn(AbortSignal, "timeout").mockReturnValue(timer.signal);
    vi.mocked(apiRequest).mockImplementation(async () => {
      timer.abort();
      throw new ApiError(0, "Network error");
    });

    const status = await statusOfFailure();
    spy.mockRestore();
    expect(status).toBe(408);
  });

  it("leaves any other failure as it is", async () => {
    vi.mocked(apiRequest).mockRejectedValue(new ApiError(0, "Network error"));

    expect(await statusOfFailure()).toBe(0);
  });
});
