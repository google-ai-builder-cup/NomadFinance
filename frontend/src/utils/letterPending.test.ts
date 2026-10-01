import { describe, expect, it } from "vitest";

import { letterPendingKey } from "@/utils/letterPending";

describe("letterPendingKey", () => {
  it.each([
    ["ai_daily_limit", "contract.complaint.missing.reason.ai_daily_limit"],
    ["ai_busy", "contract.complaint.missing.reason.ai_busy"],
    ["ai_failed", "contract.complaint.missing.reason.ai_failed"],
    ["no_template", "contract.complaint.missing.reason.no_template"],
  ] as const)("words %s", (reason, key) => {
    expect(letterPendingKey(reason)).toBe(key);
  });

  it("keeps the general message without a reason", () => {
    expect(letterPendingKey(null)).toBe("contract.complaint.missing.stillPending");
    expect(letterPendingKey(undefined)).toBe("contract.complaint.missing.stillPending");
  });
});
