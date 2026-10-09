// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import GreetingBand from "@/components/dashboard/GreetingBand";

const state = vi.hoisted(() => ({ flags: { coach: false, scam: false } }));

vi.mock("@/hooks/useFeatureFlag", () => ({
  useFeatureFlags: () => ({ flags: state.flags, isLoading: false }),
}));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { displayName: "Pranjal Parmar" } }),
}));
vi.mock("@/hooks/useUser", () => ({ useUserProfile: () => ({ data: undefined }) }));
vi.mock("@/components/visual/AnimatedBackground", () => ({ default: () => null }));
vi.mock("@/components/visual/PillarIllustration", () => ({ default: () => null }));

beforeEach(() => {
  state.flags = { coach: false, scam: false };
});
afterEach(cleanup);

function renderBand() {
  render(
    <MemoryRouter>
      <GreetingBand />
    </MemoryRouter>
  );
}

const link = (name: RegExp) => screen.queryByRole("link", { name });

describe("the welcome band's quick actions", () => {
  it("greets the worker by first name", () => {
    renderBand();

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Welcome, Pranjal");
  });

  it("has the four of v1.0 and nothing of the new pillars when both are off", () => {
    renderBand();

    for (const name of [/Compare rates/, /Check a contract/, /Report an issue/, /Log activity/]) {
      expect(link(name)).not.toBeNull();
    }
    expect(link(/Check a message/)).toBeNull();
    expect(link(/Plan with the Coach/)).toBeNull();
  });

  it("adds Scam Check, linking to its page, when its flag is on", () => {
    state.flags = { coach: false, scam: true };

    renderBand();

    expect(link(/Check a message/)?.getAttribute("href")).toBe("/scam-check");
    expect(link(/Plan with the Coach/)).toBeNull();
  });

  it("adds the Coach, linking to its page, when its flag is on", () => {
    state.flags = { coach: true, scam: false };

    renderBand();

    expect(link(/Plan with the Coach/)?.getAttribute("href")).toBe("/coach");
    expect(link(/Check a message/)).toBeNull();
  });

  it("adds both when both are on, the Coach first as in the navigation", () => {
    state.flags = { coach: true, scam: true };

    renderBand();

    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual([
      "/remittance",
      "/contract",
      "/radar/report",
      "/identity/log",
      "/coach",
      "/scam-check",
    ]);
  });
});
