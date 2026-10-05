import { describe, expect, it } from "vitest";

import { CORRIDOR_IDS } from "@/types/enums";
import {
  FX_REFRESH_HOURS,
  INDUSTRY_FACTS,
  MEASURED_METRICS,
  PROTECTED_WORDS,
} from "@/utils/landingMetrics";
import { SUPPORTED_LANGUAGES } from "@/lib/languages";

describe("landing metrics", () => {
  it("gives every industry figure a named source", () => {
    for (const fact of Object.values(INDUSTRY_FACTS)) {
      expect(fact.source.trim()).not.toBe("");
      expect(fact.value).toBeGreaterThan(0);
    }
  });

  it("shows no timing figure until one has been measured", () => {
    expect(MEASURED_METRICS.contractAnalysisSeconds).toBeNull();
  });

  it("has one word per supported language for the cycling line", () => {
    expect(PROTECTED_WORDS).toHaveLength(SUPPORTED_LANGUAGES.length);
  });

  it("matches the scope: six corridors, FX refreshed every two hours", () => {
    expect(CORRIDOR_IDS).toHaveLength(6);
    expect(FX_REFRESH_HOURS).toBe(2);
  });
});
