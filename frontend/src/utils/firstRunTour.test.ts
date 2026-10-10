// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { hasSeenTour, markTourSeen, tourSteps, tourStorageKey } from "@/utils/firstRunTour";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("which steps the tour has", () => {
  it.each([
    [{ scam: true, coach: true }, ["scam", "coach", "outro"]],
    [{ scam: true, coach: false }, ["scam", "outro"]],
    [{ scam: false, coach: true }, ["coach", "outro"]],
    [{ scam: false, coach: false }, []],
  ] as const)("is %j for %j", (flags, steps) => {
    expect(tourSteps(flags)).toEqual(steps);
  });
});

describe("whether this worker has been through it", () => {
  it("is false until it is marked, per worker", () => {
    expect(hasSeenTour("alice")).toBe(false);

    markTourSeen("alice");

    expect(hasSeenTour("alice")).toBe(true);
    expect(hasSeenTour("bob")).toBe(false);
  });

  it("keeps the mark under the worker's id and the tour's version", () => {
    markTourSeen("alice");

    expect(tourStorageKey("alice")).toBe("nomadfinance.tour.v2.alice");
    expect(localStorage.getItem("nomadfinance.tour.v2.alice")).not.toBeNull();
  });

  it("is not wiped by what signing out wipes of the Coach", async () => {
    const { clearCoachLocalData } = await import("@/lib/coachLocalData");
    markTourSeen("alice");

    clearCoachLocalData();

    expect(hasSeenTour("alice")).toBe(true);
  });

  it("counts as seen when storage cannot be read, so it never nags", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(hasSeenTour("alice")).toBe(true);
  });

  it("does not throw when storage cannot be written", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("full");
    });

    expect(() => markTourSeen("alice")).not.toThrow();
  });
});
