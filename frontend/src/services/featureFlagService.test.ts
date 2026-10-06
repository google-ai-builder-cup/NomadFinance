import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/services/apiClient";
import { getFeatureFlags, parseFeatureFlags } from "@/services/featureFlagService";

vi.mock("@/services/apiClient", () => ({ apiRequest: vi.fn() }));

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
});

describe("parseFeatureFlags", () => {
  it("reads each module's answer", () => {
    expect(parseFeatureFlags({ coach: true, scam: false })).toEqual({ coach: true, scam: false });
    expect(parseFeatureFlags({ coach: false, scam: true })).toEqual({ coach: false, scam: true });
  });

  it("turns a module on only for the boolean true", () => {
    expect(parseFeatureFlags({ coach: "true", scam: 1 })).toEqual({ coach: false, scam: false });
  });

  it("treats a missing key as off and ignores keys it does not know", () => {
    expect(parseFeatureFlags({ coach: true, partner: true })).toEqual({
      coach: true,
      scam: false,
    });
  });

  it.each([null, undefined, "yes", 7, []])("reads %j as everything off", (body) => {
    expect(parseFeatureFlags(body)).toEqual({ coach: false, scam: false });
  });
});

describe("getFeatureFlags", () => {
  it("asks the v2 flags route and returns the parsed answer", async () => {
    vi.mocked(apiRequest).mockResolvedValue(
      new Response(JSON.stringify({ coach: true, scam: false }))
    );

    const flags = await getFeatureFlags();

    expect(flags).toEqual({ coach: true, scam: false });
    expect(vi.mocked(apiRequest).mock.calls[0][0]).toBe("/api/v2/flags");
  });

  it("lets an API error through for the hook to treat as everything off", async () => {
    vi.mocked(apiRequest).mockRejectedValue(new Error("API 404: Not Found"));

    await expect(getFeatureFlags()).rejects.toThrow("API 404");
  });
});
