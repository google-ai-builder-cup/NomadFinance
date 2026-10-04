import { describe, expect, it } from "vitest";

import { safeWebUrl } from "@/utils/safeUrl";

describe("safeWebUrl", () => {
  it.each([
    ["https://www.mom.gov.sg/complaint", "https://www.mom.gov.sg/complaint"],
    ["http://example.org/path?a=1", "http://example.org/path?a=1"],
    ["  https://example.org  ", "https://example.org/"],
  ])("keeps a web address: %s", (input, expected) => {
    expect(safeWebUrl(input)).toBe(expected);
  });

  it.each([
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    " javascript:alert(1)",
    "java\tscript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "blob:https://example.org/uuid",
    "//example.org/protocol-relative",
    "/just/a/path",
    "not a url",
    "",
  ])("refuses %j", (input) => {
    expect(safeWebUrl(input)).toBeNull();
  });

  it("refuses a missing value", () => {
    expect(safeWebUrl(null)).toBeNull();
    expect(safeWebUrl(undefined)).toBeNull();
  });
});
