import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/services/apiClient";
import { compareRemittance } from "@/services/remittanceService";

vi.mock("@/services/apiClient", () => ({ apiRequest: vi.fn() }));

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
});

describe("compareRemittance", () => {
  it("posts the corridor and amount as JSON and returns the comparison", async () => {
    const comparison = { corridor_id: "SG-PH", send_amount: 645 };
    vi.mocked(apiRequest).mockResolvedValue(new Response(JSON.stringify(comparison)));

    const result = await compareRemittance({ corridor_id: "SG-PH", amount: 645 });

    expect(result).toEqual(comparison);
    const [path, init] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/api/v1/remittance/compare");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(String(init?.body))).toEqual({ corridor_id: "SG-PH", amount: 645 });
  });

  it("lets an API error through for the page to explain", async () => {
    vi.mocked(apiRequest).mockRejectedValue(new Error("API 404"));

    await expect(compareRemittance({ corridor_id: "MY-ID", amount: 700 })).rejects.toThrow(
      "API 404"
    );
  });
});
