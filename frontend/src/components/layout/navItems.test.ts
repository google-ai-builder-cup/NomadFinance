import { describe, expect, it } from "vitest";

import en from "@/i18n/en.json";
import {
  ALL_PILLAR_ITEMS,
  MODULE_ITEMS,
  PILLAR_ITEMS,
  pillarForPath,
  visiblePillarItems,
} from "@/components/layout/navItems";
import { PILLAR_KEYS, PILLAR_STYLES } from "@/utils/pillars";

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

describe("the six pillars", () => {
  it("are the four of v1.0 and the two Future Scope modules, each with its own page", () => {
    expect(PILLAR_KEYS).toHaveLength(6);
    expect(ALL_PILLAR_ITEMS).toHaveLength(6);
    expect(ALL_PILLAR_ITEMS.map((item) => item.pillar).sort()).toEqual([...PILLAR_KEYS].sort());
    expect(new Set(ALL_PILLAR_ITEMS.map((item) => item.to)).size).toBe(6);
    expect(MODULE_ITEMS.map((item) => item.to)).toEqual(["/coach", "/scam-check"]);
  });

  it("keep the four-pillar helpers as they were", () => {
    expect(PILLAR_ITEMS).toHaveLength(4);
    expect(pillarForPath("/scam-check")).toBeNull();
    expect(pillarForPath("/coach")).toBeNull();
  });

  it("give a worker a module only while its flag is on", () => {
    const names = (flags: { coach: boolean; scam: boolean }) =>
      visiblePillarItems(flags).map((item) => item.pillar);

    expect(names({ coach: false, scam: false })).toEqual([
      "remit",
      "contract",
      "radar",
      "identity",
    ]);
    expect(names({ coach: false, scam: true })).toEqual([
      "remit",
      "contract",
      "radar",
      "identity",
      "scam",
    ]);
    expect(names({ coach: true, scam: true })).toHaveLength(6);
  });

  it("have a style, and every string a card and the landing page need, in English", () => {
    const text = en as unknown as {
      pillars: Record<string, { name: string; description: string }>;
      landing: { pillars: { items: Record<string, Record<string, string>> } };
      dashboard: { widgets: Record<string, { open?: string }> };
      visual: { illustration: Record<string, string> };
    };
    const modules = ["scam", "coach"] as const;

    for (const pillar of PILLAR_KEYS) {
      expect(PILLAR_STYLES[pillar].tile).toContain(`bg-${pillar}`);
      expect(text.landing.pillars.items[pillar]).toMatchObject({
        b1: expect.any(String),
        b2: expect.any(String),
        b3: expect.any(String),
      });
      expect(text.visual.illustration[pillar]).toEqual(expect.any(String));
    }
    for (const item of ALL_PILLAR_ITEMS) {
      const key = item.nameKey.split(".")[1];
      expect(text.pillars[key].name).toEqual(expect.any(String));
      expect(text.pillars[key].description).toEqual(expect.any(String));
    }
    for (const pillar of modules) {
      expect(text.dashboard.widgets[pillar].open).toEqual(expect.any(String));
    }
  });
});
