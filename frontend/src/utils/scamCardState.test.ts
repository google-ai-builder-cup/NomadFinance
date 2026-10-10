import { describe, expect, it } from "vitest";

import type { ScamCheckList, ScamCheckSummary } from "@/types/scam";
import { scamCardState } from "@/utils/scamCardState";

function check(overrides: Partial<ScamCheckSummary>): ScamCheckSummary {
  return {
    id: "k_01",
    created_at: "2026-10-08T09:00:00Z",
    input_type: "text",
    language: "en",
    is_scam: true,
    scam_type: "illegal_recruitment_fee",
    risk_level: "high",
    confidence: 0.9,
    excerpt: "Pay the fee",
    reported: false,
    ...overrides,
  };
}

const list = (...items: ScamCheckSummary[]): ScamCheckList => ({ items, next_cursor: null });

describe("what the Scam Check card says", () => {
  it("invites a first check when there is no history", () => {
    expect(scamCardState(list())).toEqual({ kind: "none" });
  });

  it.each(["low", "medium", "high"] as const)("names a %s risk scam", (risk_level) => {
    expect(scamCardState(list(check({ risk_level })))).toEqual({
      kind: "last",
      result: risk_level,
      at: "2026-10-08T09:00:00Z",
    });
  });

  it("calls a message that is not a scam benign, whatever its risk level", () => {
    const state = scamCardState(list(check({ is_scam: false, risk_level: "high" })));

    expect(state).toEqual({ kind: "last", result: "benign", at: "2026-10-08T09:00:00Z" });
  });

  it("reads only the newest check", () => {
    const state = scamCardState(
      list(check({ risk_level: "low", created_at: "2026-10-09T09:00:00Z" }), check({}))
    );

    expect(state).toMatchObject({ result: "low", at: "2026-10-09T09:00:00Z" });
  });

  it("never prints a risk level this version does not know", () => {
    const unknown = check({ risk_level: "catastrophic" as ScamCheckSummary["risk_level"] });

    expect(scamCardState(list(unknown))).toMatchObject({ kind: "last", result: "medium" });
  });
});
