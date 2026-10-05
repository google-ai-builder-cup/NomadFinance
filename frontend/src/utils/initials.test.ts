import { describe, expect, it } from "vitest";

import { initialsOf } from "@/utils/initials";

describe("initialsOf", () => {
  it("takes the start of a name or email", () => {
    expect(initialsOf("Priya Rao")).toBe("PR");
    expect(initialsOf("priya@example.com")).toBe("PR");
  });

  it("uses the leading digits of a phone number", () => {
    expect(initialsOf("+6581234567")).toBe("65");
  });

  it("keeps letters outside the Latin script", () => {
    expect(initialsOf("प्रिया")).toHaveLength(2);
  });

  it("falls back to a question mark", () => {
    expect(initialsOf("")).toBe("?");
    expect(initialsOf("+-")).toBe("?");
  });
});
