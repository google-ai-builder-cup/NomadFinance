import { describe, expect, it } from "vitest";

import { pillarForPath } from "@/components/layout/navItems";

describe("pillarForPath", () => {
  it("finds the pillar for its own page and for pages inside it", () => {
    expect(pillarForPath("/radar")?.pillar).toBe("radar");
    expect(pillarForPath("/radar/entity/some-business")?.pillar).toBe("radar");
    expect(pillarForPath("/contract/history")?.pillar).toBe("contract");
    expect(pillarForPath("/identity/export")?.pillar).toBe("identity");
    expect(pillarForPath("/remittance")?.pillar).toBe("remit");
  });

  it("does not match a path that only starts with the same letters", () => {
    expect(pillarForPath("/radars")).toBeNull();
  });

  it("returns null outside the four pillars", () => {
    expect(pillarForPath("/dashboard")).toBeNull();
    expect(pillarForPath("/profile")).toBeNull();
  });
});
