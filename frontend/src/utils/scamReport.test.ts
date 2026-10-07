import { describe, expect, it } from "vitest";

import type { ScamIndicator } from "@/types/scam";
import {
  buildReportRequest,
  canSendReport,
  clampReportText,
  initialTicked,
  MAX_REPORT_CHARS,
  MAX_REPORT_CONTACTS,
  reportTextLength,
  scamEntitySlug,
  toggleTicked,
} from "@/utils/scamReport";

const contact = (id: string): ScamIndicator => ({
  id,
  kind: "phone",
  value: `65900000${id}`,
  flags: [],
  seen: null,
});
const contacts = (count: number) =>
  Array.from({ length: count }, (_, index) => contact(`c${index}`));

describe("the report text", () => {
  it("counts characters the way the server does, not UTF-16 units", () => {
    expect(reportTextLength("abc")).toBe(3);
    expect(reportTextLength("😀😀")).toBe(2);
    expect("😀😀".length).toBe(4);
  });

  it("is left alone up to the limit and cut at it beyond", () => {
    const exact = "a".repeat(MAX_REPORT_CHARS);

    expect(clampReportText(exact)).toBe(exact);
    expect(clampReportText(exact + "b")).toBe(exact);
  });

  it("is never cut through the middle of a character", () => {
    const clamped = clampReportText("😀".repeat(MAX_REPORT_CHARS + 5));

    expect(reportTextLength(clamped)).toBe(MAX_REPORT_CHARS);
    expect(clamped.endsWith("😀")).toBe(true);
  });

  it("can be sent when it says something and not over the limit", () => {
    expect(canSendReport("Pay the fee today")).toBe(true);
    expect(canSendReport("")).toBe(false);
    expect(canSendReport("   \n ")).toBe(false);
    expect(canSendReport("a".repeat(MAX_REPORT_CHARS))).toBe(true);
    expect(canSendReport("a".repeat(MAX_REPORT_CHARS + 1))).toBe(false);
  });
});

describe("the ticked contacts", () => {
  it("start with every contact ticked", () => {
    expect(initialTicked(contacts(2))).toEqual(["c0", "c1"]);
    expect(initialTicked([])).toEqual([]);
  });

  it("start with only the first ten when there are more", () => {
    const ticked = initialTicked(contacts(12));

    expect(ticked).toHaveLength(MAX_REPORT_CONTACTS);
    expect(ticked).not.toContain("c10");
  });

  it("can be unticked and ticked again", () => {
    const off = toggleTicked(["c0", "c1"], "c0");
    expect(off).toEqual(["c1"]);
    expect(toggleTicked(off, "c0")).toEqual(["c1", "c0"]);
  });

  it("refuse an eleventh tick, which the contract would answer with a 422", () => {
    const full = initialTicked(contacts(12));

    expect(toggleTicked(full, "c10")).toEqual(full);
    // Unticking one makes room.
    expect(toggleTicked(toggleTicked(full, "c0"), "c10")).toContain("c10");
  });
});

describe("buildReportRequest", () => {
  it("sends the text as it stands and the ticked contacts, in the message's order", () => {
    const request = buildReportRequest("  Fee due  ", contacts(3), ["c2", "c0"]);

    expect(request).toEqual({ indicator_ids: ["c0", "c2"], description: "Fee due" });
  });

  it("sends no contact when every one was unticked", () => {
    expect(buildReportRequest("Fee due", contacts(2), []).indicator_ids).toEqual([]);
  });

  it("never sends an id the check does not have", () => {
    expect(buildReportRequest("Fee due", contacts(1), ["c0", "stale"]).indicator_ids).toEqual([
      "c0",
    ]);
  });

  it("carries nothing but those two fields", () => {
    expect(Object.keys(buildReportRequest("Fee due", contacts(1), ["c0"])).sort()).toEqual([
      "description",
      "indicator_ids",
    ]);
  });
});

describe("scamEntitySlug", () => {
  it("names the Radar profile of a kind of scam the way the backend does", () => {
    expect(scamEntitySlug("illegal_recruitment_fee")).toBe("scam-illegal-recruitment-fee");
    expect(scamEntitySlug("lottery")).toBe("scam-lottery");
  });
});
